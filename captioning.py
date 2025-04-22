import os
import argparse
import assemblyai as aai
from datetime import timedelta

# Caption settings (tune as needed)
MAX_CAPTION_DURATION_MS = 5000  # max block duration in ms
MAX_WORDS_PER_CAPTION = 15      # max words per block


def ms_to_srt_timestamp(ms: int) -> str:
    """
    Convert milliseconds to SRT timestamp format: HH:MM:SS,mmm
    """
    total_seconds = ms / 1000.0
    hours = int(total_seconds // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)
    milliseconds = int((total_seconds - int(total_seconds)) * 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def transcript_to_srt(words: list, output_path: str):
    """
    Convert list of word-level dicts into a .srt file.
    Each word: {'start': int_ms, 'end': int_ms, 'text': str}
    """
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
        block_start = None

    for w in words:
        start_ms = w['start']
        end_ms = w['end']

        if block_start is None:
            block_start = start_ms
            current_block.append({'start': start_ms, 'end': end_ms, 'text': w['text']})
            continue

        # Exceed duration or word count?
        if ((end_ms - block_start) > MAX_CAPTION_DURATION_MS or
            len(current_block) >= MAX_WORDS_PER_CAPTION):
            flush_block()
            block_start = start_ms

        current_block.append({'start': start_ms, 'end': end_ms, 'text': w['text']})

    # Flush any remaining
    flush_block()

    # Write SRT
    with open(output_path, 'w', encoding='utf-8') as f:
        for idx, (start, end, text) in enumerate(srt_entries, start=1):
            start_ts = ms_to_srt_timestamp(start)
            end_ts = ms_to_srt_timestamp(end)
            f.write(f"{idx}\n")
            f.write(f"{start_ts} --> {end_ts}\n")
            f.write(f"{text}\n\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate .srt captions from a video/audio file using AssemblyAI SDK."
    )
    parser.add_argument(
        '-f', '--file', required=True,
        help='Path to local video/audio file'
    )
    parser.add_argument(
        '-o', '--output', required=True,
        help='Output path for the .srt file'
    )
    args = parser.parse_args()

    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise EnvironmentError('Please set the ASSEMBLYAI_API_KEY environment variable.')

    # Configure SDK
    aai.settings.api_key = api_key
    transcriber = aai.Transcriber()

    print('Submitting transcription request...')
    transcript = transcriber.transcribe(args.file)

    # transcript.words is a list of dicts with 'start', 'end', 'text'
    words = transcript.words
    if not words:
        raise RuntimeError('No word-level timestamps found in transcript.')

    print(f'Received {len(words)} words. Generating SRT...')
    transcript_to_srt(words, args.output)

    print(f'SRT captions saved to: {args.output}')


if __name__ == '__main__':
    main()