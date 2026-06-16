import os
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

    print(f"Sending audio file {audio_path} to OpenRouter Whisper...")
    url = "https://openrouter.ai/api/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    files = {
        "file": ("signal_004_attachment.mp3", open(audio_path, "rb"), "audio/mpeg")
    }
    data = {
        "model": "openai/whisper-large-v3"
    }

    try:
        response = requests.post(url, headers=headers, files=files, data=data)
        response.raise_for_status()
        result = response.json()
        print("\n--- Transcription Result ---")
        print(result.get("text"))
        
        # Save transcription to a text file in run_log
        log_path = os.path.join(script_dir, "run_log", "transcription_signal_004.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(result.get("text", ""))
        print(f"\nSaved transcription to {log_path}")
    except Exception as e:
        print(f"Error transcribing audio: {e}")
        if 'response' in locals() and response:
            print("Response:", response.text)

if __name__ == "__main__":
    main()
