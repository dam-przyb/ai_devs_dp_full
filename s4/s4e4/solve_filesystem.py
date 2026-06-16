import os
import json
from pathlib import Path
import requests
from dotenv import load_dotenv

# Load environment variables from the project root .env
dotenv_path = Path(__file__).resolve().parents[2] / '.env'
load_dotenv(dotenv_path=dotenv_path)

AIDEVS_KEY = os.getenv("AIDEVSKEY")
VERIFY_URL = "https://hub.ag3nts.org/verify"

if not AIDEVS_KEY:
    raise ValueError("Missing AIDEVSKEY in environment variables.")

def send_actions(actions):
    payload = {
        "apikey": AIDEVS_KEY,
        "task": "filesystem",
        "answer": actions
    }
    response = requests.post(VERIFY_URL, json=payload, timeout=60)
    return response.json()

def main():
    actions = []
    
    # 1. Reset
    actions.append({
        "action": "reset"
    })
    
    # 2. Create directories
    actions.append({
        "action": "createDirectory",
        "path": "/miasta"
    })
    actions.append({
        "action": "createDirectory",
        "path": "/osoby"
    })
    actions.append({
        "action": "createDirectory",
        "path": "/towary"
    })
    
    # 3. Create cities (miasta)
    cities = {
        "opalino": {"chleb": 45, "woda": 120, "mlotek": 6},
        "domatowo": {"makaron": 60, "woda": 150, "lopata": 8},
        "brudzewo": {"ryz": 55, "woda": 140, "wiertarka": 5},
        "darzlubie": {"wolowina": 25, "woda": 130, "kilof": 7},
        "celbowo": {"kurczak": 40, "woda": 125, "mlotek": 6},
        "mechowo": {"ziemniaki": 100, "kapusta": 70, "marchew": 65, "woda": 165, "lopata": 9},
        "puck": {"chleb": 50, "ryz": 45, "woda": 175, "wiertarka": 7},
        "karlinkowo": {"makaron": 52, "wolowina": 22, "ziemniaki": 95, "woda": 155, "kilof": 6}
    }
    
    for city_name, demand in cities.items():
        actions.append({
            "action": "createFile",
            "path": f"/miasta/{city_name}",
            "content": json.dumps(demand, ensure_ascii=False)
        })
        
    # 4. Create people (osoby)
    people = {
        "iga_kapecka": "Iga Kapecka [Opalino](/miasta/opalino)",
        "natan_rams": "Natan Rams [Domatowo](/miasta/domatowo)",
        "rafal_kisiel": "Rafal Kisiel [Brudzewo](/miasta/brudzewo)",
        "marta_frantz": "Marta Frantz [Darzlubie](/miasta/darzlubie)",
        "oskar_radtke": "Oskar Radtke [Celbowo](/miasta/celbowo)",
        "eliza_redmann": "Eliza Redmann [Mechowo](/miasta/mechowo)",
        "damian_kroll": "Damian Kroll [Puck](/miasta/puck)",
        "lena_konkel": "Lena Konkel [Karlinkowo](/miasta/karlinkowo)"
    }
    
    for person_name, content in people.items():
        actions.append({
            "action": "createFile",
            "path": f"/osoby/{person_name}",
            "content": content
        })
        
    # 5. Create goods (towary)
    goods = {
        "ryz": ["[Darzlubie](/miasta/darzlubie)", "[Opalino](/miasta/opalino)", "[Karlinkowo](/miasta/karlinkowo)"],
        "marchew": ["[Puck](/miasta/puck)"],
        "chleb": ["[Domatowo](/miasta/domatowo)", "[Celbowo](/miasta/celbowo)", "[Brudzewo](/miasta/brudzewo)"],
        "wolowina": ["[Opalino](/miasta/opalino)"],
        "kilof": ["[Puck](/miasta/puck)", "[Mechowo](/miasta/mechowo)", "[Celbowo](/miasta/celbowo)"],
        "wiertarka": ["[Karlinkowo](/miasta/karlinkowo)", "[Domatowo](/miasta/domatowo)"],
        "maka": ["[Brudzewo](/miasta/brudzewo)", "[Mechowo](/miasta/mechowo)"],
        "mlotek": ["[Karlinkowo](/miasta/karlinkowo)", "[Mechowo](/miasta/mechowo)"],
        "makaron": ["[Opalino](/miasta/opalino)"],
        "kapusta": ["[Celbowo](/miasta/celbowo)"],
        "ziemniaki": ["[Domatowo](/miasta/domatowo)", "[Darzlubie](/miasta/darzlubie)"],
        "kurczak": ["[Darzlubie](/miasta/darzlubie)"],
        "lopata": ["[Brudzewo](/miasta/brudzewo)", "[Puck](/miasta/puck)"]
    }
    
    for good_name, links in goods.items():
        # Let's try combining them on separate lines or space-separated. Let's try space-separated first.
        # e.g., "[Domatowo](/miasta/domatowo) [Celbowo](/miasta/celbowo)"
        content = " ".join(links)
        actions.append({
            "action": "createFile",
            "path": f"/towary/{good_name}",
            "content": content
        })
        
    print(f"Submitting batch with {len(actions)} actions...")
    
    batch_res = send_actions(actions)
    print("\nBatch response:")
    print(json.dumps(batch_res, indent=2, ensure_ascii=False))
    
    # Save batch response to run_log
    log_dir = Path(__file__).resolve().parent / "run_log"
    log_dir.mkdir(exist_ok=True)
    with open(log_dir / "solve_batch_response.json", "w", encoding="utf-8") as f:
        json.dump(batch_res, f, indent=2, ensure_ascii=False)
        
    # 6. Final verification (done)
    print("\nCalling action 'done' for validation...")
    done_res = send_actions({"action": "done"})
    print("\nValidation response:")
    print(json.dumps(done_res, indent=2, ensure_ascii=False))
    
    with open(log_dir / "solve_done_response.json", "w", encoding="utf-8") as f:
        json.dump(done_res, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    main()
