# AI_Devs4 Task Summary: S03E04 (Negotiations)

## 1. 🎯 What Was Accomplished

The objective of the task was to build one or two external tools (HTTP endpoints) for a central AI agent to use in order to find cities offering specific items needed for building a wind turbine. 
- **Goal**: Create an API that takes a natural language item request, matches it to a dataset of over 2000 items, and returns a list of cities where that item is available.
- **Deliverables**: 
  - `server.py`: A Flask application hosting the `/api/find_item_cities` tool endpoint.
  - `register.py`: A script to register the tool's ngrok URL with the central task verification system.
  - `check_flag.py`: A script to asynchronously poll the task status and retrieve the final flag.
- The task was successfully completed, resulting in the flag `FLG:WINDFARM`.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

### 2a. Architecture Overview
The solution was an API built with Flask, acting as a "Tool" for an external agent. Inside the tool, we used an LLM via LangChain (pointing to OpenRouter) to translate messy natural language queries into exact database matches.

```text
[Centrala Agent] ---> POST {"params": "potrzebuję kabla 10m"} ---> [Flask Server]
                                                                        |
                                                                        v
[Response: "Krakow, Warszawa"] <--- [CSV lookup] <--- [Item ID] <--- [LLM Matcher]
```

### 2b. Key Components

#### `LLM Matcher Chain`
**Purpose**: Translates natural language queries into exact item names from `items.csv`.
```python
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an assistant that maps a user's natural language request to an EXACT item name from a predefined list. "
               "Return ONLY the exact name of the item from the list that best matches the user's request.\n\n"
               "Here is the list of available items:\n{item_list}"),
    ("human", "{query}")
])
chain = prompt | llm | StrOutputParser()
```

#### `CSV Data Loader`
**Purpose**: Loads relational data (items, cities, connections) into in-memory dictionaries on startup to allow instantaneous O(1) lookups after the LLM matching.

### 2c. Data & Control Flow
1. Centrala agent sends a JSON POST request containing `params` with a natural language query.
2. The Flask route extracts the query and runs it through the LangChain LLM, providing the entire list of 2139 item names as context.
3. The LLM returns the exact string of the matched item.
4. The server looks up the item code from the `items_map` dictionary.
5. Using `connections.csv` data, it retrieves all city codes for that item.
6. Using `cities.csv` data, it maps city codes to city names and returns them as a comma-separated string (staying under the 500-byte limit).

---

## 3. 🧱 Main Struggles & How They Were Resolved

- **Problem:** When trying to register the tool, the server returned `task not found: negotiations (AI_Devs 3)`.
  - **Root Cause:** I mistakenly directed the registration payload to `https://centrala.ag3nts.org/report` and `https://centrala.ag3nts.org/verify`. The actual endpoint for `/verify` actions for this specific system was hosted on `https://hub.ag3nts.org/verify`.
  - **Resolution:** Tested various endpoints present in older lesson files with Python `requests` to see their responses. Once the discrepancy between `centrala.ag3nts.org` and `hub.ag3nts.org` was identified, the URLs in `register.py` and `check_flag.py` were updated, and the registration succeeded.
  - **Takeaway:** Always double-check the domain names in the task descriptions, especially when transitioning between tasks that use `centrala.ag3nts.org` for flags and `hub.ag3nts.org` for verifying tools or webhooks.

- **Problem:** The Flask server crashed on startup with `FileNotFoundError: [Errno 2] No such file or directory: 'csvs/items.csv'`.
  - **Root Cause:** The `server.py` script used relative paths (e.g., `open("csvs/items.csv")`). When the user ran the script from the project root (`C:\zz_projects\ai_devs4_part2`), Python looked for the `csvs` directory in the root instead of inside `s3\s3e4`.
  - **Resolution:** Modified the file operations to use absolute paths based on the script's location: `os.path.join(os.path.dirname(__file__), "csvs", "items.csv")`.
  - **Takeaway:** Never rely on the current working directory for file loading in scripts. Always use `__file__` or `pathlib` for absolute pathing.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

