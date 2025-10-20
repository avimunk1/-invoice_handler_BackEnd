from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from models import ProcessRequest, ProcessResponse
from pipeline import process_path

app = FastAPI(title="Invoice Handler", default_response_class=ORJSONResponse)


@app.get("/healthz")
async def healthz():
	return {"status": "ok"}


@app.post("/process", response_model=ProcessResponse)
async def process(req: ProcessRequest):
	results = await process_path(req.path, req.recursive, req.language_detection)
	return ProcessResponse(results=results, errors=[])
