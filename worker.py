import os
import json
import uuid
import logging
import requests
import boto3
from typing import Dict, Any
import assemblyai as aai
import openai

from captioning import ms_to_srt_timestamp, transcript_to_srt
from translation import parse_srt, write_srt, translate_srt
from auto_chapters import get_assembly_transcript, generate_llm_chapters, reconcile_chapters
from callback_service import send_callback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS S3 settings (ensure these env vars are set)
S3_BUCKET = os.getenv('S3_BUCKET')
AWS_REGION = os.getenv('AWS_REGION')

# AssemblyAI & OpenAI init
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
aai.settings.api_key = ASSEMBLYAI_API_KEY
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') or None
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Initialize AWS S3 client
s3_client = boto3.client('s3') if S3_BUCKET else None


def upload_to_s3(local_path: str, s3_key: str) -> str:
    """
    Upload a local file to S3 and return its HTTPS URL.
    """
    if not s3_client:
        raise RuntimeError('S3_BUCKET and AWS credentials must be configured')
    s3_client.upload_file(local_path, S3_BUCKET, s3_key)
    return f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"


def download_media(source_url: str, dest_path: str) -> None:
    """
    Downloads media from a URL to a local path.
    """
    resp = requests.get(source_url, stream=True)
    resp.raise_for_status()
    with open(dest_path, 'wb') as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)


def process_job(job_payload: Dict[str, Any]) -> None:
    job_id = job_payload['job_id']
    media_source = job_payload['file_path']
    callback_url = job_payload['callback_url']
    languages = job_payload.get('preferred_languages', [])
    submitted_at = job_payload.get('submission_time')

    try:
        # 1. Download media if needed
        local_media = media_source
        if media_source.startswith('http'):
            local_media = f"/tmp/{job_id}{os.path.splitext(media_source)[1]}"
            logger.info(f"Downloading media to {local_media}...")
            download_media(media_source, local_media)

        # 2. Captioning
        logger.info("Generating captions via AssemblyAI...")
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(local_media)
        words = transcript.words  # list of {'start','end','text'}
        srt_local = f"/tmp/{job_id}.srt"
        transcript_to_srt(words, srt_local)
        captions_s3_key = f"{job_id}/captions/{job_id}.srt"
        captions_url = upload_to_s3(srt_local, captions_s3_key)

        # 3. Auto-chapterning
        logger.info("Generating auto-chapters via AssemblyAI & LLM...")
        _, assembly_chaps = get_assembly_transcript(local_media)
        llm_chaps = generate_llm_chapters(transcript.text)
        reconciled_chaps = reconcile_chapters(assembly_chaps, llm_chaps)
        chap_local = f"/tmp/{job_id}_chapters.json"
        with open(chap_local, 'w', encoding='utf-8') as f:
            json.dump(reconciled_chaps, f)
        chapters_s3_key = f"{job_id}/chapters/{job_id}_reconciled.json"
        chapters_url = upload_to_s3(chap_local, chapters_s3_key)

        # 4. Translation
        logger.info("Translating captions...")
        entries = parse_srt(srt_local)
        translation_urls = {}
        for code in languages:
            txt_entries = translate_srt(entries, code)
            tr_local = f"/tmp/{job_id}_{code}.srt"
            write_srt(txt_entries, tr_local)
            tr_s3_key = f"{job_id}/translations/{job_id}_{code}.srt"
            translation_urls[code] = upload_to_s3(tr_local, tr_s3_key)

        # 5. Callback
        results = {
            'submitted_at': submitted_at,
            'captions': {'source': captions_url},
            'chapters': {'reconciled': chapters_url},
            'translations': translation_urls
        }
        send_callback(job_id, callback_url, results, status='completed')
        logger.info(f"Job {job_id} completed successfully.")

    except Exception as e:
        logger.exception(f"Error processing job {job_id}")
        send_callback(job_id, callback_url, {}, status='failed', error_message=str(e))
        raise


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Worker for MAP video processing pipeline')
    parser.add_argument('-j', '--job-payload', required=True,
                        help='Path to JSON file containing the job payload')
    args = parser.parse_args()
    with open(args.job_payload, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    process_job(payload)


if __name__ == '__main__':
    main()