from typing import Any, Dict, List, Optional
from models import InvoiceData, LineItem, BoundingBox
from dateutil import parser as dateparser


def _safe_float(v: Any) -> Optional[float]:
	try:
		if v is None:
			return None
		return float(v)
	except Exception:
		return None


def _parse_date(v: Any) -> Optional[str]:
	try:
		if not v:
			return None
		return dateparser.parse(str(v)).date().isoformat()
	except Exception:
		return None


def _extract_bounding_box(field: Dict[str, Any], page_dims: Dict[int, tuple]) -> Optional[BoundingBox]:
	"""
	Extract and normalize bounding box from Azure DI field.
	
	Args:
		field: Azure DI field containing boundingRegions
		page_dims: Dictionary mapping page_number -> (width, height) in Azure's units
	
	Returns:
		BoundingBox with normalized coordinates (0-1 range)
	"""
	try:
		if not isinstance(field, dict):
			return None
		bounding_regions = field.get("boundingRegions", [])
		if not bounding_regions or len(bounding_regions) == 0:
			return None
		# Take the first bounding region
		region = bounding_regions[0]
		polygon = region.get("polygon", [])
		page_number = region.get("pageNumber", 1)
		
		if not polygon or len(polygon) < 8:  # Need at least 4 points (8 values)
			return None
		
		# Get page dimensions for normalization
		if page_number not in page_dims:
			print(f"[WARN] No page dimensions found for page {page_number}")
			return None
		
		page_width, page_height = page_dims[page_number]
		
		# Convert flat list [x1, y1, x2, y2, x3, y3, x4, y4] to [[x1,y1], [x2,y2], ...]
		# and normalize to 0-1 range
		polygon_points = [
			[polygon[i] / page_width, polygon[i+1] / page_height] 
			for i in range(0, len(polygon), 2)
		]
		
		print(f"[DEBUG] Normalized bbox for page {page_number}: {polygon[:2]} -> {polygon_points[0]}")
		
		return BoundingBox(polygon=polygon_points, page_number=page_number)
	except Exception as e:
		print(f"[DEBUG] Failed to extract bounding box: {e}")
		import traceback
		traceback.print_exc()
		return None


def _extract_field_confidence(field: Dict[str, Any]) -> Optional[float]:
	"""Extract confidence score from Azure DI field."""
	try:
		if not isinstance(field, dict):
			return None
		return field.get("confidence")
	except Exception:
		return None


def _get_page_dimensions(di: Dict[str, Any]) -> Dict[int, tuple]:
	"""
	Extract page dimensions from Azure DI response.
	
	Returns:
		Dictionary mapping page_number -> (width, height) in Azure's coordinate units
	"""
	try:
		pages = di.get("pages", [])
		page_dims = {}
		for page in pages:
			page_number = page.get("pageNumber", 1)
			width = page.get("width", 1)
			height = page.get("height", 1)
			page_dims[page_number] = (width, height)
			print(f"[DEBUG] Page {page_number} dimensions: {width} x {height}")
		return page_dims if page_dims else {1: (1, 1)}
	except Exception as e:
		print(f"[WARN] Failed to extract page dimensions: {e}")
		return {1: (1, 1)}


def _get_page_count(di: Dict[str, Any]) -> int:
	"""Extract total page count from Azure DI response."""
	try:
		pages = di.get("pages", [])
		return len(pages) if pages else 1
	except Exception:
		return 1


