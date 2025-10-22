from typing import Any, Dict, List, Optional
from models import InvoiceData, LineItem
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
	)


def map_invoice(di: Dict[str, Any], file_name: str, source_path: str, language: str, file_url: Optional[str] = None) -> InvoiceData:
	fields = di.get("documents", [{}])[0].get("fields", {}) if di.get("documents") else di.get("fields", {})
	# Debug: print all available field names and their values
	print(f"[DEBUG] Available fields for {file_name}: {list(fields.keys())}")
	for field_name, field_data in fields.items():
		if isinstance(field_data, dict):
			value = field_data.get('valueString') or field_data.get('valueNumber') or field_data.get('valueDate') or field_data.get('valueCurrency', {}).get('amount')
			print(f"[DEBUG]   {field_name}: {value}")
	
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
	)


def validate_invoice_data(data: InvoiceData) -> InvoiceData:
	# Cross-check totals when available
	if data.subtotal is not None and data.tax_amount is not None and data.total is not None:
		computed = round((data.subtotal or 0.0) + (data.tax_amount or 0.0), 2)
		if abs(computed - (data.total or 0.0)) <= 0.02:
			return data
		# If mismatch is large, prefer total and keep others as-is; could flag in future
	return data
