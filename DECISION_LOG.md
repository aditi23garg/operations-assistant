# Decision Log: Operations Assistant Mini-Project

## Architecture and Configuration Decisions

### 1. Fixing the MCP Server Transport
- **Decision:** Redirected standard prints in `server.py` to `sys.stderr` (`print(..., file=sys.stderr)`).
- **Rationale:** CrewAI uses `stdio` to communicate with the FastMCP server. If standard print statements pollute the standard output with non-JSON strings, the MCP protocol breaks entirely, and CrewAI agents cannot parse the tools. By routing application logs to `stderr`, `stdout` remains pristine for the JSON-RPC communication.

### 2. Resolving Subprocess and Environment Conflicts
- **Decision:** Updated `SERVER_PARAMS.command` from `"python"` to `sys.executable`.
- **Rationale:** Calling `"python"` in the subprocess defaulted to the system's global Python installation, which did not have the `mcp` library installed. `sys.executable` guarantees that the subprocess runs in the exact same virtual environment as the parent CrewAI script.

### 3. Handling Windows Console Encodings
- **Decision:** Forced `sys.stdout.reconfigure(encoding='utf-8')` at the top of the script.
- **Rationale:** CrewAI outputs rich emojis during execution. The default Windows command line often runs on the `charmap` codec, causing fatal `UnicodeEncodeError` crashes upon script start.

### 4. Overriding Text-Based ReAct Tool Prompts
- **Decision:** Added `function_calling_llm=my_llm` to the Agent configurations and instantiated `crewai.LLM` natively instead of passing model strings.
- **Rationale:** Smaller local models like Ollama's `mistral` and `qwen2.5` struggle to reliably follow CrewAI's forced text-based `ReAct` formatting (e.g. `Thought: / Action: / Action Input:`). By explicitly enabling `function_calling_llm`, CrewAI bypasses ReAct prompts and natively injects the MCP tools into the model's native `/api/chat` function-calling schema, resulting in flawless tool execution without text hallucinations.

### 5. Safe Tool Logging
- **Decision:** Implemented a safe `types.MethodType` monkey-patch to capture tool execution traces.
- **Rationale:** The original attempt to manually map `tool._run` mutated the Pydantic tool structures improperly, preventing the underlying schema from accurately reflecting the `args_schema`. This caused CrewAI to lose the expected tool arguments. The refined wrapper ensures tool logging captures exact inputs without interrupting Pydantic's underlying schemas.
