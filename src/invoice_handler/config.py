from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
	# Azure Document Intelligence
	azure_di_endpoint: str = Field(..., alias="AZURE_DI_ENDPOINT")
	azure_di_key: str = Field(..., alias="AZURE_DI_KEY")

	# OpenAI
	openai_api_key: str = Field(..., alias="OPENAI_API_KEY")

	# AWS/S3
	aws_region: Optional[str] = Field(default=None, alias="AWS_REGION")
	aws_access_key_id: Optional[str] = Field(default=None, alias="AWS_ACCESS_KEY_ID")
	aws_secret_access_key: Optional[str] = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
	s3_bucket: Optional[str] = Field(default=None, alias="S3_BUCKET")
	s3_region: Optional[str] = Field(default=None, alias="S3_REGION")

	# Service behavior
	concurrency_limit: int = Field(default=4, alias="CONCURRENCY_LIMIT")
	timeout_seconds: int = Field(default=90, alias="TIMEOUT_SECONDS")
	classification_threshold: float = Field(default=0.5, alias="CLASSIFICATION_THRESHOLD")
	bulk_size: int = Field(default=5, alias="BULK_SIZE")  # Number of files to process per batch

	# Finance
	vat_rate: float = Field(default=0.18, alias="VAT_RATE")  # 18% default

	# Database (asyncpg expects postgresql:// or postgres://)
	database_url: str = Field(default="postgresql://dev:dev123@localhost:5432/invoice_handler_dev", alias="DATABASE_URL")

	# File storage
	upload_dir: str = Field(default="files/input", alias="UPLOAD_DIR")

	class Config:
		env_file = ".env"
		env_file_encoding = "utf-8"
		case_sensitive = False


settings = Settings()  # load at import; simple for now


