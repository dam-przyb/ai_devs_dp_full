import os
import json
import base64
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

# Load env from root directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, "..", "..", ".env")
load_dotenv(dotenv_path=env_path)

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def main():
    api_key = os.getenv("OPENROUTERKEY")
    if not api_key:
        print("Error: OPENROUTERKEY not found in environment variables.")
        return

    # Use google/gemini-2.5-flash as the multimodal model
    llm = ChatOpenAI(
        model="google/gemini-2.5-flash",
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
    )

    attachments_dir = os.path.join(script_dir, "captured", "attachments")
    
    images = [
        ("signal_018_attachment.jpg", "image/jpeg"),
        ("signal_026_attachment.png", "image/png")
    ]

    for img_name, mime in images:
        img_path = os.path.join(attachments_dir, img_name)
        if not os.path.exists(img_path):
            print(f"File {img_name} not found at {img_path}")
            continue

        print(f"\nAnalyzing {img_name}...")
        try:
            b64_data = encode_image(img_path)
            message = HumanMessage(
                content=[
                    {
                        "type": "text", 
                        "text": "Identify what is in this image. Read all text, coordinates, numbers, diagrams, or maps. Focus especially on anything related to the city of 'Syjon' (Skarszewy) or warehouses, area, contact numbers, etc. Report everything you see in detail."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime};base64,{b64_data}"
                        }
                    }
                ]
            )
            
            response = llm.invoke([message])
            print(f"--- Response for {img_name} ---")
            print(response.content)
            
            # Save response to a text file in run_log
            log_path = os.path.join(script_dir, "run_log", f"analysis_{img_name}.txt")
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(response.content)
            print(f"Saved response to {log_path}")
            
        except Exception as e:
            print(f"Error analyzing {img_name}: {e}")

if __name__ == "__main__":
    main()
