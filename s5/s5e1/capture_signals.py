import os
import json
import base64
import requests
from dotenv import load_dotenv

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def get_extension(meta):
    if not meta:
        return "bin"
    meta = meta.lower()
    if "json" in meta:
        return "json"
    if "text" in meta or "txt" in meta:
        return "txt"
    if "png" in meta:
        return "png"
    if "jpeg" in meta or "jpg" in meta:
        return "jpg"
    if "audio" in meta or "mp3" in meta:
        return "mp3"
    if "wav" in meta:
        return "wav"
    return "bin"

def main():
    api_key = os.getenv("AIDEVSKEY")
    if not api_key:
        print("Error: AIDEVSKEY not found in environment variables.")
        return

    url = "https://hub.ag3nts.org/verify"
    
    # 1. Start session
    print("Starting radiomonitoring session...")
    start_payload = {
        "apikey": api_key,
        "task": "radiomonitoring",
        "answer": {
            "action": "start"
        }
    }
    
    try:
        response = requests.post(url, json=start_payload)
        response.raise_for_status()
        start_data = response.json()
        print(f"Session started: {json.dumps(start_data, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Failed to start session: {e}")
        return

    # Setup directories
    captured_dir = os.path.join(script_dir, "captured")
    raw_dir = os.path.join(captured_dir, "raw")
    attachments_dir = os.path.join(captured_dir, "attachments")
    os.makedirs(raw_dir, exist_ok=True)
    os.makedirs(attachments_dir, exist_ok=True)

    # Save session start info
    with open(os.path.join(captured_dir, "session_start.json"), "w", encoding="utf-8") as f:
        json.dump(start_data, f, indent=4, ensure_ascii=False)

    # 2. Listen loop
    index = 1
    max_iterations = 150  # Safety limit
    
    while index <= max_iterations:
        print(f"\nListening to signal #{index}...")
        listen_payload = {
            "apikey": api_key,
            "task": "radiomonitoring",
            "answer": {
                "action": "listen"
            }
        }
        
        try:
            res = requests.post(url, json=listen_payload)
            res.raise_for_status()
            data = res.json()
        except Exception as e:
            print(f"Failed to listen at index {index}: {e}")
            break

        # Save raw response
        raw_file_path = os.path.join(raw_dir, f"signal_{index:03d}.json")
        with open(raw_file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

        # Print quick summary
        code = data.get("code")
        message = data.get("message", "")
        transcription = data.get("transcription")
        meta = data.get("meta")
        has_attachment = "attachment" in data
        
        print(f"Signal #{index} - Code: {code}, Message: {message}")
        if transcription:
            print(f"Transcription: {transcription[:100]}...")
        if meta or has_attachment:
            filesize = data.get("filesize", 0)
            print(f"Attachment type: {meta}, size: {filesize} bytes")

        # Check for termination condition
        # e.g., if there's no signal, or if code indicates we have enough data.
        # Often the message says "I have nothing more for you" or similar.
        # Let's inspect the message/code
        if "nic więcej nie mam" in message.lower() or "enough data" in message.lower() or "koniec" in message.lower() or "no more" in message.lower() or code == 0 or (not transcription and not has_attachment and "captured" not in message.lower()):
            print("Termination signal detected in response.")
            break

        # Process attachment if exists
        if has_attachment and data["attachment"]:
            try:
                att_bytes = base64.b64decode(data["attachment"])
                ext = get_extension(meta)
                att_file_name = f"signal_{index:03d}_attachment.{ext}"
                att_file_path = os.path.join(attachments_dir, att_file_name)
                
                # If JSON or text, save with utf-8 encoding (or just write bytes)
                with open(att_file_path, "wb") as bf:
                    bf.write(att_bytes)
                print(f"Saved attachment to {att_file_path}")
            except Exception as ae:
                print(f"Failed to save attachment for signal #{index}: {ae}")

        index += 1

    print(f"\nCaptured {index - 1} signals successfully.")

if __name__ == "__main__":
    main()
