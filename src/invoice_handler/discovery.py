from typing import Iterable, List
from pathlib import Path
import re

try:
	import boto3  # type: ignore
except Exception:  # pragma: no cover
	boto3 = None

SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".txt", ".heic", ".heif"}


def is_supported(path: str) -> bool:
	return Path(path.lower()).suffix in SUPPORTED_EXTENSIONS


def discover_local(root: Path, recursive: bool) -> List[str]:
	if recursive:
		paths = [str(p.resolve()) for p in root.rglob("*") if p.is_file() and is_supported(str(p))]
	else:
		paths = [str(p.resolve()) for p in root.glob("*") if p.is_file() and is_supported(str(p))]
	return [f"file://{p}" for p in paths]


def discover_s3(uri: str, recursive: bool) -> List[str]:
	assert uri.startswith("s3://")
	if boto3 is None:
		raise RuntimeError("boto3 not available for s3 discovery")
	m = re.match(r"s3://([^/]+)/?(.*)", uri)
	assert m
	bucket = m.group(1)
	prefix = m.group(2)
	s3 = boto3.client("s3")
	kwargs = {"Bucket": bucket, "Prefix": prefix}
	objects: List[str] = []
	while True:
		resp = s3.list_objects_v2(**kwargs)
		for obj in resp.get("Contents", []):
			key = obj["Key"]
			if not recursive and "/" in key[len(prefix) :].strip("/"):
				continue
			if is_supported(key):
				objects.append(f"s3://{bucket}/{key}")
		if not resp.get("IsTruncated"):
			break
		kwargs["ContinuationToken"] = resp.get("NextContinuationToken")
	return objects


def discover(path: str, recursive: bool) -> List[str]:
	if path.startswith("file://"):
		p = Path(path[7:])
		return discover_local(p, recursive)
	elif path.startswith("s3://"):
		return discover_s3(path, recursive)
	else:
		# assume local path
		p = Path(path)
		return discover_local(p, recursive)


