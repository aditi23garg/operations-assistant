# server.py
# The MCP server for Nexus Supply Co. Operations Assistant
# Exposes 3 tools: search_documents, read_record, save_report

import csv
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ─────────────────────────────────────────
# Load environment variables from .env file
# ─────────────────────────────────────────
load_dotenv()

# ─────────────────────────────────────────
# Define paths to our data folders
# ─────────────────────────────────────────
BASE_DIR     = Path(__file__).parent          # root of the project
DOCS_DIR     = BASE_DIR / "documents"         # where .txt files live
DATA_DIR     = BASE_DIR / "data"              # where records.csv lives
OUTPUT_DIR   = BASE_DIR / "output"            # where reports get saved
CSV_FILE     = DATA_DIR / "records.csv"       # the orders spreadsheet

# ─────────────────────────────────────────
# Create the MCP server
# ─────────────────────────────────────────
mcp = FastMCP("nexus-ops-server")


# ═══════════════════════════════════════════════════════
# TOOL 1: search_documents
# Searches all .txt files in documents/ for a query term
# ═══════════════════════════════════════════════════════
@mcp.tool()
def search_documents(query: str) -> str:
    """
    Search all documents in the documents folder for a given query.
    Returns matching excerpts with the source file name.
    Use this to find policies, product info, or support history.
    For best results use single words like 'damaged', 'return', 'shipping'.

    Args:
        query: The search term or phrase to look for.
    """
    if isinstance(query, dict):
        query = query.get("query", "")

    if not query or not query.strip():
        return "ERROR: query must be a non-empty string."

    if len(query) > 200:
        return "ERROR: query is too long. Keep it under 200 characters."

    if not DOCS_DIR.exists():
        return "ERROR: documents folder not found."

    query_clean = query.strip().lower()

    # Split into individual words so multi-word queries still find matches
    # e.g. "return policy damaged" matches lines containing ANY of those words
    query_words = [w for w in query_clean.split() if len(w) > 2]
    if not query_words:
        query_words = [query_clean]

    results = []

    for filepath in sorted(DOCS_DIR.glob("*.txt")):
        try:
            content = filepath.read_text(encoding="utf-8")
        except Exception:
            continue

        matching_lines = []
        for line in content.splitlines():
            line_lower = line.lower()
            # Match if ANY query word appears in the line
            if any(word in line_lower for word in query_words):
                stripped = line.strip()
                if stripped:  # skip blank lines
                    matching_lines.append(stripped)

        if matching_lines:
            excerpt = "\n  ".join(matching_lines[:8])
            results.append(f"[Source: {filepath.name}]\n  {excerpt}")

    if not results:
        return (
            f"No results found for '{query}' in any document. "
            "Do not guess — report that no evidence was found."
        )

    header = f"Found {len(results)} document(s) matching '{query}':\n\n"
    return header + "\n\n".join(results)

# ═══════════════════════════════════════════════════════
# TOOL 2: read_record
# Looks up a single order by its ID in records.csv
# ═══════════════════════════════════════════════════════
@mcp.tool()
def read_record(order_id: str) -> str:
    """
    Look up a specific order record by its order ID from the CSV file.
    Returns all fields for that order.
    Use this to check order status, customer name, product, quantity, price.

    Args:
        order_id: The order ID to look up, e.g. ORD-1001
    """
    if isinstance(order_id, dict):
        order_id = order_id.get("order_id", "")

    # ── Input validation ──
    if not order_id or not order_id.strip():
        return "ERROR: order_id must be a non-empty string."

    order_id_clean = order_id.strip().upper()

    # Basic format check — must look like ORD-XXXX
    if not order_id_clean.startswith("ORD-"):
        return (
            f"ERROR: '{order_id}' is not a valid order ID format. "
            "Order IDs must start with ORD- followed by numbers, e.g. ORD-1001"
        )

    # ── Check CSV file exists ──
    if not CSV_FILE.exists():
        return "ERROR: records.csv not found in data folder."

    # ── Search the CSV ──
    try:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("order_id", "").strip().upper() == order_id_clean:
                    # Format the result nicely
                    lines = [f"[Source: records.csv | Order: {order_id_clean}]"]
                    for key, value in row.items():
                        if value:  # skip empty fields
                            lines.append(f"  {key}: {value}")
                    return "\n".join(lines)

    except Exception as e:
        return f"ERROR: Could not read records.csv — {str(e)}"

    # ── Nothing found ──
    return (
        f"No record found for order ID '{order_id_clean}'. "
        "Do not guess — report that no evidence was found."
    )


