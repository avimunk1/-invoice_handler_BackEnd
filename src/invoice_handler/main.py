from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, FileResponse
from .models import ProcessRequest, ProcessResponse
from .pipeline import process_path, process_path_with_llm
import boto3
from typing import Dict, Any, List, Optional
from pathlib import Path
from urllib.parse import unquote
from pydantic import BaseModel, Field
from datetime import date
from .config import settings
import json
from sqlalchemy import select, insert, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from .database import get_engine, close_engine
from .models_db import suppliers, invoices

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
	results, total_files, files_handled = await process_path(
		req.path, req.recursive, req.language_detection, req.starting_point
	)
	return ProcessResponse(
		results=results, 
		errors=[], 
		total_files=total_files,
		files_handled=files_handled,
		vat_rate=settings.vat_rate
	)


@app.post("/process/llm", response_model=ProcessResponse)
async def process_with_llm(req: ProcessRequest):
	"""Process documents using Azure OCR + OpenAI LLM for flexible field extraction."""
	results, total_files, files_handled = await process_path_with_llm(
		req.path, req.recursive, req.language_detection, req.starting_point
	)
	return ProcessResponse(
		results=results, 
		errors=[], 
		total_files=total_files,
		files_handled=files_handled,
		vat_rate=settings.vat_rate
	)


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
	"""Get a viewable URL for a file (S3 presigned URL or local file). Auto-converts HEIC to JPEG."""
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
		
		# Check if HEIC/HEIF - need to convert before serving
		if key.lower().endswith(('.heic', '.heif')):
			# Download, convert, and serve as JPEG
			obj = s3_client.get_object(Bucket=bucket, Key=key)
			heic_content = obj["Body"].read()
			
			# Convert to JPEG
			from .pipeline import _convert_heic_to_jpeg
			from io import BytesIO
			jpeg_content = _convert_heic_to_jpeg(heic_content)
			
			# Return JPEG directly
			from fastapi.responses import Response
			return Response(
				content=jpeg_content,
				media_type="image/jpeg",
				headers={
					"Content-Disposition": f'inline; filename="{Path(key).stem}.jpg"'
				}
			)
		else:
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
		
		# Check if HEIC/HEIF - need to convert before serving
		if file_path.suffix.lower() in ['.heic', '.heif']:
			# Read and convert to JPEG
			heic_content = file_path.read_bytes()
			from .pipeline import _convert_heic_to_jpeg
			jpeg_content = _convert_heic_to_jpeg(heic_content)
			
			# Return JPEG directly
			from fastapi.responses import Response
			return Response(
				content=jpeg_content,
				media_type="image/jpeg",
				headers={
					"Content-Disposition": f'inline; filename="{file_path.stem}.jpg"'
				}
			)
		
		# For other file types, serve as-is
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


# ----------------------------
# Database setup and endpoints
# ----------------------------

class SaveInvoice(BaseModel):
    supplier_id: Optional[int] = None
    supplier_name: Optional[str] = None
    invoice_number: str
    invoice_date: date
    currency: str
    subtotal: float
    vat_amount: float
    total: float
    expense_account_id: Optional[int] = None
    deductible_pct: Optional[float] = None
    doc_name: Optional[str] = None
    doc_full_path: Optional[str] = None
    document_type: Optional[str] = Field(default="invoice")
    status: Optional[str] = Field(default="pending")
    ocr_confidence: Optional[float] = None
    ocr_language: Optional[str] = None
    ocr_metadata: Optional[Dict[str, Any]] = None
    needs_review: Optional[bool] = None
    due_date: Optional[date] = None
    payment_terms: Optional[str] = None


class BatchSaveRequest(BaseModel):
    customer_id: int
    invoices: List[SaveInvoice]


class BatchSaveResult(BaseModel):
    index: int
    invoice_number: str
    inserted_id: Optional[int] = None
    supplier_id: Optional[int] = None
    supplier_created: Optional[bool] = None
    conflict: bool = False
    error: Optional[str] = None


@app.on_event("startup")
async def startup_db():
    # Engine is created lazily via get_engine()
    pass


@app.on_event("shutdown")
async def shutdown_db():
    await close_engine()


