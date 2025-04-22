import os
import uuid
from datetime import datetime
from fastapi import (
    FastAPI, File, UploadFile, HTTPException, Header,
    BackgroundTasks, Depends, Body
)
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl, validator
from typing import List, Optional
from config import (
    ACCESS_TOKEN,
    TEMP_UPLOAD_DIR,
    ALLOWED_LANGUAGES,
)
from job_queue import enqueue_job

app = FastAPI(title="MAP Video Ingestion")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Dependencies & Auth --- #

def verify_access_token(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(401, "Authorization header missing")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or token != ACCESS_TOKEN:
        raise HTTPException(403, "Invalid or missing access token")


# --- Request Model --- #

class VideoRequest(BaseModel):
    video_url: Optional[HttpUrl] = None
    preferred_languages: List[str]
    callback_url: HttpUrl

    @validator("preferred_languages", each_item=True)
    def check_language(cls, v):
        if v not in ALLOWED_LANGUAGES:
            raise ValueError(f"Unsupported language: {v}")
        return v

    @validator("video_url", always=True)
    def require_file_or_url(cls, v, values):
        # We require either a URL or a File upload; File handled separately
        if not v and not values.get("_file_upload_included"):
            raise ValueError("Either video_url or a file upload must be provided")
        return v


# --- Endpoint --- #

@app.post(
    "/api/videos",
    dependencies=[Depends(verify_access_token)],
    status_code=202,
    summary="Submit a video for captioning, translation, and auto-chapterning"
)
async def upload_video(
    background_tasks: BackgroundTasks,
    payload: VideoRequest = Body(...),
    video: Optional[UploadFile] = File(None),
):
    """
    Submit either a direct file upload or a public video URL, specify target
    languages, and a callback URL. Returns a job_id immediately.
    """
    # Ensure temp dir exists
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

    job_id = str(uuid.uuid4())
    submission_ts = datetime.utcnow().isoformat() + "Z"

    # Handle file upload vs URL
    if video:
        ext = os.path.splitext(video.filename)[1]
        saved_path = os.path.join(TEMP_UPLOAD_DIR, f"{job_id}{ext}")
        try:
            with open(saved_path, "wb") as buf:
                import shutil
                shutil.copyfileobj(video.file, buf)
        except Exception as e:
            raise HTTPException(500, f"Failed to save upload: {e}")
    else:
        saved_path = str(payload.video_url)

    # Build job payload
    job = {
        "job_id": job_id,
        "file_path": saved_path,
        "preferred_languages": payload.preferred_languages,
        "callback_url": str(payload.callback_url),
        "submission_time": submission_ts,
    }

    # Enqueue in background
    background_tasks.add_task(enqueue_job, job)

    return {
        "job_id": job_id,
        "message": "Accepted: processing will begin shortly."
    }