def map_receipt(di: Dict[str, Any], file_name: str, source_path: str, language: str, file_url: Optional[str] = None) -> InvoiceData:
	fields = di.get("documents", [{}])[0].get("fields", {}) if di.get("documents") else di.get("fields", {})
	
	# Helper to extract currency values (amount and currencyCode)
	def get_currency_value(field):
		if not isinstance(field, dict):
			return None, None
		currency_obj = field.get("valueCurrency", {})
		if currency_obj:
			return _safe_float(currency_obj.get("amount")), currency_obj.get("currencyCode")
		# Fallback to valueNumber for non-currency fields
		return _safe_float(field.get("valueNumber")), None
	
	items = []
	for it in (fields.get("Items", {}).get("valueArray", []) if isinstance(fields.get("Items"), dict) else []):
		obj = it.get("valueObject", {})
		desc = (obj.get("Description", {}) or {}).get("valueString") if isinstance(obj.get("Description"), dict) else None
		quantity = _safe_float((obj.get("Quantity", {}) or {}).get("valueNumber") if isinstance(obj.get("Quantity"), dict) else None)
		# Price and TotalPrice might be currency fields
		unit_price_val, _ = get_currency_value(obj.get("Price", {}))
		line_total_val, _ = get_currency_value(obj.get("TotalPrice", {}))
		if desc:
			items.append(LineItem(description=desc, quantity=quantity, unit_price=unit_price_val, line_total=line_total_val))

	# Extract currency amounts
	subtotal_val, _ = get_currency_value(fields.get("Subtotal", {}))
	tax_val, _ = get_currency_value(fields.get("TotalTax", {}))
	if tax_val is None:  # Try "Tax" field as fallback
		tax_val, _ = get_currency_value(fields.get("Tax", {}))
	total_val, currency_code = get_currency_value(fields.get("Total", {}))
	
	# If we didn't get currency from Total, try Subtotal
	if not currency_code:
		_, currency_code = get_currency_value(fields.get("Subtotal", {}))

	# Extract page dimensions, bounding boxes, and field confidence
	page_dims = _get_page_dimensions(di)
	page_count = _get_page_count(di)
	
	bounding_boxes = {}
	field_confidences = {}
	field_mapping = {
		"MerchantName": "supplier_name",
		"TransactionDate": "invoice_date",
		"Subtotal": "subtotal",
		"TotalTax": "tax_amount",
		"Tax": "tax_amount",
		"Total": "total",
	}
	
	for azure_field_name, our_field_name in field_mapping.items():
		if azure_field_name in fields:
			# Extract bounding box
			bbox = _extract_bounding_box(fields[azure_field_name], page_dims)
			if bbox:
				bounding_boxes[our_field_name] = bbox
			
			# Extract confidence (don't overwrite if already set from another field)
			if our_field_name not in field_confidences:
				conf = _extract_field_confidence(fields[azure_field_name])
				if conf is not None:
					field_confidences[our_field_name] = conf

	return InvoiceData(
		file_name=file_name,
		source_path=source_path,
		file_url=file_url,
		language=language,
		document_type="receipt",
		supplier_name=(fields.get("MerchantName", {}) or {}).get("valueString") if isinstance(fields.get("MerchantName"), dict) else None,
		invoice_number=None,
		invoice_date=_parse_date((fields.get("TransactionDate", {}) or {}).get("valueDate") if isinstance(fields.get("TransactionDate"), dict) else None),
		currency=currency_code,
		subtotal=subtotal_val,
		tax_amount=tax_val,
		total=total_val,
		line_items=items or None,
		confidence=_safe_float(di.get("confidence")) or None,
		bounding_boxes=bounding_boxes if bounding_boxes else None,
		page_count=page_count,
		field_confidence=field_confidences if field_confidences else None,
	)