async def _ensure_supplier(conn, customer_id: int, supplier_id: Optional[int], supplier_name: Optional[str]) -> tuple[int, bool]:
    """Ensure supplier exists, update if needed, or create new one."""
    from sqlalchemy import func
    
    if supplier_id is not None:
        # If supplier_id exists and name is provided, update the supplier name
        if supplier_name:
            stmt = (
                update(suppliers)
                .where(suppliers.c.id == supplier_id, suppliers.c.customer_id == customer_id)
                .values(name=supplier_name, updated_at=func.now())
            )
            await conn.execute(stmt)
        return supplier_id, False
    
    if not supplier_name:
        raise ValueError("supplier_id or supplier_name is required")
    
    # Try match by OCR identification first, then by name
    stmt = select(suppliers.c.id).where(
        suppliers.c.customer_id == customer_id,
        (suppliers.c.ocr_supplier_identification == supplier_name) | (suppliers.c.name == supplier_name)
    )
    result = await conn.execute(stmt)
    row = result.first()
    if row:
        return int(row.id), False
    
    # Create new supplier
    stmt = (
        insert(suppliers)
        .values(
            customer_id=customer_id,
            name=supplier_name,
            ocr_supplier_identification=supplier_name,
            active=True
        )
        .returning(suppliers.c.id)
    )
    result = await conn.execute(stmt)
    row = result.first()
    return int(row.id), True


@app.post("/invoices/batch")
async def save_invoices_batch(payload: BatchSaveRequest) -> Dict[str, Any]:
    from sqlalchemy import func
    
    engine = get_engine()
    results: List[BatchSaveResult] = []
    
    async with engine.begin() as conn:  # Automatically commits or rolls back
        for idx, inv in enumerate(payload.invoices):
            try:
                sup_id, created = await _ensure_supplier(conn, payload.customer_id, inv.supplier_id, inv.supplier_name)
                
                # Build upsert statement
                stmt = pg_insert(invoices).values(
                    customer_id=payload.customer_id,
                    supplier_id=sup_id,
                    invoice_number=inv.invoice_number,
                    invoice_date=inv.invoice_date,
                    due_date=inv.due_date,
                    currency=inv.currency,
                    subtotal=inv.subtotal,
                    vat_amount=inv.vat_amount,
                    total=inv.total,
                    expense_account_id=inv.expense_account_id,
                    deductible_pct=inv.deductible_pct,
                    doc_name=inv.doc_name,
                    doc_full_path=inv.doc_full_path,
                    document_type=inv.document_type,
                    status=inv.status,
                    ocr_confidence=inv.ocr_confidence,
                    ocr_language=inv.ocr_language,
                    ocr_metadata=inv.ocr_metadata,  # SQLAlchemy handles JSONB serialization
                    needs_review=inv.needs_review,
                    payment_terms=inv.payment_terms,
                )
                
                # On conflict, update all fields
                stmt = stmt.on_conflict_do_update(
                    index_elements=['customer_id', 'supplier_id', 'invoice_number'],
                    set_={
                        'invoice_date': stmt.excluded.invoice_date,
                        'due_date': stmt.excluded.due_date,
                        'currency': stmt.excluded.currency,
                        'subtotal': stmt.excluded.subtotal,
                        'vat_amount': stmt.excluded.vat_amount,
                        'total': stmt.excluded.total,
                        'expense_account_id': stmt.excluded.expense_account_id,
                        'deductible_pct': stmt.excluded.deductible_pct,
                        'doc_name': stmt.excluded.doc_name,
                        'doc_full_path': stmt.excluded.doc_full_path,
                        'document_type': stmt.excluded.document_type,
                        'status': stmt.excluded.status,
                        'ocr_confidence': stmt.excluded.ocr_confidence,
                        'ocr_language': stmt.excluded.ocr_language,
                        'ocr_metadata': stmt.excluded.ocr_metadata,
                        'needs_review': stmt.excluded.needs_review,
                        'payment_terms': stmt.excluded.payment_terms,
                        'updated_at': func.now(),
                    }
                ).returning(invoices.c.id)
                
                result = await conn.execute(stmt)
                row = result.first()
                
                if row and row.id is not None:
                    results.append(BatchSaveResult(
                        index=idx,
                        invoice_number=inv.invoice_number,
                        inserted_id=int(row.id),
                        supplier_id=sup_id,
                        supplier_created=created
                    ))
                else:
                    results.append(BatchSaveResult(
                        index=idx,
                        invoice_number=inv.invoice_number,
                        inserted_id=None,
                        supplier_id=sup_id,
                        supplier_created=created,
                        error="No ID returned from database"
                    ))
            except Exception as e:
                results.append(BatchSaveResult(
                    index=idx,
                    invoice_number=inv.invoice_number,
                    supplier_id=sup_id if 'sup_id' in locals() else None,
                    supplier_created=created if 'created' in locals() else None,
                    error=f"{type(e).__name__}: {str(e)}"
                ))
    
    return {"results": [r.dict() for r in results]}


