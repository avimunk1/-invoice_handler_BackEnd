"""S3 client factory with credential support."""
import boto3
from typing import Optional
from .config import settings


def get_s3_client(region: Optional[str] = None):
    """
    Create S3 client with optional explicit credentials.
    
    If AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are set in environment/settings,
    they will be used. Otherwise, falls back to boto3's default credential chain
    (AWS CLI config, IAM role, etc.).
    
    Args:
        region: AWS region, defaults to settings.s3_region or settings.aws_region
    
    Returns:
        boto3 S3 client
    """
    client_kwargs = {
        'service_name': 's3',
        'region_name': region or settings.s3_region or settings.aws_region or 'us-east-1'
    }
    
    # Only pass credentials if explicitly set (otherwise use default credential chain)
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        client_kwargs['aws_access_key_id'] = settings.aws_access_key_id
        client_kwargs['aws_secret_access_key'] = settings.aws_secret_access_key
    
    return boto3.client(**client_kwargs)


