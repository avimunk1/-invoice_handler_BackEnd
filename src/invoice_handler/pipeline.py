from typing import List
from pathlib import Path
from .models import InvoiceData, LineItem
from .azure_di import AzureDIClient
from .discovery import discover
from .mapping import map_invoice, validate_invoice_data
from .llm_processor import OpenAIClient
import mimetypes
import asyncio
from datetime import datetime
from io import BytesIO
import re
import shutil


# Hebrew character detection for language identification
HEBREW_CHARS = re.compile(r"[\u0590-\u05FF]")


def detect_language(text: str) -> str:
	"""Detect language based on character set (Hebrew vs English)."""
	if HEBREW_CHARS.search(text or ""):
		return "he"
	return "en"


def _move_to_processed(file_path: str) -> str:
	"""
	Move a processed file to the 'processed' subdirectory to avoid reprocessing.
	
	Returns the new file path (with file:// prefix if it was present), or the original path if move failed.
	"""
	try:
		had_prefix = False
		original_path = file_path
		
		# Only move local files, not S3 files
		if file_path.startswith("file://"):
			file_path = file_path[7:]  # Remove file:// prefix
			had_prefix = True
		elif file_path.startswith("s3://"):
			# Don't move S3 files
			return original_path
		
		source = Path(file_path)
		if not source.exists():
			return original_path
		
		# Create processed directory next to the input directory
		processed_dir = source.parent / "processed"
		processed_dir.mkdir(parents=True, exist_ok=True)
		
		# Move file to processed directory
		destination = processed_dir / source.name
		
		# If destination exists, add a counter to make it unique
		if destination.exists():
			counter = 1
			stem = source.stem
			suffix = source.suffix
			while destination.exists():
				destination = processed_dir / f"{stem}_{counter}{suffix}"
				counter += 1
		
		shutil.move(str(source), str(destination))
		print(f"[INFO] Moved processed file: {source.name} → processed/{destination.name}")
		
		# Return new path with file:// prefix if original had it
		new_path = str(destination)
		if had_prefix:
			new_path = f"file://{new_path}"
		return new_path
		
	except Exception as e:
		print(f"[WARN] Failed to move file {file_path} to processed: {e}")
		return original_path


def _convert_heic_to_jpeg(heic_content: bytes) -> bytes:
	"""Convert HEIC/HEIF image to JPEG format."""
	try:
		from pillow_heif import register_heif_opener
		from PIL import Image
		
		# Register HEIF opener with Pillow
		register_heif_opener()
		
		# Open HEIC image from bytes
		heic_image = Image.open(BytesIO(heic_content))
		
		# Convert to RGB if necessary (HEIC can have different color modes)
		if heic_image.mode not in ('RGB', 'L'):
			heic_image = heic_image.convert('RGB')
		
		# Save as JPEG to bytes
		jpeg_buffer = BytesIO()
		heic_image.save(jpeg_buffer, format='JPEG', quality=95)
		jpeg_buffer.seek(0)
		
		print("[INFO] Successfully converted HEIC to JPEG")
		return jpeg_buffer.read()
	except Exception as e:
		print(f"[ERROR] Failed to convert HEIC to JPEG: {type(e).__name__}: {str(e)}")
		raise


async def _read_file_bytes(uri: str):
	"""Read file content from local path or S3. Converts HEIC/HEIF to JPEG automatically."""
	if uri.startswith("s3://"):
		import re
		m = re.match(r"s3://([^/]+)/(.+)", uri)
		if not m:
			raise ValueError(f"Invalid S3 URI: {uri}")
		bucket, key = m.group(1), m.group(2)
		from .s3_client import get_s3_client
		s3 = get_s3_client()
		obj = s3.get_object(Bucket=bucket, Key=key)
		content = obj["Body"].read()
		file_name = Path(key).name
		ct = obj.get("ContentType") or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
		
		# Convert HEIC/HEIF to JPEG
		if file_name.lower().endswith(('.heic', '.heif')):
			print(f"[INFO] Detected HEIC/HEIF file: {file_name}, converting to JPEG")
			content = _convert_heic_to_jpeg(content)
			ct = "image/jpeg"
			# Update filename for logging purposes
			file_name = file_name.rsplit('.', 1)[0] + '.jpg'
		
		return content, ct, file_name, uri
	else:
		# Local file
		if uri.startswith("file://"):
			uri = uri[7:]
		p = Path(uri)
		content = p.read_bytes()
		file_name = p.name
		ct = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
		
		# Convert HEIC/HEIF to JPEG
		if file_name.lower().endswith(('.heic', '.heif')):
			print(f"[INFO] Detected HEIC/HEIF file: {file_name}, converting to JPEG")
			content = _convert_heic_to_jpeg(content)
			ct = "image/jpeg"
			# Update filename for logging purposes
			file_name = file_name.rsplit('.', 1)[0] + '.jpg'
		
		return content, ct, file_name, f"file://{str(p.resolve())}"


