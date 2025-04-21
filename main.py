from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
import shutil
import uuid
import os
from datetime import datetime

from config import ACCESS_TOKEN
from job_queue import enqueue_job  # Import the enqueue function

# Initialize FastAPI app
app = FastAPI(title="MAP Project API Gateway with Job Queue Integration")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------
# Middleware / Dependencies
# ------------------------------

def verify_access_token(authorization: Optional[str] = Header(None)):
    """
    Dependency to verify the request has a valid access token in the header "Authorization".
    The expected format: "Bearer <token>".
    """
    if authorization is None:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    try:
        scheme, token = authorization.split()
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid authorization format")
    
    if scheme.lower() != "bearer" or token != ACCESS_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing access token")
    return token


# ------------------------------
# Pydantic Models for Metadata
# ------------------------------

class VideoMetadata(BaseModel):
    video_url: Optional[HttpUrl] = None  # Optional URL if a file is not uploaded
    preferred_languages: List[str] = ["en"]  # Defaults to English; valid entries: en, fr, es, ar.
    callback_url: Optional[HttpUrl] = None  # Callback URL for processing completion notification

    class Config:
        schema_extra = {
            "example": {
                "video_url": "https://example.com/path/to/video.mp4",
                "preferred_languages": ["en", "fr"],
                "callback_url": "https://yourdomain.com/callback"
            }
        }


# ------------------------------
# Utility Function: Save Uploaded File
# ------------------------------

def save_upload_file(upload_file: UploadFile, destination: str) -> None:
    """
    Saves the uploaded file to the specified destination.
    Consider integrating AWS S3 for production storage.
    """
    with open(destination, "wb") as buffer:
        shutil.copyfileobj(upload_file.file, buffer)


# ------------------------------
# API Endpoints
# ------------------------------

@app.post("/api/videos", dependencies=[Depends(verify_access_token)])
async def upload_video(
    # Accept file upload (optional)
    video: Optional[UploadFile] = File(None),
    # Accept metadata as form data fields
    video_url: Optional[str] = Form(None),
    preferred_languages: List[str] = Form(...),
    callback_url: str = Form(...),
):
    """
    Endpoint to accept video submissions.
    
    Either a video file upload (using "video") or a video URL (using "video_url") must be provided.
    Also accepts a list of preferred languages and a callback URL.
    
    Returns a JSON response with the job identifier.
    """
    if video is None and video_url is None:
        raise HTTPException(
            status_code=400,
            detail="Either a video file or a video URL must be provided"
        )

    job_id = str(uuid.uuid4())

    # Set up local temporary storage
    temp_dir = "temp_uploads"
    os.makedirs(temp_dir, exist_ok=True)

    saved_file_path = None

    if video is not None:
        file_extension = os.path.splitext(video.filename)[1]
        saved_file_path = os.path.join(temp_dir, f"{job_id}{file_extension}")
        try:
            save_upload_file(video, saved_file_path)
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Failed to save uploaded file: {str(e)}"
            )
    else:
        saved_file_path = video_url  # For video URLs, you may optionally download the file if needed.

    # Create job payload with metadata
    job_payload = {
        "job_id": job_id,
        "file_path": saved_file_path,
        "preferred_languages": preferred_languages,
        "callback_url": callback_url,
        "submission_time": datetime.utcnow().isoformat() + "Z"
    }

    try:
        enqueue_job(job_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to enqueue job: {str(e)}")

    return {"job_id": job_id, "message": "Video submission accepted. Processing started."}