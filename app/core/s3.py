# 파일명 util + S3 클라이언트
import boto3

from .config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_S3_BUCKET_NAME,
    AWS_REGION,
)

# 파일명에 쓸 수 있도록 문자열 처리
def sanitize_filename(name: str, default: str = "flow") -> str:
    if not name:
        return default
    safe = "".join(
        ch for ch in name
        if ch.isalnum() or ch in (" ", "-", "_", ".", "·", "ㆍ")
    )
    safe = safe.strip().replace(" ", "_")
    return (safe or default)[:120]

# S3 클라이언트
s3 = boto3.client(
    "s3",
    region_name=AWS_REGION,
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
)

BUCKET_NAME = AWS_S3_BUCKET_NAME