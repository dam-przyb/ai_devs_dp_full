# AI_Devs 4: Builders — Course Project Solutions

Welcome to the repository containing solutions and interactive agents for the **AI_Devs 4: Builders** course. This course is dedicated to advanced human-AI cooperation, agentic design, stateful workflows, and programmatic LLM orchestrations.

---

## 🎯 Course & Repository Overview

This project serves as a comprehensive workspace for implementing state-of-the-art agent systems. Using **Python**, **LangChain/LCEL**, and **LangGraph**, we have developed tools and workflows to solve complex programmatic challenges presented throughout the course.

The repository is structured into weekly/seasonal lessons (`s2`, `s3`, `s4`, `s5`), each containing individual exercise folders (`s<season>e<episode>`).

---

## 📂 Repository Structure

Each lesson folder (`sX/sXeY`) follows a structured format:
- **`sXeYtaskdescription.txt`**: The original instructions (in Polish) defining the challenge constraints.
- **`sXeY_summary.md`**: Educational retrospective detailing architectural designs, struggles, learnings, and prompting patterns discovered during that specific exercise.
- **Source Scripts**:
  - `explore_<name>.py`: Lightweight probes to extract schema, verify endpoints, and read documentation before coding.
  - `solve_<name>.py` / `timetravel_assistant.py` / `transcribe_final.py`: The executable agents or CLI workflows implementing the solution.
- **`run_log/`**: JSON execution histories, transcripts, and media files generated during runtime.

### Summary of Season 5 Exercises:
*   **S5E1 (Garden & Workspaces)**: Initial configuration of localized environments.
*   **S5E2 (Voice Transcription & Phonecall Interaction)**: Handled audio conversion and automated a conversation flow with the system operator to disable monitor controls.
*   **S5E3 (Shell Access & Expansion)**: Expanded functionality on remote servers.
*   **S5E4 (Goingthere Rocket Navigation)**: Optimized trajectories and navigated real-time endpoints for payload delivery.
*   **S5E5 (Chronos-P1 Time Travel Assistant)**: Developed a human-in-the-loop CLI assistant to calculate temporal coordinates, decode stabilization hints, and monitor `internalMode` loops in coordination with the web interface.

---

## 🛠️ Tech Stack & Standards

- **Core Runtime**: Python 3.11+ (using virtual environment `.venv`)
- **Orchestration**: LangChain & LangGraph (StateGraph pipelines, LCEL)
- **Model Provider**: OpenRouter API (`openai/gpt-5-mini` / Claude models)
- **Observability**: LangSmith (`LANGCHAIN_TRACING_V2=true`)
- **Coding Standards**: PEP 8 compliance, Black formatting, and type hints.

---

## 🚀 Setup & Execution

### 1. Prerequisites
Ensure you have Python 3.11+ installed.

### 2. Configure Environment Variables
Create a `.env` file in the root directory (never commit secrets) with the following parameters:
```env
AIDEVSKEY=your_aidevs_key
OPENROUTER_API_KEY=your_openrouter_key
LANGCHAIN_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ai_devs4_builders
```

### 3. Run a Solution (e.g. S5E5 Time Travel)
Each task can be executed from the root folder. For example, to launch the S5E5 interactive coordinator:
```powershell
python s5/s5e5/timetravel_assistant.py
```
Follow the terminal prompt instructions to coordinate with the machine's Web interface.
