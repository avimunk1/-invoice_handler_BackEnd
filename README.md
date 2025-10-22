# Invoice Handler Backend

FastAPI backend for invoice/receipt processing using Azure Document Intelligence.

## Features

- Process invoices and receipts from local files or S3
- Automatic document classification (invoice vs receipt)
- Multi-language support (English and Hebrew)
- Extract structured data: supplier, amounts, dates, line items
- RESTful API with automatic documentation
- S3 presigned URL generation for secure file uploads

## Setup

### Prerequisites

- Python 3.10 or higher
- Azure Document Intelligence account
- (Optional) AWS S3 bucket for file storage

### Installation

Using `uv` (recommended):

```bash
cd backend
uv sync
```

Or using pip:

```bash
cd backend
pip install -r requirements.txt
```

### Configuration

Create a `.env` file with required credentials:

```env
# Azure Document Intelligence (REQUIRED)
AZURE_DI_ENDPOINT=https://your-instance.cognitiveservices.azure.com
AZURE_DI_KEY=your-api-key-here

# AWS S3 (Optional - for web uploads)
S3_BUCKET=invoice-uploads
S3_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Optional settings
CONCURRENCY_LIMIT=4
TIMEOUT_SECONDS=90
CLASSIFICATION_THRESHOLD=0.5
```

### Running

Start the development server:

```bash
./backend_Start.sh
```

Or manually:

```bash
cd backend
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- **API**: http://localhost:8000
- **Docs**: http://localhost:8000/docs (Swagger UI)
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### Health Check

```
GET /healthz
```

Returns service status.

### Process Invoices

```
POST /process
Content-Type: application/json

{
  "path": "file:///path/to/invoices",  // or "s3://bucket/prefix"
  "recursive": false,
  "language_detection": true
}
```

Returns structured invoice data.

### Get S3 Presigned URL

```
POST /upload/presigned-url?filename=invoice.pdf
```

Returns presigned POST URL for S3 upload.

## Supported File Types

- PDF documents
- Images (JPG, PNG)
- Text files (.txt)

## Architecture

### Pipeline Flow

1. **File Discovery**: Locate files in local filesystem or S3
2. **Document Analysis**: Azure DI extracts text and structured data
3. **Classification**: Identify document type (invoice/receipt/other)
4. **Language Detection**: Detect Hebrew or English
5. **Data Mapping**: Extract fields into standardized format
6. **Validation**: Cross-check totals and confidence scores

### Key Modules

- `main.py` - FastAPI application and routes
- `pipeline.py` - Document processing pipeline
- `azure_di.py` - Azure Document Intelligence client
- `classifier.py` - Document type classification
- `mapping.py` - Extract and normalize invoice fields
- `discovery.py` - File system and S3 discovery
- `models.py` - Pydantic data models
- `config.py` - Configuration management

## Rate Limiting

Azure Document Intelligence has rate limits:
- **Free tier**: 20 requests/minute
- **Paid tier**: Varies by subscription

The backend includes automatic retry with exponential backoff for 429 errors.

## Development

### Testing

```bash
# Process a test file
curl -X POST http://localhost:8000/process \
  -H "Content-Type: application/json" \
  -d '{
    "path": "/Users/username/invoices",
    "recursive": false,
    "language_detection": true
  }'
```

### Adding New Document Types

1. Add keywords to `classifier.py`
2. Create analyzer method in `azure_di.py`
3. Add mapping function in `mapping.py`
4. Update `pipeline.py` to route to new analyzer

## Future Enhancements

- [ ] Database integration for storing results
- [ ] Webhook support for async processing
- [ ] Custom document templates
- [ ] OCR quality scoring
- [ ] Duplicate detection