# ═══════════════════════════════════════════════════════
# TOOL 3: search_orders
# Searches all order records for a matching keyword/status
# ═══════════════════════════════════════════════════════
@mcp.tool()
def search_orders(query: str) -> str:
    """
    Search all order records in the database by a general query (e.g. status, customer name, or product).
    Use this to find orders when you don't have a specific order ID, such as finding all 'Processing' or 'Pending' orders.

    Args:
        query: The search term to look for, e.g. 'Processing'.
    """
    if isinstance(query, dict):
        query = query.get("query", "")

    if not query or not query.strip():
        return "ERROR: query must be a non-empty string."

    if not CSV_FILE.exists():
        return "ERROR: records.csv not found in data folder."

    query_clean = query.strip().lower()
    results = []

    try:
        with open(CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if any(query_clean in str(v).lower() for v in row.values()):
                    lines = [f"Order: {row.get('order_id', 'Unknown')}"]
                    for key, value in row.items():
                        if value:
                            lines.append(f"  {key}: {value}")
                    results.append("\n".join(lines))

        if not results:
            return (
                f"No orders found matching '{query}'. "
                "Do not guess — report that no evidence was found."
            )

        header = f"[Source: records.csv]\nFound {len(results)} order(s) matching '{query}':\n\n"
        return header + "\n\n".join(results)

    except Exception as e:
        return f"ERROR: Could not read records.csv — {str(e)}"


# ═══════════════════════════════════════════════════════
# TOOL 4: save_report
# Saves a markdown report to the output/ folder
# ═══════════════════════════════════════════════════════
@mcp.tool()
def save_report(title: str, content: str) -> str:
    """
    Save a markdown report to the output folder.
    Always call this after writing the final report.
    The report must cite sources for every fact.

    Args:
        title:   Short title for the report, e.g. 'Order ORD-1005 Summary'
        content: Full markdown content of the report, with cited sources.
    """

    # ── Input validation ──
    if not title or not title.strip():
        return "ERROR: title must be a non-empty string."

    if not content or not content.strip():
        return "ERROR: content must be non-empty."

    if len(title) > 100:
        return "ERROR: title is too long. Keep it under 100 characters."

    if len(content) > 50000:
        return "ERROR: content is too long (max 50,000 characters)."

    # ── Sanitize the title for use as a filename ──
    # Remove characters that are illegal in Windows filenames
    safe_title = "".join(
        c if c.isalnum() or c in (" ", "-", "_") else "_"
        for c in title.strip()
    ).replace(" ", "_")

    # ── Create output folder if it doesn't exist ──
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Build filename with timestamp so reports don't overwrite each other ──
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename  = f"{timestamp}_{safe_title}.md"
    filepath  = OUTPUT_DIR / filename

    # ── Write the file ──
    try:
        filepath.write_text(content, encoding="utf-8")
    except Exception as e:
        return f"ERROR: Could not save report — {str(e)}"

    return (
        f"Report saved successfully.\n"
        f"File: output/{filename}"
    )


# ═══════════════════════════════════════════════════════
# Start the server (stdio transport — used by CrewAI)
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    import sys
    print("Nexus Ops MCP server starting...", file=sys.stderr)
    mcp.run(transport="stdio")