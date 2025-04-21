import os
import time
import requests
from datetime import timedelta

# Configuration
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY", "your_assemblyai_api_key")
UPLOAD_ENDPOINT = "https://api.assemblyai.com/v2/upload"
TRANSCRIPT_ENDPOINT = "https://api.assemblyai.com/v2/transcript"

# Caption settings
MAX_CAPTION_DURATION_MS = 5000  # Maximum duration per caption block
MAX_WORDS_PER_CAPTION = 15     # Maximum number of words per caption block


class AssemblyAIClient:
    def __init__(self, api_key: str = ASSEMBLYAI_API_KEY):
        if not api_key or api_key == "your_assemblyai_api_key":
            raise ValueError("Please set your ASSEMBLYAI_API_KEY environment variable.")
        self.headers = {"authorization": api_key}

    def upload_audio(self, file_path: str) -> str:
        """
        Uploads a local audio/video file to AssemblyAI and returns the audio_url.
        """
        with open(file_path, 'rb') as f:
            response = requests.post(
                UPLOAD_ENDPOINT,
                headers=self.headers,
                data=f
            )
        response.raise_for_status()
        return response.json()['upload_url']

    def request_transcription(self, audio_url: str) -> str:
        """
        Sends a transcription request and returns the transcript ID.
        """
        json_payload = {
            "audio_url": audio_url,
            "format_text": True,
            "word_boost": [],
            "auto_highlights": False
        }
        response = requests.post(
            TRANSCRIPT_ENDPOINT,
            json=json_payload,
            headers=self.headers
        )
        response.raise_for_status()
        return response.json()['id']

    def poll_transcription(self, transcript_id: str, interval: int = 5) -> dict:
        """
        Polls the transcription status until completion and returns the full transcript JSON.
        """
        polling_url = f"{TRANSCRIPT_ENDPOINT}/{transcript_id}"
        while True:
            response = requests.get(polling_url, headers=self.headers)
            response.raise_for_status()
            result = response.json()
            status = result.get('status')
            if status == 'completed':
                return result
            if status == 'error':
                raise RuntimeError(f"Transcription failed: {result.get('error')}")
            time.sleep(interval)


def ms_to_srt_timestamp(ms: int) -> str:
    """
    Converts milliseconds to SRT timestamp format: HH:MM:SS,mmm
    """
    td = timedelta(milliseconds=ms)
    hours, remainder = divmod(td.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    milliseconds = td.microseconds // 1000
    return f"{td.hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def transcript_to_srt(transcript_json: dict, output_path: str):
    """
    Converts AssemblyAI transcript JSON into .srt file at output_path.
    """
    words = transcript_json.get('words')
    if not words:
        raise ValueError("Transcript JSON does not contain word-level timestamps.")

    srt_entries = []
    current_block = []
    block_start = None

    def flush_block():
        nonlocal current_block, block_start
        if not current_block:
            return
        block_end = current_block[-1]['end']
        text = ' '.join([w['text'] for w in current_block])
        srt_entries.append((block_start, block_end, text))
        current_block = []

    for word in words:
        start_ms = int(word['start'])
        end_ms = int(word['end'])

        if block_start is None:
            # Initialize block
            block_start = start_ms
            current_block.append(word)
            continue

        # Determine if adding this word exceeds duration or word count
        duration = end_ms - block_start
        if duration > MAX_CAPTION_DURATION_MS or len(current_block) >= MAX_WORDS_PER_CAPTION:
            flush_block()
            block_start = start_ms
        current_block.append(word)

    # Flush any remaining words
    flush_block()

    # Write to .srt file
    with open(output_path, 'w', encoding='utf-8') as f:
        for idx, (start, end, text) in enumerate(srt_entries, start=1):
            start_ts = ms_to_srt_timestamp(start)
            end_ts = ms_to_srt_timestamp(end)
            f.write(f"{idx}\n")
            f.write(f"{start_ts} --> {end_ts}\n")
            f.write(f"{text}\n\n")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(
        description="Caption videos using AssemblyAI and output .srt files."
    )
    parser.add_argument(
        '--file', '-f', required=True,
        help='Path to local video/audio file'
    )
    parser.add_argument(
        '--output', '-o', required=True,
        help='Path to output .srt file'
    )
    args = parser.parse_args()

    client = AssemblyAIClient()
    print("Uploading file to AssemblyAI...")
    audio_url = client.upload_audio(args.file)
    print(f"Received audio URL: {audio_url}")

    print("Requesting transcription...")
    transcript_id = client.request_transcription(audio_url)
    print(f"Transcript ID: {transcript_id}")

    print("Polling for transcript completion...")
    transcript_json = client.poll_transcription(transcript_id)

    print("Converting transcript to SRT...")
    transcript_to_srt(transcript_json, args.output)

    print(f"SRT file saved to: {args.output}")