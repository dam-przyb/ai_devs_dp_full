import os
import json
import base64
import requests
from dotenv import load_dotenv

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def main():
    api_key = os.getenv("OPENROUTERKEY")
    if not api_key:
        print("Error: OPENROUTERKEY not found in environment variables.")
        return

    audio_path = os.path.join(script_dir, "captured", "attachments", "signal_004_attachment.mp3")
    if not os.path.exists(audio_path):
        print(f"Audio file not found at {audio_path}")
        return

    print("Encoding audio...")
    with open(audio_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    print("Sending to OpenRouter (google/gemini-2.5-flash)...")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
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
                            "data": audio_b64,
                            "format": "mp3"
                        }
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        choices = data.get("choices", [])
        if choices:
            text = choices[0].get("message", {}).get("content", "")
            print("\n--- Transcription ---")
            print(text)
            
            # Save to run_log
            log_path = os.path.join(script_dir, "run_log", "transcription_signal_004.txt")
            with open(log_path, "w", encoding="utf-8") as lf:
                lf.write(text)
            print(f"\nSaved transcription to {log_path}")
        else:
            print("No transcription found in response.")
            print(json.dumps(data, indent=2))
            
    except Exception as e:
        print(f"Error occurred: {e}")
        if 'response' in locals() and response:
            print("Response:", response.text)

if __name__ == "__main__":
    main()
