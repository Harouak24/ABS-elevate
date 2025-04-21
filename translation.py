import os
import openai
import argparse
import time
from typing import List, Dict

# Configuration
env_api_key = os.getenv("OPENAI_API_KEY")
if not env_api_key:
    raise EnvironmentError("Please set the OPENAI_API_KEY environment variable.")
openai.api_key = env_api_key

# Supported target languages map
target_language_map = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "ar": "Arabic"
}


def parse_srt(srt_path: str) -> List[Dict]:
    """
    Parse an .srt file into a list of entries:
    [{ 'index': int, 'start': str, 'end': str, 'text': str }, ...]
    """
    entries = []
    with open(srt_path, "r", encoding="utf-8") as f:
        content = f.read().strip()
    blocks = content.split("\n\n")
    for block in blocks:
        lines = block.split("\n")
        if len(lines) >= 3:
            idx = int(lines[0].strip())
            times = lines[1].strip().split(" --> ")
            start, end = times[0], times[1]
            text = " ".join(lines[2:]).strip()
            entries.append({"index": idx, "start": start, "end": end, "text": text})
    return entries


def write_srt(entries: List[Dict], out_path: str):
    """
    Write a list of entries back to .srt file.
    """
    with open(out_path, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(f"{entry['index']}\n")
            f.write(f"{entry['start']} --> {entry['end']}\n")
            f.write(f"{entry['text']}\n\n")


def translate_text(text: str, target_lang_code: str, retry: int = 3) -> str:
    """
    Use OpenAI ChatCompletion to translate a piece of text into the target language.
    """
    target_language = target_language_map.get(target_lang_code)
    if not target_language:
        raise ValueError(f"Unsupported target language: {target_lang_code}")

    prompt = (
        f"Translate the following text into {target_language}."
        f" Preserve meaning without adding or removing content:\n\"{text}\""
    )
    for attempt in range(retry):
        try:
            response = openai.ChatCompletion.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a translation assistant."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            translated = response.choices[0].message.content.strip()
            return translated
        except openai.error.OpenAIError as e:
            wait = 2 ** attempt
            print(f"Translation attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)
    raise RuntimeError("Failed to translate text after multiple attempts.")


def translate_srt_file(input_srt: str, output_srt: str, target_lang_code: str):
    """
    Parse input .srt, translate each entry's text, and write to output .srt preserving timestamps.
    """
    entries = parse_srt(input_srt)
    for entry in entries:
        entry["text"] = translate_text(entry["text"], target_lang_code)
    write_srt(entries, output_srt)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Translate an SRT file to a target language preserving timestamps.")
    parser.add_argument('-i', '--input', required=True, help='Path to input .srt file')
    parser.add_argument('-o', '--output', required=True, help='Path to output translated .srt file')
    parser.add_argument('-t', '--target', required=True, choices=target_language_map.keys(),
                        help='Target language code: "en", "fr", "es", "ar"')
    args = parser.parse_args()

    print(f"Translating {args.input} to {target_language_map[args.target]}...")
    translate_srt_file(args.input, args.output, args.target)
    print(f"Translated SRT saved to {args.output}")