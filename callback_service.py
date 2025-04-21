import os
import time
import json
import requests
from datetime import datetime
from typing import Dict, Optional


def send_callback(
    job_id: str,
    callback_url: str,
    results: Dict[str, Dict[str, str]],
    status: str = "completed",
    error_message: Optional[str] = None,
    max_retries: int = 3,
    backoff_factor: int = 2
) -> bool:
    """
    Sends a POST request to the callback URL with job metadata and result URLs.

    Parameters:
    - job_id: Unique identifier of the processing job.
    - callback_url: The endpoint to notify when processing is done.
    - results: A dict containing result categories (captions, translations, chapters) and their URLs, e.g.: 
        {
            "captions": {"en": "https://.../captions_en.srt", ...},
            "translations": {"fr": "https://.../captions_fr.srt", ...},
            "chapters": {"reconciled": "https://.../video_chapters_reconciled.json"}
        }
    - status: 'completed' or 'failed'.
    - error_message: Optional error description if status is 'failed'.
    - max_retries: Number of retry attempts on failure.
    - backoff_factor: Multiplier for exponential backoff (in seconds).

    Returns:
    - True if notification was successful; False otherwise.
    """
    payload = {
        "job_id": job_id,
        "status": status,
        "submitted_at": results.get("submitted_at", datetime.utcnow().isoformat() + "Z"),
        "completed_at": datetime.utcnow().isoformat() + "Z",
        "results": results
    }
    if status.lower() == "failed" and error_message:
        payload["error_message"] = error_message

    headers = {"Content-Type": "application/json"}
    attempt = 0

    while attempt < max_retries:
        try:
            response = requests.post(callback_url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()
            print(f"Callback succeeded (status {response.status_code}).")
            return True
        except requests.RequestException as e:
            wait = backoff_factor ** attempt
            print(f"Callback attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)
            attempt += 1

    print("All callback attempts failed.")
    return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Notify client via callback with job processing results.")
    parser.add_argument('-j', '--job-id', required=True, help='Job identifier')
    parser.add_argument('-u', '--callback-url', required=True, help='Callback endpoint URL')
    parser.add_argument('-r', '--results-file', required=True,
                        help='Path to a JSON file containing the results dict')
    parser.add_argument('-s', '--status', default='completed', choices=['completed', 'failed'],
                        help='Job status')
    parser.add_argument('-e', '--error-message', help='Error message if status is failed')
    args = parser.parse_args()

    # Load results dict from file
    with open(args.results_file, 'r', encoding='utf-8') as rf:
        results = json.load(rf)

    success = send_callback(
        job_id=args.job_id,
        callback_url=args.callback_url,
        results=results,
        status=args.status,
        error_message=args.error_message
    )

    exit(0 if success else 1)