---
trigger: always_on
---

# Copilot Instructions — AI_Devs4 Project

## Project Overview

This project is part of the **AI_Devs4** course, focused on effective human–AI cooperation and the design of agentic systems and solutions. The codebase uses Python as the primary language and relies on the LangChain ecosystem for building, orchestrating, and observing AI agents.

---

## Coding Standards & Language

- **Language:** Python 3.11+
- **Style:** Follow PEP 8. Use type hints everywhere (`def foo(bar: str) -> int:`).
- **Docstrings:** Use Google-style docstrings for all functions and classes.
- **Formatting:** Code must be compatible with `black` formatter and `ruff` linter.
- **Async:** Prefer `async/await` patterns for I/O-bound operations (LLM calls, API requests).

---

## Core Frameworks & Libraries

### LangChain
- Use `langchain` as the primary abstraction layer for chains, prompts, and document loaders.
- Prefer **LCEL (LangChain Expression Language)** (`|` pipe syntax) for composing chains.
- Use `ChatPromptTemplate` and `MessagesPlaceholder` for structured prompt management.
- Avoid legacy `LLMChain` — always use LCEL equivalents.

### LangGraph
- Use `langgraph` for designing **stateful, multi-step agentic workflows**.
- Model agent logic as explicit **graphs**: define `StateGraph`, nodes, and edges clearly.
- Use `TypedDict` or `dataclasses` for graph state definitions.
- Prefer conditional edges (`add_conditional_edges`) for branching logic over nested if-chains.
- Always define a clear `END` node; avoid infinite loops — implement cycle detection or iteration limits.
- Document each node's responsibility in a docstring or inline comment.

### LangSmith
- All runs must be **traced via LangSmith** for observability.
- Set the following environment variables (loaded from `.env`):
  ```
  LANGCHAIN_TRACING_V2=true
  LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
  LANGCHAIN_API_KEY=<from .env>
  LANGCHAIN_PROJECT=<project name>
  ```
- Use `@traceable` decorator on custom functions that should appear in traces.
- Add meaningful `run_name` and `tags` to chain invocations for easier filtering in LangSmith UI.

---

## LLM Provider — OpenRouter

- **All LLM calls go through OpenRouter.**
- Use `ChatOpenAI` from `langchain_openai`, pointed at the OpenRouter base URL:

  ```python
  from langchain_openai import ChatOpenAI

  llm = ChatOpenAI(
      model="openai/gpt-5-mini",          # or any OpenRouter-supported model
      openai_api_key=os.getenv("OPENROUTER_API_KEY"),
      openai_api_base="https://openrouter.ai/api/v1",
  )
  ```

- The API key is stored in `.env` as `OPENROUTER_API_KEY`. **Never hardcode keys.**
- Load environment variables at the top of each entry-point file:
  ```python
  from dotenv import load_dotenv
  load_dotenv()
  ```
- When switching models, change only the `model` string — keep the base URL and key pattern intact.
- Prefer models available on OpenRouter that support **tool/function calling** when building tool-using agents.

---

## Core/Example Project Structure (may differ depending on task)

```
project/
├── .env                    # API keys and env config (never commit)
├── .env.example            # Template with key names, no values
├── agents/                 # LangGraph agent definitions
│   ├── __init__.py
│   └── <agent_name>.py
├── chains/                 # LCEL chains
│   ├── __init__.py
│   └── <chain_name>.py
├── tools/                  # Custom LangChain tools
│   ├── __init__.py
│   └── <tool_name>.py
├── prompts/                # Prompt templates (.py or .yaml)
├── utils/                  # Shared helpers (loaders, parsers, etc.)
├── tasks/                  # AI_Devs4 task solutions
│   └── taskXX/
├── notebooks/              # Exploratory Jupyter notebooks
├── tests/                  # Unit and integration tests
│   └── test_<module>.py
├── main.py                 # Entry point
└── requirements.txt
```

---

## Agent Design Principles

1. **Single Responsibility:** Each node in a LangGraph graph should do one thing.
2. **Tool Use:** Define tools using `@tool` decorator or `StructuredTool.from_function()`. Include clear `description` fields — the LLM uses them for routing.
3. **Memory:** Use `ConversationBufferMemory` or `LangGraph` checkpointers (`MemorySaver`) for persistence.
4. **Error Handling:** Wrap LLM calls in `try/except`. Implement retry logic with `tenacity` for transient API errors.
5. **Human-in-the-Loop:** For tasks requiring confirmation, use LangGraph's `interrupt_before` / `interrupt_after` mechanisms.
6. **Structured Output:** Prefer `.with_structured_output(PydanticModel)` over manual JSON parsing.


## Dependencies

Keep `requirements.txt` up to date. Core dependencies:

```
langchain
langchain-openai
langchain-community
langgraph
langsmith
python-dotenv
pydantic>=2.0
tenacity
```

---

## Testing

- Write tests with `pytest`.
- Mock LLM calls in unit tests using `langchain_core.runnables.fake.FakeListChatModel` or `unittest.mock`.
- Integration tests may make real API calls — mark them with `@pytest.mark.integration` and skip by default in CI.

---

## What to Avoid

- ❌ Do not use deprecated `LLMChain`, `ConversationalRetrievalChain`, or `initialize_agent` — use LCEL and LangGraph instead.
- ❌ Do not hardcode model names as magic strings throughout the codebase — define them in a config or constants file.
- ❌ Do not commit `.env` files or any secrets.
- ❌ Do not use synchronous `requests` for external calls inside async contexts — use `httpx` with `async with`.
- ❌ Do not ignore LangSmith traces — review them during debugging before adding print statements.
- ❌ Do not delete ANY files without strict permission.
- ❌ Do not save files in root folder of the project without strict permission - keep lesson folder context.