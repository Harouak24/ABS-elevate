import os
import time
import requests
import json
from datetime import datetime
from typing import List, Dict

# Optional: Use OpenAI to simulate in-house LLM—replace with your own LLM client
import openai

env_assembly_key = os.getenv("ASSEMBLYAI_API_KEY")
env_openai_key = os.getenv("OPENAI_API_KEY")
if not env_assembly_key:
    raise EnvironmentError("Please set the ASSEMBLYAI_API_KEY environment variable.")
openai.api_key = env_openai_key or ""

# AssemblyAI endpoints
ASSEMBLYAI_UPLOAD_URL = "https://api.assemblyai.com/v2/upload"
ASSEMBLYAI_TRANSCRIPT_URL = "https://api.assemblyai.com/v2/transcript"
HEADERS = {"authorization": env_assembly_key}

MAX_POLL_INTERVAL = 5  # seconds between polls


def upload_file_to_assemblyai(file_path: str) -> str:
    """
    Uploads a local file to AssemblyAI and returns the upload_url for processing.
    """
    with open(file_path, "rb") as f:
        response = requests.post(ASSEMBLYAI_UPLOAD_URL, headers=HEADERS, data=f)
    response.raise_for_status()
    return response.json()["upload_url"]


def request_assemblyai_chapters(audio_url: str) -> str:
    """
    Requests a transcription with auto chapters enabled and returns the transcript_id.
    """
    payload = {
        "audio_url": audio_url,
        "auto_chapters": True
    }
    response = requests.post(ASSEMBLYAI_TRANSCRIPT_URL, json=payload, headers=HEADERS)
    response.raise_for_status()
    return response.json()["id"]


def poll_assemblyai(transcript_id: str) -> Dict:
    """
    Polls the AssemblyAI transcript endpoint until status is 'completed'.
    Returns the full JSON response including 'chapters'.
    """
    url = f"{ASSEMBLYAI_TRANSCRIPT_URL}/{transcript_id}"
    while True:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        status = data.get("status")
        if status == "completed":
            return data
        if status == "error":
            raise RuntimeError(f"AssemblyAI processing error: {data.get('error')}")
        time.sleep(MAX_POLL_INTERVAL)


def generate_llm_chapters(transcript_text: str) -> List[Dict]:
    """
    Uses an LLM to generate chapter markers.
    Replace this with your in-house LLM client as needed.
    Prompts the model to return JSON list: [{"start": float, "end": float, "title": str}, ...]
    """
    prompt = (
        "You are an assistant that generates chapter markers for educational videos. "
        "Given the transcript below, suggest chapter start and end time in seconds, and a short title. "
        "Return strictly a JSON list of objects with keys 'start', 'end', and 'title'.\n" + transcript_text
    )
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You generate chapters from transcript."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )
    content = response.choices[0].message.content.strip()
    # Parse JSON
    return json.loads(content)


def reconcile_chapters(
    assembly: List[Dict], llm: List[Dict]
) -> List[Dict]:
    """
    Reconcile two chapter lists. Default to assembly results but merge LLM entries
    that don't overlap significantly.
    """
    reconciled = []
    ai_idx = 0
    for asm in assembly:
        # Add AssemblyAI chapter
        reconciled.append(asm)
        # Check if any LLM chapter starts within this asm segment
        for marker in llm:
            if asm['start'] <= marker['start'] < asm['end']:
                # decide by shorter segment or more descriptive title
                if len(marker['title']) > len(asm['headline'] if 'headline' in asm else ''):
                    reconciled[-1]['title'] = marker['title']  # override title
    # Optionally append LLM-only chapters that don't overlap
    for marker in llm:
        overlap = any(
            abs(marker['start'] - asm['start']) < 1 for asm in assembly
        )
        if not overlap:
            reconciled.append({
                'start': marker['start'],
                'end': marker['end'],
                'headline': marker['title']
            })
    # Sort by start time
    reconciled.sort(key=lambda x: x['start'])
    return reconciled


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description="Auto-chapterning via AssemblyAI and LLM reconciliation.")
    parser.add_argument('--file', '-f', required=True, help='Path to local video/audio file')
    parser.add_argument('--output', '-o', required=True, help='Base path for output JSON files')
    args = parser.parse_args()

    # Step 1: Upload and request chapters from AssemblyAI
    print("Uploading file...")
    audio_url = upload_file_to_assemblyai(args.file)
    print(f"Audio URL: {audio_url}")

    print("Requesting chapters from AssemblyAI...")
    transcript_id = request_assemblyai_chapters(audio_url)
    print(f"Transcript ID: {transcript_id}")

    print("Polling AssemblyAI for chapters...")
    result = poll_assemblyai(transcript_id)
    assembly_chapters = result.get('chapters', [])
    print(f"Received {len(assembly_chapters)} chapters from AssemblyAI.")

    # Write AssemblyAI chapters
    asm_path = f"{args.output}_assembly.json"
    with open(asm_path, 'w', encoding='utf-8') as f:
        json.dump(assembly_chapters, f, indent=2)
    print(f"AssemblyAI chapters saved to {asm_path}")

    # Step 2: Generate LLM chapters
    print("Fetching transcript text for LLM chapterning...")
    transcript_text = result.get('text', '')
    print("Generating chapters via LLM...")
    llm_chapters = generate_llm_chapters(transcript_text)
    llm_path = f"{args.output}_llm.json"
    with open(llm_path, 'w', encoding='utf-8') as f:
        json.dump(llm_chapters, f, indent=2)
    print(f"LLM chapters saved to {llm_path}")

    # Step 3: Reconcile
    print("Reconciling chapter lists...")
    reconciled = reconcile_chapters(assembly_chapters, llm_chapters)
    rec_path = f"{args.output}_reconciled.json"
    with open(rec_path, 'w', encoding='utf-8') as f:
        json.dump(reconciled, f, indent=2)
    print(f"Reconciled chapters saved to {rec_path}")