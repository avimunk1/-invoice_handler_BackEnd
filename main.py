from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, FileResponse
from models import ProcessRequest, ProcessResponse
from pipeline import process_path, process_path_with_llm
from config import settings
import boto3
from typing import Dict, Any
from pathlib import Path
from urllib.parse import unquote

app = FastAPI(title="Invoice Handler", default_response_class=ORJSONResponse)

# CORS middleware for frontend
app.add_middleware(
	CORSMiddleware,
	allow_origins=["http://localhost:5173", "http://localhost:3000"],  # Vite and common dev ports
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
	return {"status": "ok"}


@app.post("/process", response_model=ProcessResponse)
async def process(req: ProcessRequest):
	results = await process_path(req.path, req.recursive, req.language_detection)
	return ProcessResponse(results=results, errors=[])


@app.post("/process/llm", response_model=ProcessResponse)
async def process_with_llm(req: ProcessRequest):
	"""Process documents using Azure OCR + OpenAI LLM for flexible field extraction."""
	results = await process_path_with_llm(req.path, req.recursive, req.language_detection)
	return ProcessResponse(results=results, errors=[])


@app.post("/upload/presigned-url")
async def get_presigned_url(filename: str) -> Dict[str, Any]:
	"""Generate a presigned POST URL for S3 upload"""
	if not settings.s3_bucket:
		return {"error": "S3 bucket not configured"}
	
	s3_client = boto3.client(
		's3',
		region_name=settings.s3_region or settings.aws_region or 'us-east-1'
	)
	
	# Generate unique key with timestamp
	from datetime import datetime
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	key = f"uploads/{timestamp}_{filename}"
	
	# Generate presigned POST
	presigned_post = s3_client.generate_presigned_post(
		Bucket=settings.s3_bucket,
		Key=key,
		ExpiresIn=3600  # 1 hour
	)
	
	return {
		"url": presigned_post["url"],
		"fields": presigned_post["fields"],
		"s3_path": f"s3://{settings.s3_bucket}/{key}"
	}


@app.get("/file/view", response_model=None)
async def view_file(path: str):
	"""Get a viewable URL for a file (S3 presigned URL or local file)"""
	decoded_path = unquote(path)
	
	if decoded_path.startswith("s3://"):
		# Generate presigned GET URL for S3
		if not settings.s3_bucket:
			return {"error": "S3 bucket not configured"}
		
		# Parse S3 path
		import re
		m = re.match(r"s3://([^/]+)/(.+)", decoded_path)
		if not m:
			return {"error": "Invalid S3 path"}
		
		bucket = m.group(1)
		key = m.group(2)
		
		s3_client = boto3.client(
			's3',
			region_name=settings.s3_region or settings.aws_region or 'us-east-1'
		)
		
		# Generate presigned URL for viewing (1 hour expiry)
		url = s3_client.generate_presigned_url(
			'get_object',
			Params={'Bucket': bucket, 'Key': key},
			ExpiresIn=3600
		)
		
		return {"url": url}
	
	elif decoded_path.startswith("file://"):
		# Serve local file directly
		local_path = decoded_path[7:]  # Remove file://
		file_path = Path(local_path)
		
		if not file_path.exists():
			return {"error": "File not found"}
		
		# Determine correct media type
		import mimetypes
		media_type, _ = mimetypes.guess_type(str(file_path))
		if not media_type:
			media_type = 'application/octet-stream'
		
		return FileResponse(
			path=str(file_path),
			filename=file_path.name,
			media_type=media_type
		)
	
	else:
		return {"error": "Invalid path format"}
