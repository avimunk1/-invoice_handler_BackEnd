from typing import List
from pathlib import Path
from models import InvoiceData, LineItem
from azure_di import AzureDIClient
from discovery import discover
from mapping import map_invoice, validate_invoice_data
from classifier import detect_language
from llm_processor import OpenAIClient
import mimetypes
import boto3
import asyncio
from datetime import datetime


async def _read_file_bytes(uri: str):
	"""Read file content from local path or S3."""
	if uri.startswith("s3://"):
		import re
		m = re.match(r"s3://([^/]+)/(.+)", uri)
		if not m:
			raise ValueError(f"Invalid S3 URI: {uri}")
		bucket, key = m.group(1), m.group(2)
		s3 = boto3.client("s3")
		obj = s3.get_object(Bucket=bucket, Key=key)
		content = obj["Body"].read()
		file_name = Path(key).name
		ct = obj.get("ContentType") or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
		return content, ct, file_name, uri
	else:
		# Local file
		if uri.startswith("file://"):
			uri = uri[7:]
		p = Path(uri)
		content = p.read_bytes()
		file_name = p.name
		ct = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
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


async def process_path(path: str, recursive: bool, language_detection: bool) -> List[InvoiceData]:
	client = AzureDIClient()
	uris = discover(path, recursive)
	results: List[InvoiceData] = []
	for uri in uris:
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


async def process_path_with_llm(path: str, recursive: bool, language_detection: bool) -> List[InvoiceData]:
	"""
	Process documents using Azure OCR + OpenAI LLM for field extraction.
	This approach is more flexible for non-standard documents.
	"""
	azure_client = AzureDIClient()
	llm_client = OpenAIClient()
	uris = discover(path, recursive)
	results: List[InvoiceData] = []
	
	for uri in uris:
		try:
			content, content_type, file_name, source_uri = await _read_file_bytes(uri)
			
			# Step 1: Run Azure OCR with Hebrew locale by default
			locale = "he-IL"
			print(f"[DEBUG-LLM] Running OCR for {file_name} (locale: {locale})")
			parsed = await azure_client.analyze_read(content, content_type)
			
			# Extract text content
			ocr_text = parsed.get("content", "")
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
					)
				)
				continue
			
			# Step 2: Send text to LLM for structured extraction
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
				confidence=None  # LLM doesn't provide confidence scores
			)
			
			print(f"[DEBUG-LLM] Successfully processed {file_name} with LLM: type={invoice_data.document_type}, total={invoice_data.total}")
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
				)
			)
	
	return results
