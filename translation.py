import os
import argparse
import time
import openai
from typing import List, Dict

# Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    raise EnvironmentError('Please set the OPENAI_API_KEY environment variable.')
openai.api_key = OPENAI_API_KEY

# Supported target languages
TARGET_LANGUAGE_MAP = {
    'en': 'English',
    'fr': 'French',
    'es': 'Spanish',
    'ar': 'Arabic'
}

# Default retry and backoff settings
MAX_RETRIES = int(os.getenv('TRANSLATION_MAX_RETRIES', 3))
BACKOFF_FACTOR = int(os.getenv('TRANSLATION_BACKOFF', 2))


def parse_srt(srt_path: str) -> List[Dict]:
    """
    Parse an .srt file into a list of entries:
    [{ 'index': int, 'start': str, 'end': str, 'text': str }, ...]
    """
    entries = []
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
    for block in content.split('\n\n'):
        lines = block.split('\n')
        if len(lines) < 3:
            continue
        idx = int(lines[0].strip())
        start, end = lines[1].split(' --> ')
        text = ' '.join(lines[2:]).strip()
        entries.append({'index': idx, 'start': start, 'end': end, 'text': text})
    return entries


def write_srt(entries: List[Dict], out_path: str):
    """
    Write entries list back to .srt file.
    """
    with open(out_path, 'w', encoding='utf-8') as f:
        for e in entries:
            f.write(f"{e['index']}\n")
            f.write(f"{e['start']} --> {e['end']}\n")
            f.write(f"{e['text']}\n\n")


def translate_text(text: str, target_code: str) -> str:
    """
    Translate a single caption text into the target language.
    """
    language = TARGET_LANGUAGE_MAP.get(target_code)
    if not language:
        raise ValueError(f"Unsupported language code: {target_code}")

    prompt = (
        f"Translate this text into {language} without changing meaning or length: '{text}'"
    )
    for attempt in range(MAX_RETRIES):
        try:
            resp = openai.ChatCompletion.create(
                model='gpt-4',
                messages=[
                    {'role': 'system', 'content': 'You are a translation assistant.'},
                    {'role': 'user', 'content': prompt}
                ],
                temperature=0
            )
            return resp.choices[0].message.content.strip()
        except openai.error.OpenAIError as err:
            wait = BACKOFF_FACTOR ** attempt
            print(f"Translation error (attempt {attempt+1}): {err}. Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError('Translation failed after multiple attempts.')


def translate_srt(entries: List[Dict], target_code: str) -> List[Dict]:
    """
    Translate all entries into target language, preserving timestamps.
    """
    translated = []
    for e in entries:
        txt = translate_text(e['text'], target_code)
        translated.append({
            'index': e['index'],
            'start': e['start'],
            'end': e['end'],
            'text': txt
        })
    return translated


def main():
    parser = argparse.ArgumentParser(
        description='Translate an .srt file into one or more target languages.'
    )
    parser.add_argument('-s', '--source', required=True,
                        help='Input .srt file path')
    parser.add_argument('-o', '--output', required=True,
                        help='Output filename base (e.g., captions)')
    parser.add_argument('-t', '--targets', required=True,
                        help='Comma-separated language codes (en,fr,es,ar)')
    args = parser.parse_args()

    entries = parse_srt(args.source)
    for code in args.targets.split(','):
        code = code.strip()
        if code not in TARGET_LANGUAGE_MAP:
            print(f"Skipping unsupported code: {code}")
            continue
        print(f"Translating to {TARGET_LANGUAGE_MAP[code]}...")
        translated = translate_srt(entries, code)
        out_file = f"{args.output}_{code}.srt"
        write_srt(translated, out_file)
        print(f"Written {out_file}")

if __name__ == '__main__':
    main()