async def process_specific_files(file_paths: List[str], language_detection: bool) -> List[InvoiceData]:
	"""Process specific file paths without directory discovery"""
	client = AzureDIClient()
	results: List[InvoiceData] = []
	for uri in file_paths:
		try:
			content, content_type, file_name, source_uri = await _read_file_bytes(uri)
			
			# TESTING: Hardcode Hebrew locale to test OCR improvement
			locale = "he-IL"
			print(f"[DEBUG] Analyzing {file_name} with invoice analyzer (locale: {locale})")
			parsed = await client.analyze_invoice(content, content_type, locale=locale)
			
			# Extract text content from Azure response for language detection
			azure_content = parsed.get("content", "")
			print(f"[DEBUG] Extracted text preview for {file_name}: {azure_content[:200]}")
			
			# Detect language from Azure's text extraction
			lang = detect_language(azure_content) if language_detection and azure_content else "en"
			print(f"[DEBUG] Detected language for {file_name}: {lang}")
			
			# Generate file_url for viewing
			from urllib.parse import quote
			file_view_url = f"/file/view?path={quote(source_uri)}"
			
			# Map the invoice data
			mapped = map_invoice(parsed, file_name=file_name, source_path=source_uri, language=lang, file_url=file_view_url)
			
			# Determine document type based on what Azure found
			if mapped.invoice_number or mapped.total or mapped.supplier_name:
				mapped.document_type = "invoice"
				print(f"[DEBUG] Successfully processed {file_name} as invoice")
			else:
				mapped.document_type = "other"
				print(f"[DEBUG] No invoice data found for {file_name}, marked as 'other'")
			
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


async def process_path(path: str, recursive: bool, language_detection: bool, starting_point: int = 0) -> tuple[List[InvoiceData], int, int]:
	"""
	Process invoices from a path with bulk processing support.
	
	Args:
		path: Path to process (local or S3)
		recursive: Whether to process recursively
		language_detection: Whether to detect language
		starting_point: Index to start processing from (0-based)
	
	Returns:
		Tuple of (results, total_files, files_handled)
	"""
	from .config import settings
	
	client = AzureDIClient()
	uris = discover(path, recursive)
	total_files = len(uris)
	
	# Calculate the slice of files to process in this batch
	end_point = min(starting_point + settings.bulk_size, total_files)
	uris_to_process = uris[starting_point:end_point]
	files_handled = len(uris_to_process)
	
	print(f"[DEBUG] Processing batch: {starting_point} to {end_point} of {total_files} files")
	
	results: List[InvoiceData] = []
	for uri in uris_to_process:
		try:
			content, content_type, file_name, source_uri = await _read_file_bytes(uri)
			
			# TESTING: Hardcode Hebrew locale to test OCR improvement
			locale = "he-IL"
			print(f"[DEBUG] Analyzing {file_name} with invoice analyzer (locale: {locale})")
			parsed = await client.analyze_invoice(content, content_type, locale=locale)
			
			# Extract text content from Azure response for language detection
			azure_content = parsed.get("content", "")
			print(f"[DEBUG] Extracted text preview for {file_name}: {azure_content[:200]}")
			
			# Detect language from Azure's text extraction
			lang = detect_language(azure_content) if language_detection and azure_content else "en"
			print(f"[DEBUG] Detected language for {file_name}: {lang}")
			
			# Generate file_url for viewing
			from urllib.parse import quote
			file_view_url = f"/file/view?path={quote(source_uri)}"
			
			# Map the invoice data
			mapped = map_invoice(parsed, file_name=file_name, source_path=source_uri, language=lang, file_url=file_view_url)
			
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
			
			validated = validate_invoice_data(mapped)
			
			# Move successfully processed file to 'processed' directory and update path
			new_uri = _move_to_processed(uri)
			if new_uri != uri:
				validated.source_path = new_uri
				# Also update file_url to point to new location
				from urllib.parse import quote
				validated.file_url = f"/file/view?path={quote(new_uri)}"
			
			results.append(validated)
			
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
	return results, total_files, files_handled


