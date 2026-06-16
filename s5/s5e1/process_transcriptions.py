import os
import json

script_dir = os.path.dirname(os.path.abspath(__file__))
raw_dir = os.path.join(script_dir, "captured", "raw")

def main():
    files = sorted(os.listdir(raw_dir))
    print(f"Total raw files: {len(files)}")
    
    transcriptions = []
    attachments = []
    
    for filename in files:
        if not filename.endswith(".json"):
            continue
        file_path = os.path.join(raw_dir, filename)
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
            trans = data.get("transcription")
            meta = data.get("meta")
            
            if trans:
                transcriptions.append((filename, trans))
            if "attachment" in data:
                attachments.append((filename, meta, data.get("filesize")))

    print("\n--- TRANSCRIPTIONS ---")
    for fname, trans in transcriptions:
        print(f"[{fname}]: {trans.strip()}")
        
    print("\n--- ATTACHMENTS ---")
    for fname, meta, size in attachments:
        print(f"[{fname}]: meta={meta}, size={size} bytes")

if __name__ == "__main__":
    main()
