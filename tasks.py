import io
import os
import logging
import requests
from redis import Redis
from PIL import Image
import pytesseract

logger = logging.getLogger("WorkerCore")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_client = Redis.from_url(REDIS_URL)

def execute_ocr_pipeline(blob_url: str, image_hash: str) -> str:
    """Executed asynchronously by background worker nodes."""
    logger.info(f"Worker pulled task. Downloading from Vercel CDN: {blob_url}")
    
    try:
        # 1. Download file directly out of Vercel CDN into RAM
        response = requests.get(blob_url, timeout=10)
        response.raise_for_status()
        image_bytes = response.content
        
        # 2. Process image through the Tesseract pipeline
        image = Image.open(io.BytesIO(image_bytes))
        extracted_text = pytesseract.image_to_string(image).strip()
        
        # 3. Save results to Cache Layer with a 24-Hour TTL
        redis_client.setex(
            name=f"ocr:cache:{image_hash}",
            time=86400,
            value=extracted_text
        )
        
        logger.info(f"Successfully processed and cached result for hash: {image_hash}")
        return extracted_text

    except Exception as e:
        logger.error(f"Execution pipeline error on asset {blob_url}: {str(e)}")
        raise e