async def process_path_with_llm(path: str, recursive: bool, language_detection: bool, starting_point: int = 0) -> tuple[List[InvoiceData], int, int]:
	"""
	Process documents using Azure Invoice Analyzer + Azure OCR + OpenAI LLM.
	
	This hybrid approach provides:
	1. Bounding boxes and page count from Azure Invoice Analyzer
	2. Text extraction from Azure OCR
	3. Flexible field extraction from OpenAI LLM
	
	Best of both worlds: LLM's intelligent extraction + Azure's visual coordinates.
	
	Args:
		path: Path to process (local or S3)
		recursive: Whether to process recursively
		language_detection: Whether to detect language
		starting_point: Index to start processing from (0-based)
	
	Returns:
		Tuple of (results, total_files, files_handled)
	"""
	from .config import settings
	
	azure_client = AzureDIClient()
	llm_client = OpenAIClient()
	uris = discover(path, recursive)
	total_files = len(uris)
	
	# Calculate the slice of files to process in this batch
	end_point = min(starting_point + settings.bulk_size, total_files)
	uris_to_process = uris[starting_point:end_point]
	files_handled = len(uris_to_process)
	
	print(f"[DEBUG-LLM] Processing batch: {starting_point} to {end_point} of {total_files} files")
	
	results: List[InvoiceData] = []
	
	for uri in uris_to_process:
		try:
			content, content_type, file_name, source_uri = await _read_file_bytes(uri)
			
			# Step 1: Run Azure Invoice Analyzer to get bounding boxes and page count
			locale = "he-IL"
			print(f"[DEBUG-LLM] Running Invoice Analyzer for {file_name} to get bounding boxes (locale: {locale})")
			invoice_parsed = await azure_client.analyze_invoice(content, content_type, locale=locale)
			
			# Extract bounding boxes, confidence, and page count from invoice analyzer
			from .mapping import _extract_bounding_box, _get_page_count, _get_page_dimensions, _extract_field_confidence
			fields = invoice_parsed.get("documents", [{}])[0].get("fields", {}) if invoice_parsed.get("documents") else invoice_parsed.get("fields", {})
			
			# Debug: log field confidence scores
			print(f"[DEBUG-LLM] Field confidence scores for {file_name}:")
			for field_name, field_data in fields.items():
				if isinstance(field_data, dict):
					confidence = field_data.get('confidence')
					if confidence is not None:
						print(f"[DEBUG-LLM]   {field_name}: {confidence:.3f}")
			
			# Get page dimensions for normalization
			page_dims = _get_page_dimensions(invoice_parsed)
			page_count = _get_page_count(invoice_parsed)
			
			bounding_boxes = {}
			field_confidences = {}
			field_mapping = {
				"VendorName": "supplier_name",
				"CustomerName": "supplier_name",
				"InvoiceId": "invoice_number",
				"InvoiceNumber": "invoice_number",
				"InvoiceDate": "invoice_date",
				"SubTotal": "subtotal",
				"TotalTax": "tax_amount",
				"InvoiceTotal": "total",
				"MerchantName": "supplier_name",
				"TransactionDate": "invoice_date",
				"Subtotal": "subtotal",
				"Tax": "tax_amount",
				"Total": "total",
			}
			
			for azure_field_name, our_field_name in field_mapping.items():
				if azure_field_name in fields:
					# Extract bounding box
					if our_field_name not in bounding_boxes:
						bbox = _extract_bounding_box(fields[azure_field_name], page_dims)
						if bbox:
							bounding_boxes[our_field_name] = bbox
					
					# Extract confidence
					if our_field_name not in field_confidences:
						conf = _extract_field_confidence(fields[azure_field_name])
						if conf is not None:
							field_confidences[our_field_name] = conf
			
			print(f"[DEBUG-LLM] Extracted {len(bounding_boxes)} bounding boxes, {len(field_confidences)} confidences, page_count={page_count}")
			
			# Step 2: Run Azure OCR to get text for LLM
			print(f"[DEBUG-LLM] Running OCR for {file_name} to get text")
			ocr_parsed = await azure_client.analyze_read(content, content_type)
			
			# Extract text content
			ocr_text = ocr_parsed.get("content", "")
			print(f"[DEBUG-LLM] Extracted {len(ocr_text)} characters of text")
			print(f"[DEBUG-LLM] OCR text preview for {file_name}:")
			print("=" * 80)
			print(ocr_text[:1000])  # Print first 1000 characters
			print("=" * 80)
			
			if not ocr_text:
				print(f"[WARN-LLM] No text extracted from {file_name}, skipping")
				results.append(
					InvoiceData(
						file_name=file_name,
						source_path=source_uri,
						language="unknown",
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
						bounding_boxes=bounding_boxes if bounding_boxes else None,
						page_count=page_count,
					)
				)
				continue
			
			# Step 3: Send text to LLM for structured extraction
			print(f"[DEBUG-LLM] Sending to LLM for extraction")
			llm_result = await llm_client.extract_invoice_data(ocr_text, file_name)
			
			# Step 3: Parse LLM response into InvoiceData
			from urllib.parse import quote
			file_view_url = f"/file/view?path={quote(source_uri)}"
			
			# Convert line items
			line_items = None
			if llm_result.get("line_items"):
				line_items = [
					LineItem(
						description=item.get("description"),
						quantity=item.get("quantity"),
						unit_price=item.get("unit_price"),
						line_total=item.get("line_total")
					)
					for item in llm_result.get("line_items", [])
					if item.get("description")  # Only include items with descriptions
				]
			
			invoice_data = InvoiceData(
				file_name=file_name,
				source_path=source_uri,
				file_url=file_view_url,
				language=llm_result.get("language", "unknown"),
				document_type=llm_result.get("document_type", "other"),
				supplier_name=llm_result.get("supplier_name"),
				invoice_number=llm_result.get("invoice_number"),
				invoice_date=llm_result.get("invoice_date"),
				currency=llm_result.get("currency"),
				subtotal=llm_result.get("subtotal"),
				tax_amount=llm_result.get("tax_amount"),
				total=llm_result.get("total"),
				line_items=line_items,
				confidence=None,  # LLM doesn't provide confidence scores
				bounding_boxes=bounding_boxes if bounding_boxes else None,  # Add bounding boxes from Azure
				page_count=page_count,  # Add page count from Azure
				field_confidence=field_confidences if field_confidences else None,  # Add field confidence from Azure
			)
			
			print(f"[DEBUG-LLM] Successfully processed {file_name} with LLM: type={invoice_data.document_type}, total={invoice_data.total}, bboxes={len(bounding_boxes)}")
			
			# Move successfully processed file to 'processed' directory and update path
			new_uri = _move_to_processed(uri)
			if new_uri != uri:
				invoice_data.source_path = new_uri
				# Also update file_url to point to new location
				from urllib.parse import quote
				invoice_data.file_url = f"/file/view?path={quote(new_uri)}"
			
			results.append(invoice_data)
			
		except Exception as e:
			print(f"[ERROR-LLM] Failed to process {uri}: {type(e).__name__}: {str(e)}")
			import traceback
			traceback.print_exc()
			results.append(
				InvoiceData(
					file_name=Path(uri).name,
					source_path=uri,
					language="unknown",
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
					bounding_boxes=None,
					page_count=None,
				)
			)
	
	return results, total_files, files_handled


