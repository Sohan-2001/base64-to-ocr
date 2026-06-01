import os
from vercel import blob

# The vercel SDK automatically checks os.environ["BLOB_READ_WRITE_TOKEN"]
def upload_binary_to_vercel_blob(file_bytes: bytes, filename: str) -> str:
    """
    Uploads raw image bytes directly to Vercel Blob in-memory.
    Returns the secure public URL of the uploaded asset.
    """
    response = blob.put(
        pathname=filename,
        body=file_bytes,
        access="public"  # 'public' allows the worker to access it via CDN URL
    )
    
    # The response object contains the generated public URL (.url)
    return response.url