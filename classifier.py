import re
from typing import Literal, Tuple

DocType = Literal["invoice", "receipt", "other", "uncertain"]

HEBREW_CHARS = re.compile(r"[\u0590-\u05FF]")

# simple keyword sets (en/he)
RECEIPT_KEYWORDS = [
	"receipt",
	"sales receipt",
	"קבלה",
]
INVOICE_KEYWORDS = [
	"invoice",
	"tax invoice",
	"חשבונית",
	"חשבונית מס",
	"חשבונית מס קבלה",
	"חשבון"
]


def detect_language(text: str) -> str:
	if HEBREW_CHARS.search(text or ""):
		return "he"
	return "en"


def classify_text(text: str, threshold: float = 0.5) -> Tuple[DocType, float]:
	if not text:
		return ("uncertain", 0.0)
	lower = text.lower()
	receipt_hits = sum(1 for k in RECEIPT_KEYWORDS if k in lower)
	invoice_hits = sum(1 for k in INVOICE_KEYWORDS if k in lower)
	total = receipt_hits + invoice_hits
	if total == 0:
		# look for generic purchase signals
		if re.search(r"total|subtotal|tax|amount|סך|סה\"כ|מע\"מ", lower):
			return ("uncertain", 0.4)
		return ("other", 0.3)
	if receipt_hits > invoice_hits and receipt_hits >= 1:
		score = min(1.0, 0.4 + 0.2 * receipt_hits)
		return ("receipt", score)
	if invoice_hits > receipt_hits and invoice_hits >= 1:
		score = min(1.0, 0.4 + 0.2 * invoice_hits)
		return ("invoice", score)
	# tie or too close
	return ("uncertain", 0.45)
