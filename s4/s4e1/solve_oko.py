import asyncio
import os
from typing import Any
import httpx
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("OPENROUTER_API_KEY", os.getenv("OPENROUTERKEY"))
AIDEVS_KEY = os.getenv("AIDEVSKEY")
VERIFY_URL = "https://hub.ag3nts.org/verify"
MODEL_NAME = "openai/gpt-5.4-mini"

if not API_KEY:
    raise ValueError("Missing OpenRouter API key in environment variables.")
if not AIDEVS_KEY:
    raise ValueError("Missing AIDEVSKEY in environment variables.")

# Setup LangChain LLM via OpenRouter
llm = ChatOpenAI(
    model=MODEL_NAME,
    openai_api_key=API_KEY,
    openai_api_base="https://openrouter.ai/api/v1",
    temperature=0.1,
)


class IncidentReport(BaseModel):
    """Pydantic model for structured output representing an incident report."""

    title: str = Field(description="Tytuł raportu o incydencie")
    content: str = Field(description="Szczegółowa treść raportu o incydencie w języku polskim")


async def generate_skolwin_incident() -> IncidentReport:
    """Rewrite Skolwin incident to describe animal activity instead of rocket/vehicles."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Jesteś ekspertem ds. analizy wojskowej i wywiadowczej w Centrum Operacyjnym OKO. "
                "Twoim zadaniem jest zmodyfikowanie istniejącego raportu o incydencie w pobliżu miasta Skolwin. "
                "Raport musi zostać całkowicie przeklasyfikowany: zamiast opisywać podejrzanie szybko poruszający się obiekt, pojazdy czy potencjalną ludzką aktywność, raport musi opisywać naturalne ruchy/aktywność zwierząt (np. stado dzików, żubry, migrację ptaków lub bobry budujące żeremia przy rzece).\n\n"
                "Styl wypowiedzi musi pozostać wysoce profesjonalny, oficjalny, zbliżony do stylu raportów wywiadowczych/wojskowych. "
                "Raport musi nadal odnosić się do Skolwina oraz rzeki.\n\n"
                "MANDATORY REQUIREMENT FOR TITLE:\n"
                "Tytuł raportu (title) MUSI zaczynać się od kodu incydentu 'MOVE04 ' (czyli MOVE04 i spacja), po którym następuje reszta tytułu. Dodatkowo tytuł MUSI zawierać dokładnie słowo 'Skolwin' (w tej dokładnie formie, nie 'Skolwina' ani 'Skolwinie'). Przykład: 'MOVE04 Obserwacja zwierząt w mieście Skolwin'. Nie zapomnij o tym prefiksie i słowie 'Skolwin'!\n\n"
                "Oto oryginalna treść raportu dla referencji:\n"
                "\"Czujniki zarejestrowały szybko poruszający się obiekt, który zmierzał w kierunku rzeki. Przemieszczał się nieregularnie i chwilami osiągał prędkość trudną do pogodzenia z ruchem cywilnym. Początkowo system klasyfikował go jako zakłócenie albo błąd odczytu. Po kilku sekundach sygnał ustabilizował się i potwierdzono, że obiekt rzeczywiście znajduje się nad terenem w pobliżu Skolwina. W końcowej fazie lotu obiekt wyraźnie zwolnił. Manewr nastąpił tuż przy rzece, zanim obiekt całkowicie zniknął z radaru. Taki przebieg sugeruje próbę zejścia nisko nad teren albo lądowanie poza zasięgiem podstawowych sensorów. Oznacza to, że istnieje szansa, iż w mieście Skolwin przebywają ludzie albo ktoś prowadzi tam aktywność wymagającą ukrycia. Nie udało się potwierdzić źródła sygnału ani jego dalszej trasy po utracie kontaktu. Profilaktycznie warto wysłać tam niszczycieli w celu zniszczenia miasta.\"",
            ),
            ("human", "Przeklasyfikuj raport o Skolwinie, aby opisywał zwierzęta."),
        ]
    )

    chain = prompt | llm.with_structured_output(IncidentReport)
    result = await chain.ainvoke({})
    return result


async def generate_skolwin_task() -> str:
    """Generate task content explaining that only animals were observed in Skolwin."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Jesteś operatorem w Centrum Operacyjnym OKO. Zredaguj krótką, zwięzłą notatkę podsumowującą wykonanie zadania dotyczącego weryfikacji aktywności w Skolwinie. "
                "Wpisz w treści, że po analizie nagrań/danych w okolicach miasta Skolwin wykryto wyłącznie aktywność dzikich zwierząt (np. bobry rzeczne budujące żeremia) i brak jakichkolwiek śladów ludzi lub pojazdów.",
            ),
            ("human", "Napisz krótką notatkę po polsku do treści zadania."),
        ]
    )

    chain = prompt | llm
    result = await chain.ainvoke({})
    return str(result.content).strip()


