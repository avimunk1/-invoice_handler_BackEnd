import httpx
import asyncio
from typing import Optional, Dict, Any
from config import settings


class AzureDIClient:
	def __init__(self, endpoint: Optional[str] = None, api_key: Optional[str] = None, timeout_seconds: Optional[int] = None):
		self.endpoint = (endpoint or settings.azure_di_endpoint).rstrip("/")
		self.api_key = api_key or settings.azure_di_key
		self.timeout = timeout_seconds or settings.timeout_seconds

	async def _poll_operation(self, client: httpx.AsyncClient, operation_url: str) -> Dict[str, Any]:
		# Poll until status is succeeded/failed
		for _ in range(60):  # up to ~60 * 1s = 60s; bound by client timeout per request
			res = await client.get(operation_url, headers={"Ocp-Apim-Subscription-Key": self.api_key})
			res.raise_for_status()
			data = res.json()
			status = data.get("status") or data.get("operationState")
			if status in {"succeeded", "failed", "partiallySucceeded"}:
				return data.get("analyzeResult") or data
			await asyncio.sleep(1)
		raise TimeoutError("Azure DI analyze operation timed out")

	async def _post_analyze(self, model_id: str, content: bytes, content_type: str, max_retries: int = 3) -> Dict[str, Any]:
		headers = {
			"Ocp-Apim-Subscription-Key": self.api_key,
			"Content-Type": content_type,
			"Accept": "application/json",
		}
		url = f"{self.endpoint}/documentintelligence/documentModels/{model_id}:analyze?api-version=2024-11-30"
		
		last_error = None
		for attempt in range(max_retries):
			try:
				async with httpx.AsyncClient(timeout=self.timeout) as client:
					resp = await client.post(url, headers=headers, content=content)
					# Expect 202 with Operation-Location header
					if resp.status_code not in (200, 202):
						# Handle rate limiting with exponential backoff
						if resp.status_code == 429:
							retry_after = int(resp.headers.get("Retry-After", 2 ** attempt))
							print(f"[WARN] Rate limited (429), retrying after {retry_after}s (attempt {attempt + 1}/{max_retries})")
							if attempt < max_retries - 1:
								await asyncio.sleep(retry_after)
								continue
						resp.raise_for_status()
					operation_url = resp.headers.get("Operation-Location") or resp.headers.get("operation-location")
					if not operation_url:
						# Some environments may return body; fallback to JSON if present
						try:
							return resp.json()
						except Exception:
							raise RuntimeError("Azure DI did not return operation-location header")
					return await self._poll_operation(client, operation_url)
			except httpx.HTTPStatusError as e:
				last_error = e
				if e.response.status_code == 429 and attempt < max_retries - 1:
					retry_after = int(e.response.headers.get("Retry-After", 2 ** attempt))
					print(f"[WARN] Rate limited (429), retrying after {retry_after}s (attempt {attempt + 1}/{max_retries})")
					await asyncio.sleep(retry_after)
					continue
				raise
		
		if last_error:
			raise last_error

	async def analyze_read(self, content: bytes, content_type: str) -> Dict[str, Any]:
		return await self._post_analyze("prebuilt-read", content, content_type)

	async def analyze_receipt(self, content: bytes, content_type: str) -> Dict[str, Any]:
		return await self._post_analyze("prebuilt-receipt", content, content_type)

	async def analyze_invoice(self, content: bytes, content_type: str) -> Dict[str, Any]:
		return await self._post_analyze("prebuilt-invoice", content, content_type)
