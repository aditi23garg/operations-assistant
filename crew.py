# crew.py - Nexus Supply Co. Operations Assistant
# Uses LiteLLM + Ollama with explicit ReAct prompting

import json
import os
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from datetime import datetime
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from crewai_tools import MCPServerAdapter
from dotenv import load_dotenv
from mcp import StdioServerParameters

load_dotenv()

BASE_DIR   = Path(__file__).parent
TRACES_DIR = BASE_DIR / "traces"
TRACES_DIR.mkdir(exist_ok=True)

MODEL_NAME      = os.getenv("MODEL_NAME", "ollama/qwen2.5")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

if MODEL_NAME.startswith("ollama/"):
    MODEL_NAME = "ollama_chat/" + MODEL_NAME.split("/", 1)[1]

from crewai import LLM
my_llm = LLM(
    model=MODEL_NAME,
    base_url=OLLAMA_BASE_URL
)

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=["server.py"],
    env=None
)


def save_trace(question: str, result: str, tool_calls: list):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    trace = {
        "timestamp":  timestamp,
        "question":   question,
        "tool_calls": tool_calls,
        "result":     result,
    }
    trace_file = TRACES_DIR / f"trace_{timestamp}.json"
    trace_file.write_text(
        json.dumps(trace, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print(f"\nTrace saved → traces/trace_{timestamp}.json")


def run_crew(question: str) -> str:

    print(f"\n{'='*60}")
    print(f"Question: {question}")
    print(f"{'='*60}\n")

    tool_calls_log = []

    with MCPServerAdapter(SERVER_PARAMS) as tools:

        tool_names = [t.name for t in tools]
        print(f"MCP tools available: {tool_names}\n")

        import types
        researcher_tools = []
        writer_tools = []
        for t in tools:
            def make_wrapper(orig_run, tool_name):
                def wrapped_run(self, *args, **kwargs):
                    entry = {"tool": tool_name, "args": kwargs or args}
                    tool_calls_log.append(entry)
                    print(f"\n>>> TOOL CALLED: {tool_name} | args: {kwargs or args}")
                    result = orig_run(*args, **kwargs)
                    print(f">>> TOOL RESULT: {str(result)[:200]}")
                    return result
                return wrapped_run
            t._run = types.MethodType(make_wrapper(t._run, t.name), t)
            if t.name in ["read_record", "search_documents", "search_orders"]:
                researcher_tools.append(t)
            elif t.name == "save_report":
                writer_tools.append(t)

        # ── Pre-detect order ID and extract keywords (Python, not LLM) ──
        import re
        order_id_match = re.search(r'ORD-\d+', question, re.IGNORECASE)
        detected_order_id = order_id_match.group(0).upper() if order_id_match else None

        # Extract meaningful keywords from the question (skip stop-words)
        STOP_WORDS = {
            'what', 'is', 'the', 'are', 'there', 'any', 'for', 'and', 'our',
            'how', 'do', 'does', 'a', 'an', 'of', 'in', 'to', 'with', 'if',
            'i', 'we', 'can', 'could', 'would', 'should', 'under', 'over',
            'about', 'that', 'this', 'have', 'has', 'be', 'been', 'was',
        }
        raw_words = re.findall(r'[a-z]+', question.lower())
        keywords = [w for w in raw_words if w not in STOP_WORDS and len(w) > 3]
        # Deduplicate while preserving order, limit to 2
        seen = set()
        search_keywords = []
        for w in keywords:
            if w not in seen:
                seen.add(w)
                search_keywords.append(w)
            if len(search_keywords) == 2:
                break
        if not search_keywords:
            search_keywords = ['policy']

        # Detect if user is asking for orders by status (e.g. "currently processing")
        status_match = re.search(r'\b(processing|pending|shipped|delivered|refunded)\b', question, re.IGNORECASE)
        detected_status = status_match.group(1).capitalize() if status_match else None

        # Compute exact number of tool calls (used by agent max_iter + task prompt)
        expected_tool_calls = len(search_keywords) + (1 if detected_order_id else 0) + (1 if detected_status else 0)

        # ── Researcher ─────────────────────────────────────────
        researcher = Agent(
            role="Operations Researcher",
            goal=(
                "Use tools to find facts. "
                "Call read_record ONLY when an order ID is explicitly given. "
                "Call search_documents with single relevant words. "
                "Never invent information."
            ),
            backstory=(
                "You are a data analyst who ONLY uses tool results. "
                "You never call read_record unless an order ID like ORD-XXXX is present. "
                "You call search_orders to find orders by their status. "
                "You call search_documents with ONE short word at a time. "
                "You never assume or guess."
            ),
            tools=researcher_tools,
            llm=my_llm,
            function_calling_llm=my_llm,
            verbose=True,
            max_iter=expected_tool_calls + 1,  # exactly enough: tools + 1 final answer step
            allow_delegation=False,
            max_retry_limit=2,
        )

        # ── Writer ─────────────────────────────────────────────
        writer = Agent(
            role="Report Writer",
            goal=(
                "Write a markdown report from researcher findings only. "
                "Call save_report to save it. "
                "Cite sources for every fact."
            ),
            backstory=(
                "You write concise reports. "
                "You only use facts the researcher found. "
                "You never infer specific order status from general policy or support ticket documents. "
                "Order statuses can only come from records.csv via read_record. "
                "You always call save_report at the end."
            ),
            tools=writer_tools,
            llm=my_llm,
            function_calling_llm=my_llm,
            verbose=True,
            max_iter=3,
            allow_delegation=False,
        )

        # ── Research Task (dynamically built) ─────────────────
        task_steps = []
        step_num = 1
        if detected_order_id:
            task_steps.append(
                f"{step_num}. Call read_record with order_id='{detected_order_id}'."
            )
            step_num += 1
        else:
            task_steps.append(
                f"{step_num}. SKIP read_record — there is NO order ID in this question. "
                f"Do NOT call read_record under any circumstances."
            )
            step_num += 1
            
        if detected_status:
            task_steps.append(
                f"{step_num}. Call search_orders with query='{detected_status}'."
            )
            step_num += 1
            
        for kw in search_keywords:
            task_steps.append(
                f"{step_num}. Call search_documents with query='{kw}'."
            )
            step_num += 1
        task_steps.append(
            f"{step_num}. STOP — do NOT call any more tools. "
            f"Report exactly what each tool returned, nothing more."
        )
        steps_text = "\n".join(task_steps)

        research_task = Task(
            description=(
                f"QUESTION: {question}\n\n"
                f"You MUST follow these steps EXACTLY — {expected_tool_calls} tool call(s) total, then stop:\n"
                f"{steps_text}"
            ),
            expected_output=(
                f"Exactly {expected_tool_calls} TOOL/RESULT pair(s). "
                "List what each tool returned word-for-word. No extra tool calls."
            ),
            agent=researcher,
        )

        # ── Write Task ─────────────────────────────────────────
        write_task = Task(
            description=(
                f"Using the researcher's TOOL RESULTS above, "
                f"write a markdown report for:\n\n"
                f"QUESTION: {question}\n\n"
                f"Rules:\n"
                f"1. Only use facts from tool results.\n"
                f"2. Cite source after every fact e.g. [Source: return_policy.txt]\n"
                f"3. Add a ## Sources section at the end.\n"
                f"4. Call save_report tool with title and content.\n"
                f"5. Under 300 words.\n"
                f"6. If the question asks about specific orders but no order records were read (e.g. no order ID was provided), explicitly state that no processing order information was found in the documents and records.csv must be checked directly. Do NOT guess or infer order status from support tickets."
            ),
            expected_output=(
                "Confirmation that save_report was called with the filename."
            ),
            agent=writer,
            context=[research_task],
        )

        # ── Run ────────────────────────────────────────────────
        crew = Crew(
            agents=[researcher, writer],
            tasks=[research_task, write_task],
            process=Process.sequential,
            verbose=True,
        )

        result     = crew.kickoff()
        result_str = str(result)

        save_trace(question, result_str, tool_calls_log)

        print(f"\n{'='*60}")
        print(f"Tool calls made: {len(tool_calls_log)}")
        for tc in tool_calls_log:
            print(f"  → {tc['tool']}({tc['args']})")
        print(f"{'='*60}")
        print("\nFINAL ANSWER:")
        print(result_str)

        return result_str


if __name__ == "__main__":
    question = (
        " ".join(sys.argv[1:])
        if len(sys.argv) > 1
        else "What is the status of order ORD-1005 and what is our return policy for damaged items?"
    )
    run_crew(question)