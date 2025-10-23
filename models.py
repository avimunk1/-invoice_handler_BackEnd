from typing import List, Optional, Dict
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
	polygon: List[List[float]]  # [[x1,y1], [x2,y2], [x3,y3], [x4,y4]] normalized coordinates (0-1)
	page_number: int


class LineItem(BaseModel):
	description: str
	quantity: Optional[float] = None
	unit_price: Optional[float] = None
	line_total: Optional[float] = None


class InvoiceData(BaseModel):
	file_name: str
	source_path: str
	file_url: Optional[str] = None  # URL to view/download the file
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
	bounding_boxes: Optional[Dict[str, BoundingBox]] = None  # Field name -> bounding box
	page_count: Optional[int] = None  # Total number of pages in document
	field_confidence: Optional[Dict[str, float]] = None  # Field name -> confidence score (0-1)


class ProcessRequest(BaseModel):
	path: str
	recursive: bool = False
	language_detection: bool = True
	starting_point: int = 0  # Index to start processing from (0-based)


class ProcessResponse(BaseModel):
	results: List[InvoiceData]
	errors: List[str] = []
	total_files: int = 0  # Total number of files discovered
	files_handled: int = 0  # Number of files processed in this batch
