import json
from typing import Dict, Any, Optional
from openai import AsyncOpenAI
from config import settings


class OpenAIClient:
	def __init__(self):
		self.client = AsyncOpenAI(api_key=settings.openai_api_key)
		self.model = "gpt-4o"  # Cost-effective model, can upgrade to gpt-4o if needed
	
	async def extract_invoice_data(self, text: str, file_name: str) -> Dict[str, Any]:
		"""
		Extract structured invoice data from OCR text using LLM.
		
		Args:
			text: OCR text content from the document
			file_name: Name of the file being processed
		
		Returns:
			Dictionary with extracted invoice fields
		"""
		prompt = self._build_extraction_prompt(text, file_name)
		
		try:
			response = await self.client.chat.completions.create(
				model=self.model,
				messages=[
					{
						"role": "system",
						"content": "You are an expert at extracting structured data from invoice and receipt text. Always return valid JSON."
					},
					{
						"role": "user",
						"content": prompt
					}
				],
				response_format={"type": "json_object"},
				temperature=0.1,  # Low temperature for consistent extraction
			)
			
			result_text = response.choices[0].message.content
			result = json.loads(result_text)
			
			print(f"[DEBUG] LLM extracted data for {file_name}: {json.dumps(result, ensure_ascii=False)[:500]}")
			
			return result
			
		except Exception as e:
			print(f"[ERROR] LLM extraction failed for {file_name}: {type(e).__name__}: {str(e)}")
			# Return empty structure on error
			return {
				"language": "unknown",
				"document_type": "other",
				"supplier_name": None,
				"invoice_number": None,
				"invoice_date": None,
				"currency": None,
				"subtotal": None,
				"tax_amount": None,
				"total": None,
				"line_items": []
			}
	
	def _build_extraction_prompt(self, text: str, file_name: str) -> str:
		"""Build the prompt for invoice data extraction."""
		return f"""Analyze the following invoice/receipt text and extract structured information.

File: {file_name}

Text content:
```
{text}
```

Extract and return a JSON object with these fields:
{{
  "language": "2-letter language code (en, he, etc.)",
  "document_type": "invoice, receipt, or other",
  "supplier_name": "vendor/merchant/supplier name",
  "invoice_number": "invoice or receipt number",
  "invoice_date": "date in YYYY-MM-DD format",
  "currency": "3-letter currency code (USD, ILS, EUR, etc.)",
  "subtotal": numeric value or null,
  "tax_amount": numeric value or null,
  "total": numeric total amount,
  "line_items": [
    {{
      "description": "item description",
      "quantity": numeric or null,
      "unit_price": numeric or null,
      "line_total": numeric or null
    }}
  ]
}}

Important guidelines:
1. Extract amounts as pure numbers (no currency symbols)
2. If a field is not found, use null
3. For dates, convert to ISO format (YYYY-MM-DD)
4. Detect language from the text content
5. Be careful with decimal separators - some locales use comma instead of period
6. For Hebrew text, identify supplier names and numbers carefully
7. Common Hebrew invoice terms: חשבונית (invoice), קבלה (receipt), סכום (amount), מס (tax), ספק (supplier)
8. CRITICAL: The shekel symbol is ₪
   - "₪220.0" means the number 220.0 (not 10220 or 220000)
   - "₪1,234.56" means 1234.56
   - Never merge the currency symbol into the number
   - Extract only the numeric value after the ₪ symbol
9. Examples of correct extraction:
   - Text: "סכום ₪220.0" → total: 220.0
   - Text: "Total $100.50" → total: 100.5
   - Text: "€1,500.00" → total: 1500.0

Return ONLY the JSON object, no additional text."""

