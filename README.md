# 🎥 ABS Elevate - Video Processing & Metadata Service

This is a high-reliability microservice pipeline developed for **UM6P Africa Business School’s e-learning platform** (ABS Elevate), designed to automate:

- 🎙️ Captioning (via AssemblyAI)
- 🌐 Translation (to English, French, Spanish, Arabic using LLMs)
- 📍 Auto-Chapterning (AssemblyAI + in-house LLM)
- 📬 Notification via callback once processing completes

## 📌 Project Metadata

- **Client**: UM6P Africa Business School (ABS Elevate)
- **Project ID**: MAP
- **Priority**: High
- **Deadline**: April 3rd, 2025

---

## 🛠️ Features

- REST API for secure video submission
- Scalable, fault-tolerant job queue with RabbitMQ
- Caption generation in `.srt` format
- Timestamp-preserving multilingual translation
- Auto-chapter marker generation and reconciliation
- Callback notification with structured job metadata
- Extensible and container-ready microservice architecture

---

## 📦 Project Structure

├── main.py # FastAPI entrypoint: POST /api/videos 
├── config.py # Central config/env manager 
├── job_queue.py # RabbitMQ producer setup 
├── captioning.py # AssemblyAI caption pipeline 
├── translation.py # LLM-powered multilingual translation 
├── auto_chapters.py # AssemblyAI + LLM chapter generator 
├── callback_service.py # Callback notifier with retry logic 
├── requirements.txt # Dependencies 
├── README.md # You're here

---

## 🚀 Quickstart

### 1. 📋 Prerequisites

- Python 3.9+
- RabbitMQ (local or cloud instance)
- API Keys:
  - `ASSEMBLYAI_API_KEY`
  - `OPENAI_API_KEY`

### 2. 🔧 Environment Setup

# Clone repo
git clone 
cd ABS-elevate

# Create virtual environment
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Export environment variables
export ACCESS_TOKEN="your_secure_token_here"
export RABBITMQ_HOST="localhost"
export RABBITMQ_USER="guest"
export RABBITMQ_PASSWORD="guest"
export ASSEMBLYAI_API_KEY="your_key"
export OPENAI_API_KEY="your_key"

### 3. ▶️ Run API Server

uvicorn main:app --reload
# API will be accessible at:
http://localhost:8000/api/videos

### 4. 🧪 Example Submission (via curl)

# File Upload
curl -X POST http://localhost:8000/api/videos \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "video=@/path/to/video.mp4" \
  -F "preferred_languages=fr,es" \
  -F "callback_url=https://client.app/callback"

# URL Reference
curl -X POST http://localhost:8000/api/videos \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "video_url=https://domain.com/video.mp4" \
  -F "preferred_languages=en,ar" \
  -F "callback_url=https://client.app/callback"

### 🔄 Background Workers (To Be Implemented)

# Each worker will:

Consume jobs from RabbitMQ
Run captioning.py, translation.py, and auto_chapters.py
Upload output files (e.g., to AWS S3 or similar)
Call callback_service.py with job status and results
📤 Callback Payload Example

{
  "job_id": "MAP_abc123",
  "status": "completed",
  "submitted_at": "2025-04-01T12:00:00Z",
  "completed_at": "2025-04-01T12:20:00Z",
  "results": {
    "captions": {
      "en": "https://s3.aws.com/abs/MAP_abc123/en.srt",
      "fr": "https://s3.aws.com/abs/MAP_abc123/fr.srt"
    },
    "translations": {
      "es": "https://s3.aws.com/abs/MAP_abc123/es.srt",
      "ar": "https://s3.aws.com/abs/MAP_abc123/ar.srt"
    },
    "chapters": {
      "reconciled": "https://s3.aws.com/abs/MAP_abc123/chapters.json"
    }
  }
}

### ⚙️ Scripts Reference

captioning.py: Generates .srt from video using AssemblyAI
translation.py: Translates .srt using GPT-4 while preserving timestamps
auto_chapters.py: Creates chapter markers via AssemblyAI & LLM, reconciles
callback_service.py: Sends job result to client’s callback URL

### 🔐 Security

All endpoints require Bearer Token (ACCESS_TOKEN) via Authorization header.
Workers and callback services must be internal or authenticated.