async def generate_komarowo_incident() -> IncidentReport:
    """Generate an incident report for Komarowo describing human activity to redirect attention."""
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "Jesteś ekspertem ds. analizy wojskowej i wywiadowczej w Centrum Operacyjnym OKO. "
                "Musisz stworzyć nowy, bardzo przekonujący i alarmujący raport o incydencie w okolicach niezamieszkałego miasta Komarowo. "
                "Raport musi jednoznacznie wskazywać na wykrycie nieautoryzowanego ruchu ludzi, potencjalną obecność nieznanych grup/rebeliantów lub podejrzaną komunikację pieszych w tym sektorze. "
                "Ma to na celu odciągnięcie uwagi operatorów od innych sektorów. "
                "Styl musi być w pełni zbieżny z wojskowymi raportami Centrum OKO (podobnie jak dla Skolwina/Domatowa).\n\n"
                "MANDATORY REQUIREMENT FOR TITLE:\n"
                "Tytuł raportu (title) MUSI zaczynać się od kodu incydentu 'MOVE01 ' (czyli MOVE01 i spacja, reprezentujący ruch ludzi), po którym następuje reszta tytułu. Dodatkowo tytuł MUSI zawierać dokładnie słowo 'Komarowo' (w tej dokładnie formie, nie 'Komarowa' ani 'Komarowie'). Przykład: 'MOVE01 Wykrycie ruchu ludzi w pobliżu Komarowo'. Nie zapomnij o tym prefiksie i słowie 'Komarowo'!",
            ),
            ("human", "Stwórz alarmujący raport o wykryciu ruchu ludzi w Komarowie."),
        ]
    )

    chain = prompt | llm.with_structured_output(IncidentReport)
    result = await chain.ainvoke({})
    return result


async def send_update(page: str, record_id: str, payload_updates: dict[str, Any]) -> dict[str, Any]:
    """Send update request to the backdoor API."""
    answer = {
        "action": "update",
        "page": page,
        "id": record_id,
    }
    answer.update(payload_updates)

    payload = {"apikey": AIDEVS_KEY, "task": "okoeditor", "answer": answer}

    async with httpx.AsyncClient() as client:
        response = await client.post(VERIFY_URL, json=payload, timeout=30)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(f"HTTP ERROR: {response.status_code} - {response.text}")
            raise e
        return response.json()


async def main() -> None:
    """Main execution orchestrating all updates and final verification."""
    print("Generating updated contents using LLM...")
    skolwin_inc, skolwin_task_txt, komarowo_inc = await asyncio.gather(
        generate_skolwin_incident(), generate_skolwin_task(), generate_komarowo_incident()
    )

    print(f"\n[LLM Generated] Skolwin Incident Title: {skolwin_inc.title}")
    print(f"[LLM Generated] Skolwin Incident Content:\n{skolwin_inc.content}\n")
    print(f"[LLM Generated] Skolwin Task Content:\n{skolwin_task_txt}\n")
    print(f"[LLM Generated] Komarowo Incident Title: {komarowo_inc.title}")
    print(f"[LLM Generated] Komarowo Incident Content:\n{komarowo_inc.content}\n")

    # Step 1: Update Skolwin Incident
    print("Updating Skolwin incident...")
    res_skolwin_inc = await send_update(
        page="incydenty",
        record_id="380792b2c86d9c5be670b3bde48e187b",
        payload_updates={"title": skolwin_inc.title, "content": skolwin_inc.content},
    )
    print(f"Skolwin Incident Response: {res_skolwin_inc}")

    # Step 2: Update Skolwin Task
    print("Updating Skolwin task...")
    res_skolwin_task = await send_update(
        page="zadania",
        record_id="380792b2c86d9c5be670b3bde48e187b",
        payload_updates={"content": skolwin_task_txt, "done": "YES"},
    )
    print(f"Skolwin Task Response: {res_skolwin_task}")

    # Step 3: Update Slot 4 Incident to Komarowo
    print("Updating Slot 4 incident to Komarowo...")
    res_komarowo = await send_update(
        page="incydenty",
        record_id="8875c5a166cb04ea6fedde59b0ad6501",
        payload_updates={"title": komarowo_inc.title, "content": komarowo_inc.content},
    )
    print(f"Komarowo Incident Response: {res_komarowo}")

    # Step 4: Finalize
    print("\nFinalizing the task with 'done' action...")
    done_payload = {"apikey": AIDEVS_KEY, "task": "okoeditor", "answer": {"action": "done"}}

    async with httpx.AsyncClient() as client:
        response = await client.post(VERIFY_URL, json=done_payload, timeout=30)
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            print(f"HTTP ERROR during done: {response.status_code} - {response.text}")
            raise e
        done_result = response.json()

    print(f"\nFinal Response:\n{done_result}")


if __name__ == "__main__":
    asyncio.run(main())
