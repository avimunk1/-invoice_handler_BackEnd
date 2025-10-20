from typing import List, Optional
from pydantic import BaseModel, Field


class LineItem(BaseModel):
	description: str
	quantity: Optional[float] = None
	unit_price: Optional[float] = None
	line_total: Optional[float] = None


class InvoiceData(BaseModel):
	file_name: str
	source_path: str
	language: str  # "en" or "he"
	document_type: str  # "invoice", "receipt", "other", or "uncertain"
	supplier_name: Optional[str] = None
	invoice_number: Optional[str] = None
	invoice_date: Optional[str] = None
	currency: Optional[str] = None
	subtotal: Optional[float] = None
	tax_amount: Optional[float] = None
	total: Optional[float] = None
	line_items: Optional[List[LineItem]] = None
	confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class ProcessRequest(BaseModel):
	path: str
	recursive: bool = False
	language_detection: bool = True


class ProcessResponse(BaseModel):
	results: List[InvoiceData]
	errors: List[str] = []
