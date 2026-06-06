# 📦 Nexus Supply Co. — Operations Assistant

> An intelligent, dual-agent system that automatically resolves customer inquiries by looking up live order records and searching internal company policy documents — all powered by local AI.

---

## 🏗️ High-Level Architecture

![High-Level Architecture Diagram](./high_level_diagram.png)

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Agent Orchestration | [CrewAI](https://www.crewai.com/) |
| Tool Protocol | [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) via FastMCP |
| LLM Engine | [Ollama](https://ollama.com/) — local `qwen2.5` model |
| Testing | [Pytest](https://pytest.org/) |
| Language | Python 3.11+ |

---

## 🔄 End-to-End Workflow

```
User Inquiry
     │
     ▼
 crew.py ──► MCPServerAdapter ──► FastMCP Server (server.py)
     │                                     │
     │                              Exposes 3 MCP tools
     │
     ├──► Operations Researcher Agent
     │         Tools: read_record, search_documents
     │         Calls tools → Returns raw facts
     │
     └──► Report Writer Agent (receives Researcher's context)
               Tool: save_report
               Writes cited Markdown report → output/
```

1. **User Inquiry** — A natural language question is submitted (e.g., *"What is the status of ORD-1005 and what is the return policy for damaged items?"*).
2. **Operations Researcher Agent** runs first:
   - Calls `read_record("ORD-1005")` → fetches live order data from `data/records.csv`.
   - Calls `search_documents("damaged")` → scans `documents/` for policy excerpts.
   - Calls `search_documents("return")` → gathers return policy details.
   - Outputs strictly factual, cited tool results — **never guesses**.
3. **Report Writer Agent** runs second:
   - Receives the Researcher's findings via `context=[research_task]`.
   - Formats a professional, cited Markdown report (≤300 words).
   - Calls `save_report(title, content)` → saves final `.md` file into `output/`.
4. **Trace Logger** captures every tool call, argument, and result into `traces/trace_TIMESTAMP.json` for full auditability.

---

## 🗂️ Project Structure

```
operations-assistant/
│
├── crew.py                  # Main entry point — defines agents, tasks, crew
├── server.py                # FastMCP server exposing the 3 MCP tools
│
├── data/
│   └── records.csv          # Order records database (ORD-1001 to ORD-1020)
│
├── documents/               # 10 internal policy & support documents
│   ├── return_policy.txt
│   ├── shipping_policy.txt
│   ├── payment_terms.txt
│   ├── warehouse_guidelines.txt
│   ├── vendor_policy.txt
│   ├── product_catalog.txt
│   ├── company_overview.txt
│   └── support_ticket_001/002/003.txt
│
├── tests/
│   ├── test_tools.py        # 22 Pytest unit tests for all 3 MCP tools
│   └── test_server.py       # Integration-level server tests
│
├── output/                  # Auto-generated Markdown reports (git-ignored)
├── traces/                  # Execution trace JSON logs (git-ignored)
│
├── high_level_diagram.png   # Architecture overview diagram
├── low_level_diagram.png    # Technical component diagram
├── DECISION_LOG.md          # Engineering decisions & rationale
├── requirements.txt         # Locked Python dependencies
├── .env.example             # Environment config template
└── .gitignore
```

---

## 🔧 MCP Tools Reference

| Tool | Agent | Description |
|---|---|---|
| `read_record(order_id)` | Researcher only | Looks up a single order by ID from `records.csv`. Returns all order fields with source citation. |
| `search_documents(query)` | Researcher only | Full-text searches all `.txt` files in `documents/`. Returns matching excerpts with source filenames. |
| `save_report(title, content)` | Writer only | Sanitizes the title, timestamps the filename, and saves a Markdown report to `output/`. |

---

## 🚧 Key Engineering Challenges & Solutions

| # | Challenge | Solution |
|---|---|---|
| 1 | **Agent infinite loops** — both agents had all 3 tools, causing the Researcher to save reports and the Writer to re-research, looping indefinitely. | Segregated tools at initialization: `researcher_tools = [read_record, search_documents]`, `writer_tools = [save_report]`. |
| 2 | **MCP stdio corruption** — `print()` statements in `server.py` polluted the JSON-RPC stream, crashing tool parsing. | Rerouted all server logs to `sys.stderr`, keeping `stdout` clean for MCP protocol traffic. |
| 3 | **ReAct formatting failures** — local `qwen2.5` model couldn't reliably follow CrewAI's `Thought: / Action: / Action Input:` text format. | Enabled `function_calling_llm` on both agents, bypassing text-based ReAct in favour of native JSON tool-calling schemas. |
| 4 | **Windows encoding crashes** — CrewAI outputs rich Unicode/emojis which caused `UnicodeEncodeError` on default Windows console encoding. | Added `sys.stdout.reconfigure(encoding='utf-8')` at script startup. |
| 5 | **Subprocess Python mismatch** — `SERVER_PARAMS` using `"python"` picked the system Python, which lacked `mcp` package. | Replaced with `sys.executable` to guarantee the subprocess inherits the correct virtual environment. |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) installed and running locally

```powershell
# Pull the model
ollama pull qwen2.5
```

### Installation

```powershell
# 1. Clone the repo and enter the directory
cd operations-assistant

# 2. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate

# 3. Install all dependencies
pip install -r requirements.txt

# 4. Set up environment variables
copy .env.example .env
```

### Environment Variables (`.env`)

```env
OLLAMA_BASE_URL=http://localhost:11434
MODEL_NAME=ollama/qwen2.5
```

### Run the Assistant

```powershell
# Default inquiry
python crew.py

# Custom inquiry
python crew.py "What is the status of order ORD-1005 and the return policy for damaged items?"
```

Reports are saved to `output/` and traces to `traces/`.

---

## 🧪 Testing

The project ships with **27 tests** across two test files covering all tool functions, validation logic, and edge cases.

```powershell
# Run all tests with verbose output
python -m pytest tests/ -v
```

| Test File | Tests | Covers |
|---|---|---|
| `tests/test_tools.py` | 22 | Full edge case coverage for all 3 MCP tools |
| `tests/test_server.py` | 5 | Integration-level server tool tests |

---

## 📋 Decision Log

All major architectural and configuration decisions are documented in [`DECISION_LOG.md`](./DECISION_LOG.md), including rationale for each technical choice made during development.