### 4a. What the User Did Well
- **Environment Management:** Explicitly requested the agent not to create a new virtual environment but to use the existing `.venv`, preventing environment sprawl.
- **Clear Error Reporting:** When `ngrok` failed, the user pasted the exact PowerShell error (`CommandNotFoundException`), allowing the agent to immediately identify that the `winget` installation needed a new PowerShell window or was using the wrong package name.

### 4b. What Could Be Improved (User Side)
- The user's specification of the model `openai/gpt-5.4-mini` was likely a typo for `gpt-4o-mini`. While it didn't strictly break the OpenRouter fallback, ensuring exact model strings prevents API routing errors.

### 4c. What the Coding Agent Did Well
- Effectively used Python scripts to probe the Centrala API endpoints when debugging the `task not found` error, testing `/report`, `/verify`, and different domains systematically.
- Re-used the user's local `.venv` executable paths (`.\.venv\Scripts\python.exe`) correctly in all terminal command suggestions.

### 4d. What the Coding Agent Could Improve
- Missed the `hub.ag3nts.org` vs `centrala.ag3nts.org` distinction initially, causing a delay in registration.
- Used fragile relative paths initially when building the data loader, requiring a manual fix later.

### 4e. Recommended Prompting Patterns for Next Time
> "Please ensure all file loading in Python scripts uses absolute paths relative to `__file__`."
> "When making API calls to central systems, please cross-reference the exact base URL (hub vs centrala) from the task markdown file."

---

## 5. 💡 Agentic Patterns Observed

- **Tool Use (Reversed):** In this task, we built the tool for another agent rather than building the agent itself. This is a great exercise in designing strict, error-resistant schema boundaries.
- **LLM-as-a-Function:** Instead of complex text retrieval (RAG) or fuzzy string matching algorithms, we used the LLM strictly as a text transformation function (natural language -> exact CSV key), relying on the LLM's vast context window to hold all 2139 items.

---

## 6. 🔁 What Would You Do Differently

- **Prototyping:** I would test the tool's LLM chain in an isolated script first to ensure it successfully maps edge-case natural language queries before wrapping it in Flask.
- **File Paths:** Implement `pathlib` from the very first draft of `server.py`.
- **API Endpoints:** Extract the Centrala/Hub URLs into variables in `.env` or at the top of the scripts to make switching between them during debugging much easier.

---

## 7. 🧠 Key Learnings

> **Robust File Paths:** Relying on relative paths like `"csvs/items.csv"` is brittle. Always anchor paths using `os.path.dirname(__file__)` to ensure scripts can be run from anywhere.
> **AI_Devs4 Endpoints:** The ecosystem separates reporting flags (`centrala.ag3nts.org/report`) from tool/webhook verification (`hub.ag3nts.org/verify`). Pay close attention to the domain in the task description.
> **LLM Context for Matching:** Modern LLMs easily handle 12k+ token context windows. Passing a 2000+ item list directly into the prompt for exact matching is highly effective and often faster to implement than setting up a local vector database or TF-IDF fuzzy matcher.

---

## 8. 📦 Reusable Artifacts

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `server.py` | `s3/s3e4/server.py` | Acts as a boilerplate for standing up a quick Flask API that uses LangChain to process input parameters. |
| `register.py` | `s3/s3e4/register.py` | Contains the exact payload structure needed to register an external tool URL with the Hub. |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S03E04` |
| Date completed | `2026-06-11` |
| LangSmith project | `N/A` |
| Models used | `openai/gpt-5.4-mini` (via OpenRouter) |
| Approx. number of agent turns | `7` |
| Hardest part (one line) | Debugging the `task not found` error due to confusing `hub.ag3nts.org` with `centrala.ag3nts.org`. |
| Overall complexity estimate | `Medium` |
