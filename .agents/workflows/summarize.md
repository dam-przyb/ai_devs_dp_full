---
description: Summarize work on current task
---

# Task Summary Generation — Reusable Prompt

> **Usage:** Run this prompt at the end of every AI_Devs4 lesson task.  
> The coding agent will generate a `s<lesson>e<task>_summary.md` file in the relevant task folder (e.g. `tasks/s01e02/s01e02_summary.md`).

---

## Prompt

```
You are a reflective technical writer summarizing the completion of an AI_Devs4 lesson task.
Review the entire conversation, all code written, errors encountered, and decisions made during this session.

Generate a structured summary file in Markdown. Be specific and honest — this document is an educational artifact, not a status report. Vague statements like "the agent worked well" are not acceptable. Use concrete examples, reference actual code, and name real problems.

---

## 1. 🎯 What Was Accomplished

Describe what the task required and what was actually built or solved.
- State the task goal in one sentence.
- List deliverables produced (files, scripts, agent graphs, chains, etc.).
- Note any scope that was intentionally skipped or deferred, and why.

---

## 2. 🏗️ How the Agent / Solution Was Constructed

Provide a clear architectural walkthrough of what was built.

### 2a. Architecture Overview
Describe the high-level design: Was it a simple chain? A LangGraph graph? A tool-using agent? Draw a short ASCII diagram if helpful.

### 2b. Key Components
For each significant component (graph nodes, tools, chains, prompts), provide:
- Its purpose in one sentence
- A representative code snippet

Example format:
#### `<ComponentName>`
**Purpose:** <what it does>
```python
# snippet
```

### 2c. Data & Control Flow
Describe how data moves through the system: input → processing steps → output.

---

## 3. 🧱 Main Struggles & How They Were Resolved

Be specific. Generic statements are not useful here.

For each significant problem encountered:
- **Problem:** What went wrong or was unclear.
- **Root Cause:** Why it happened (model behavior, API quirk, design flaw, missing context, etc.).
- **Resolution:** How it was fixed, or if it wasn't — what was tried and why it remains open.
- **Takeaway:** What this means for future tasks of similar type.

---

## 4. 🤝 User ↔ Coding Agent Interaction Assessment

Critically assess the quality of collaboration in this session.

### 4a. What the User Did Well
List specific instructions or decisions by the user that made the agent's work easier or more accurate.

### 4b. What Could Be Improved (User Side)
Be constructive and specific. Examples of what to look for:
- Instructions that were too vague or ambiguous
- Missing context that caused the agent to make wrong assumptions
- Cases where the user had to correct the agent multiple times on the same point
- Over-correction or micro-management that slowed things down

### 4c. What the Coding Agent Did Well
List moments where the agent added genuine value beyond mechanical execution (e.g. caught a design flaw, suggested a better pattern, self-corrected).

### 4d. What the Coding Agent Could Improve
Name any recurring failure modes observed in this session (e.g. hallucinated API signatures, ignored instructions after context grew, over-engineered solutions).

### 4e. Recommended Prompting Patterns for Next Time
Based on this session, write 2–4 concrete prompt patterns or instructions the user should apply in the next task. Format as ready-to-use instruction snippets.

---

## 5. 💡 Agentic Patterns Observed

Identify which agentic design patterns appeared in this task (even implicitly). For each:
- **Pattern name** (e.g. ReAct, Reflection, Tool Use, Human-in-the-Loop, Map-Reduce, Subagent Delegation)
- **How it manifested** in this task
- **Assessment:** Did it work well here? Any limitations observed?

---

## 6. 🔁 What Would You Do Differently

If you were to redo this task from scratch with the knowledge gained:
- What design decisions would change?
- What would you prototype first?
- What would you skip or simplify?

---

## 7. 🧠 Key Learnings

List 3–7 concrete, transferable learnings from this task. These should be specific enough to be actionable in a future task. Avoid platitudes.

Format each as:
> **[Topic]:** <specific insight>

Examples of acceptable specificity:
> **LangGraph state:** Passing mutable lists in TypedDict state between nodes requires explicit copying — mutations propagate unexpectedly.  
> **OpenRouter:** Model `mistral/mistral-7b-instruct` does not reliably follow JSON output instructions without `response_format` enforcement.

---

## 8. 📦 Reusable Artifacts

List any code, prompts, utilities, or patterns produced in this task that are worth extracting for reuse in future tasks.

| Artifact | Location | Why It's Reusable |
|----------|----------|-------------------|
| `<name>` | `<path>` | `<reason>` |

---

## 9. 📊 Session Snapshot

| Field | Value |
|-------|-------|
| Lesson / Task | `S__E__` |
| Date completed | `YYYY-MM-DD` |
| LangSmith project | `<project name>` |
| Models used | `<list>` |
| Approx. number of agent turns | `<n>` |
| Hardest part (one line) | `<text>` |
| Overall complexity estimate | `Low / Medium / High` |

---

Save this file as `s<lesson>e<task>_summary.md` inside the task folder (e.g. `tasks/s01e02/s01e02_summary.md`).
Do not omit any section. If a section truly does not apply, write one sentence explaining why.
```