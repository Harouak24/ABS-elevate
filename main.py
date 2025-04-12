import os
import uuid
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel, HttpUrl
import redis
from rq import Queue
import worker  # Import the worker module with the processing function

# Load secure token from environment variable or configuration.
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "YOUR_SECURE_TOKEN")

# Setup Redis connection and create an RQ queue.
redis_conn = redis.Redis(host="localhost", port=6379, db=0)
job_queue = Queue(connection=redis_conn)

app = FastAPI(title="ABS Elevate Video Processing API (RQ)")

class VideoSubmission(BaseModel):
    video_url: HttpUrl
    callback_url: HttpUrl

@app.post("/submit_video")
async def submit_video(submission: VideoSubmission, authorization: str = Header(...)):
    """
    Submit a video for processing. Request must include a Bearer access token.
    JSON payload should contain a video_url and a callback_url.
    """
    if authorization != f"Bearer {ACCESS_TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Generate a unique job ID.
    job_id = str(uuid.uuid4())

    # Enqueue the processing task using RQ.
    job = job_queue.enqueue(worker.process_video, submission.video_url, submission.callback_url, job_id)

    return {
        "job_id": job_id,
        "rq_job_id": job.get_id(),
        "status": "Processing started"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)