from typing import List, Tuple, Dict, Any
from pathlib import Path
import mimetypes

from azure_di import AzureDIClient
from discovery import discover
from classifier import classify_text, detect_language
from models import InvoiceData
from mapping import map_receipt, map_invoice, validate_invoice_data


async def _read_file_bytes(uri: str) -> Tuple[bytes, str, str, str]:
	# returns: (content, content_type, file_name, normalized_source_uri)
	if uri.startswith("file://"):
		p = Path(uri[7:])
		content = p.read_bytes()
		file_name = p.name
		ext = p.suffix.lower()
		ct = mimetypes.guess_type(file_name)[0] or (
			"application/pdf" if ext == ".pdf" else "application/octet-stream"
		)
		return content, ct, file_name, f"file://{str(p.resolve())}"
	elif uri.startswith("s3://"):
		# Lazy import to avoid hard dependency when unused
		import boto3  # type: ignore
		import re

		m = re.match(r"s3://([^/]+)/(.+)", uri)
		assert m
		bucket = m.group(1)
		key = m.group(2)
		s3 = boto3.client("s3")
		obj = s3.get_object(Bucket=bucket, Key=key)
		content = obj["Body"].read()
		file_name = Path(key).name
		ct = obj.get("ContentType") or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
		version_id = obj.get("VersionId")
		source = f"s3://{bucket}/{key}" + (f"?versionId={version_id}" if version_id else "")
		return content, ct, file_name, source
	else:
		# treat as local path
		p = Path(uri)
		content = p.read_bytes()
		file_name = p.name
		ct = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
		return content, ct, file_name, f"file://{str(p.resolve())}"


async def process_path(path: str, recursive: bool, language_detection: bool) -> List[InvoiceData]:
	client = AzureDIClient()
	uris = discover(path, recursive)
	results: List[InvoiceData] = []
	for uri in uris:
		try:
			content, content_type, file_name, source_uri = await _read_file_bytes(uri)
			
			# Optimized: Call invoice analyzer directly (saves 50% API calls vs analyze_read first)
			# Invoice analyzer can handle invoices, receipts, bills, and returns full text content
			print(f"[DEBUG] Analyzing {file_name} with invoice analyzer")
			parsed = await client.analyze_invoice(content, content_type)
			
			# Extract text content from Azure response for language detection and classification
			azure_content = parsed.get("content", "")
			print(f"[DEBUG] Extracted text preview for {file_name}: {azure_content[:200]}")
			
			# Detect language from Azure's text extraction
			lang = detect_language(azure_content) if language_detection and azure_content else "en"
			print(f"[DEBUG] Detected language for {file_name}: {lang}")
			
			# Map the invoice data
			mapped = map_invoice(parsed, file_name=file_name, source_path=source_uri, language=lang)
			
			# Determine document type based on what Azure found
			if mapped.invoice_number or mapped.total or mapped.supplier_name:
				# Azure successfully extracted invoice/receipt data
				mapped.document_type = "invoice"
				print(f"[DEBUG] Successfully processed {file_name} as invoice")
			else:
				# Azure didn't find structured invoice data
				# Future: This is where you can add logic to try other analyzers or mark as "other"
				mapped.document_type = "other"
				print(f"[DEBUG] No invoice data found for {file_name}, marked as 'other'")
			
			# Optional: Use classifier for validation/logging (not for routing anymore)
			doc_type_hint, cls_score = classify_text(azure_content or "")
			print(f"[DEBUG] Classifier hint for {file_name}: type={doc_type_hint}, score={cls_score}")
			
			results.append(validate_invoice_data(mapped))
		except Exception as e:
			print(f"[ERROR] Failed to process {uri}: {type(e).__name__}: {str(e)}")
			import traceback
			traceback.print_exc()
			results.append(
				InvoiceData(
					file_name=Path(uri).name,
					source_path=uri,
					language="en",
					document_type="other",
					supplier_name=None,
					invoice_number=None,
					invoice_date=None,
					currency=None,
					subtotal=None,
					tax_amount=None,
					total=None,
					line_items=None,
					confidence=0.0,
				)
			)
	return results
