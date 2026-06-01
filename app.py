import os
import hashlib
import base64
from flask import Flask, request, jsonify
from redis import Redis
from rq import Queue
from storage_utils import upload_binary_to_vercel_blob

app = Flask(__name__)

# Enforce strict payload limit at the HTTP layer
app.config['MAX_CONTENT_LENGTH'] = 6 * 1024 * 1024 

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
redis_conn = Redis.from_url(REDIS_URL)
task_queue = Queue("ocr_tasks", connection=redis_conn)

@app.route('/v1/ocr', methods=['POST'])
def enqueue_ocr():
    data = request.get_json(silent=True)
    if not data or 'image' not in data:
        return jsonify({"error": "Invalid payload structure. Missing 'image' key."}), 400
    
    base64_str = data['image']
    if "," in base64_str:
        base64_str = base64_str.split(",")[-1]

    try:
        image_bytes = base64.b64decode(base64_str)
        
        # Enforce exact 4 MB raw binary execution threshold
        if len(image_bytes) > 4 * 1024 * 1024:
            return jsonify({"error": "Image binary size exceeds the maximum 4 MB limit."}), 400
        
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        
        # Cache Layer Look-up (De-duplication)
        cached_result = redis_conn.get(f"ocr:cache:{image_hash}")
        if cached_result:
            return jsonify({
                "status": "completed", 
                "source": "cache", 
                "text": cached_result.decode('utf-8')
            }), 200

        # Claim-Check Pattern: Stream file to Vercel Blob and capture CDN URL
        filename = f"ocr_payloads/{image_hash}.jpg"
        blob_url = upload_binary_to_vercel_blob(image_bytes, filename)
        
        # Send the lightweight URL pointer to the background workers
        job = task_queue.enqueue("tasks.execute_ocr_pipeline", blob_url, image_hash)
        
        return jsonify({
            "status": "queued",
            "task_id": job.get_id(),
            "check_status_url": f"/v1/ocr/status/{job.get_id()}"
        }), 202

    except Exception as e:
        return jsonify({"error": "Failed to safely ingest payload stream."}), 500

@app.route('/v1/ocr/status/<task_id>', methods=['GET'])
def get_task_status(task_id):
    job = task_queue.fetch_job(task_id)
    if not job:
        return jsonify({"error": "Requested tracking token does not exist."}), 404
        
    if job.is_finished:
        return jsonify({"status": "success", "text": job.result}), 200
    elif job.is_failed:
        return jsonify({"status": "failed", "error": "Internal processor crash during execution."}), 500
        
    return jsonify({"status": job.get_status()}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)