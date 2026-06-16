import os
import json
import base64
import requests
from dotenv import load_dotenv

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

OPENROUTER_KEY = os.getenv("OPENROUTERKEY")

# The successful run directory
run_dir = os.path.join(script_dir, "run_log", "run_20260615_203630")
success_file_path = os.path.join(run_dir, "success.txt")

def transcribe_speech(audio_base64: str) -> str:
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Transcribe this audio recording in Polish. Write down every single word exactly as spoken, without summarizing."
                    },
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": audio_base64,
                            "format": "mp3"
                        }
                    }
                ]
            }
        ]
    }
    response = requests.post(url, headers=headers, json=payload)
    response.raise_for_status()
    res_data = response.json()
    choices = res_data.get("choices", [])
    if choices:
        return choices[0].get("message", {}).get("content", "").strip()
    return ""

def main():
    # Read success.txt to extract the base64 audio
    with open(success_file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # Let's parse the success dict printed at the end of success.txt
    # Format: {'code': 0, 'message': '{FLG:CANYOUHEARME}', 'audio': '...'}
    # We find where 'audio': ' starts and ends
    start_str = "'audio': '"
    start_idx = content.find(start_str)
    if start_idx == -1:
        start_str = '"audio": "'
        start_idx = content.find(start_str)
    
    if start_idx == -1:
        print("Could not find audio key in success.txt")
        return
        
    audio_start = start_idx + len(start_str)
    # find ending quote ' or "
    quote_char = content[start_idx + len(start_str) - 1]
    audio_end = content.find(quote_char, audio_start)
    
    audio_base64 = content[audio_start:audio_end]
    print(f"Extracted base64 audio string (length: {len(audio_base64)} chars)")
    
    # Save as 08_operator_reply_4.mp3
    output_path = os.path.join(run_dir, "08_operator_reply_4.mp3")
    with open(output_path, "wb") as f:
        f.write(base64.b64decode(audio_base64))
    print(f"Saved final operator reply to {output_path}")
    
    # Transcribe
    print("Transcribing final response audio...")
    text = transcribe_speech(audio_base64)
    print(f"\n--- Transcribed Final Response ---\n{text}\n----------------------------------")
    
    # Save transcript
    transcript_path = os.path.join(run_dir, "08_operator_reply_4_transcript.txt")
    with open(transcript_path, "w", encoding="utf-8") as tf:
        tf.write(text)
    print(f"Saved transcript to {transcript_path}")

if __name__ == "__main__":
    main()