def map_invoice(di: Dict[str, Any], file_name: str, source_path: str, language: str, file_url: Optional[str] = None) -> InvoiceData:
	fields = di.get("documents", [{}])[0].get("fields", {}) if di.get("documents") else di.get("fields", {})
	# Debug: print all available field names and their values with confidence
	print(f"[DEBUG] Available fields for {file_name}: {list(fields.keys())}")
	for field_name, field_data in fields.items():
		if isinstance(field_data, dict):
			value = field_data.get('valueString') or field_data.get('valueNumber') or field_data.get('valueDate') or field_data.get('valueCurrency', {}).get('amount')
			confidence = field_data.get('confidence')
			print(f"[DEBUG]   {field_name}: {value} (confidence: {confidence})")
	
	# Helper to extract currency values (amount and currencyCode)
	def get_currency_value(field):
		if not isinstance(field, dict):
			return None, None
		currency_obj = field.get("valueCurrency", {})
		if currency_obj:
			return _safe_float(currency_obj.get("amount")), currency_obj.get("currencyCode")
		# Fallback to valueNumber for non-currency fields
		return _safe_float(field.get("valueNumber")), None
	
	items = []
	for it in (fields.get("Items", {}).get("valueArray", []) if isinstance(fields.get("Items"), dict) else []):
		obj = it.get("valueObject", {})
		desc = (obj.get("Description", {}) or {}).get("valueString") if isinstance(obj.get("Description"), dict) else None
		quantity = _safe_float((obj.get("Quantity", {}) or {}).get("valueNumber") if isinstance(obj.get("Quantity"), dict) else None)
		# UnitPrice and Amount might be currency fields
		unit_price_val, _ = get_currency_value(obj.get("UnitPrice", {}))
		line_total_val, _ = get_currency_value(obj.get("Amount", {}))
		if desc:
			items.append(LineItem(description=desc, quantity=quantity, unit_price=unit_price_val, line_total=line_total_val))

	# Extract currency amounts
	subtotal_val, _ = get_currency_value(fields.get("SubTotal", {}))
	tax_val, _ = get_currency_value(fields.get("TotalTax", {}))
	total_val, currency_code = get_currency_value(fields.get("InvoiceTotal", {}))
	
	# If we didn't get currency from InvoiceTotal, try SubTotal
	if not currency_code:
		_, currency_code = get_currency_value(fields.get("SubTotal", {}))

	# Extract page dimensions, bounding boxes, and field confidence
	page_dims = _get_page_dimensions(di)
	page_count = _get_page_count(di)
	
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
	}
	
	for azure_field_name, our_field_name in field_mapping.items():
		if azure_field_name in fields:
			# Extract bounding box (don't overwrite if already set)
			if our_field_name not in bounding_boxes:
				bbox = _extract_bounding_box(fields[azure_field_name], page_dims)
				if bbox:
					bounding_boxes[our_field_name] = bbox
			
			# Extract confidence (don't overwrite if already set)
			if our_field_name not in field_confidences:
				conf = _extract_field_confidence(fields[azure_field_name])
				if conf is not None:
					field_confidences[our_field_name] = conf

	return InvoiceData(
		file_name=file_name,
		source_path=source_path,
		file_url=file_url,
		language=language,
		document_type="invoice",
		supplier_name=(fields.get("VendorName", {}) or {}).get("valueString") if isinstance(fields.get("VendorName"), dict) else (fields.get("CustomerName", {}) or {}).get("valueString") if isinstance(fields.get("CustomerName"), dict) else None,
		invoice_number=(fields.get("InvoiceId", {}) or {}).get("valueString") if isinstance(fields.get("InvoiceId"), dict) else (fields.get("InvoiceNumber", {}) or {}).get("valueString") if isinstance(fields.get("InvoiceNumber"), dict) else None,
		invoice_date=_parse_date((fields.get("InvoiceDate", {}) or {}).get("valueDate") if isinstance(fields.get("InvoiceDate"), dict) else None),
		currency=currency_code,
		subtotal=subtotal_val,
		tax_amount=tax_val,
		total=total_val,
		line_items=items or None,
		confidence=_safe_float(di.get("confidence")) or None,
		bounding_boxes=bounding_boxes if bounding_boxes else None,
		page_count=page_count,
		field_confidence=field_confidences if field_confidences else None,
	)


def validate_invoice_data(data: InvoiceData) -> InvoiceData:
	# Cross-check totals when available
	if data.subtotal is not None and data.tax_amount is not None and data.total is not None:
		computed = round((data.subtotal or 0.0) + (data.tax_amount or 0.0), 2)
		if abs(computed - (data.total or 0.0)) <= 0.02:
			return data
		# If mismatch is large, prefer total and keep others as-is; could flag in future
	return data
