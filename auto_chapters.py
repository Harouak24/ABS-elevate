import os
import json
import argparse
import assemblyai as aai
import openai
from typing import List, Dict

# Configuration
ASSEMBLYAI_API_KEY = os.getenv('ASSEMBLYAI_API_KEY')
if not ASSEMBLYAI_API_KEY:
    raise EnvironmentError('Please set the ASSEMBLYAI_API_KEY environment variable.')
aai.settings.api_key = ASSEMBLYAI_API_KEY

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY') or None
if OPENAI_API_KEY:
    openai.api_key = OPENAI_API_KEY

# Initialize Transcriber
transcriber = aai.Transcriber()


def get_assembly_transcript(source: str):
    """
    Submits media to AssemblyAI with auto_chapters enabled and returns
    the transcript object plus its chapter list.
    """
    config = aai.TranscriptionConfig(auto_chapters=True)
    transcript = transcriber.transcribe(source, config)
    chapters = []
    for chap in transcript.chapters or []:
        chapters.append({
            'start': chap.start,  # seconds
            'end': chap.end,      # seconds
            'headline': chap.headline
        })
    return transcript, chapters


def generate_llm_chapters(transcript_text: str) -> List[Dict]:
    """
    Generates chapter markers via an LLM. Returns a list of dicts:
    [{'start': float, 'end': float, 'title': str}, ...]
    """
    if not OPENAI_API_KEY:
        raise EnvironmentError('OPENAI_API_KEY is required for LLM-generated chapters.')

    prompt = (
        "You are an assistant that creates chapter markers for educational videos."
        " Given the transcript text, suggest chapters with start and end times in seconds and a "
        "short descriptive title. Return strictly a JSON array of objects with keys 'start', 'end', 'title'.\n" +
        transcript_text
    )
    response = openai.ChatCompletion.create(
        model='gpt-4',
        messages=[
            {'role': 'system', 'content': 'Generate chapter markers from transcript.'},
            {'role': 'user', 'content': prompt}
        ],
        temperature=0.3
    )
    content = response.choices[0].message.content.strip()
    return json.loads(content)


def reconcile_chapters(
    assembly: List[Dict], llm: List[Dict]
) -> List[Dict]:
    """
    Merges AssemblyAI and LLM chapter lists.
    Prefers AssemblyAI segments but overrides titles if LLM provides more detail,
    and adds non-overlapping LLM chapters.
    """
    reconciled = []

    # Add assembly chapters, possibly overridden
    for asm in assembly:
        entry = asm.copy()
        # Override title if more descriptive in LLM input
        for marker in llm:
            if asm['start'] <= marker['start'] < asm['end']:
                if len(marker['title']) > len(asm.get('headline', '')):
                    entry['headline'] = marker['title']
        reconciled.append(entry)

    # Append LLM-only chapters
    for m in llm:
        overlap = any(abs(m['start'] - a['start']) < 1 for a in assembly)
        if not overlap:
            reconciled.append({
                'start': m['start'],
                'end': m['end'],
                'headline': m['title']
            })

    # Sort by start time
    return sorted(reconciled, key=lambda x: x['start'])


def main():
    parser = argparse.ArgumentParser(
        description='Auto-chapterning with AssemblyAI SDK and LLM reconciliation.'
    )
    parser.add_argument('-s', '--source', required=True,
                        help='Path or URL to media file')
    parser.add_argument('-o', '--output', required=True,
                        help='Base path for output JSON files (without extension)')
    args = parser.parse_args()

    print('Requesting AssemblyAI transcript with auto-chapters...')
    transcript, assembly_chapters = get_assembly_transcript(args.source)
    print(f'Retrieved {len(assembly_chapters)} AssemblyAI chapters.')

    # Save AssemblyAI chapters
    asm_path = f"{args.output}_assembly.json"
    with open(asm_path, 'w', encoding='utf-8') as f:
        json.dump(assembly_chapters, f, indent=2)
    print(f'AssemblyAI chapters saved to {asm_path}')

    # LLM-generated chapters
    print('Generating LLM-based chapters...')
    llm_chapters = generate_llm_chapters(transcript.text)
    llm_path = f"{args.output}_llm.json"
    with open(llm_path, 'w', encoding='utf-8') as f:
        json.dump(llm_chapters, f, indent=2)
    print(f'LLM chapters saved to {llm_path}')

    # Reconciliation
    print('Reconciling chapter lists...')
    reconciled = reconcile_chapters(assembly_chapters, llm_chapters)
    rec_path = f"{args.output}_reconciled.json"
    with open(rec_path, 'w', encoding='utf-8') as f:
        json.dump(reconciled, f, indent=2)
    print(f'Reconciled chapters saved to {rec_path}')


if __name__ == '__main__':
    main()