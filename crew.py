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
        logged_tools = []
        for t in tools:
            original_run = t._run
            def wrapped_run(self, *args, **kwargs):
                entry = {"tool": self.name, "args": kwargs or args}
                tool_calls_log.append(entry)
                print(f"\n>>> TOOL CALLED: {self.name} | args: {kwargs or args}")
                result = original_run(*args, **kwargs)
                print(f">>> TOOL RESULT: {str(result)[:200]}")
                return result
            t._run = types.MethodType(wrapped_run, t)
            logged_tools.append(t)

        # ── Researcher ─────────────────────────────────────────
        researcher = Agent(
            role="Operations Researcher",
            goal=(
                "Use tools to find facts. "
                "Call read_record for any order ID. "
                "Call search_documents with single words like "
                "'damaged', 'return', 'refund', 'shipping'. "
                "Never invent information."
            ),
            backstory=(
                "You are a data analyst who ONLY uses tool results. "
                "You always call tools before answering. "
                "You call read_record when you see an order ID like ORD-1005. "
                "You call search_documents with ONE short word at a time. "
                "You never assume or guess."
            ),
            tools=logged_tools,
            llm=my_llm,
            function_calling_llm=my_llm,
            verbose=True,
            max_iter=10,
            allow_delegation=False,
            max_retry_limit=3,
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
                "You always call save_report at the end."
            ),
            tools=logged_tools,
            llm=my_llm,
            function_calling_llm=my_llm,
            verbose=True,
            max_iter=5,
            allow_delegation=False,
        )

        # ── Research Task ──────────────────────────────────────
        research_task = Task(
            description=(
                f"QUESTION: {question}\n\n"
                f"You MUST use tools. Do these steps in order:\n"
                f"1. Does the question have an order ID like ORD-XXXX? "
                f"If yes → call read_record tool with that order_id NOW.\n"
                f"2. Call search_documents tool with the word 'damaged'.\n"
                f"3. Call search_documents tool with the word 'return'.\n"
                f"4. Report exactly what each tool returned, nothing more."
            ),
            expected_output=(
                "A list of TOOL/RESULT pairs showing exactly what "
                "each tool returned. Minimum 2 tool calls required."
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
                f"5. Under 300 words."
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