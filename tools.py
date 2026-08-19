
import random

# Each tool costs a fixed number of credits per call.
# Integers only — this keeps credit accounting exact, no float drift.
TOOL_COSTS = {
    "web_search": 10,
    "write_file": 10,
}

def web_search(query: str, force_fail: bool = False) -> dict:
    """Mock web search tool. Returns a canned result."""
    if force_fail:
        raise RuntimeError("web_search tool failed (simulated failure)")
    return {
        "tool": "web_search",
        "output": f"[MOCK] Found 3 results about '{query}'",
        "cost": TOOL_COSTS["web_search"],
    }

def write_file(content: str, force_fail: bool = False) -> dict:
    """Mock file-writing tool. Returns a canned result."""
    if force_fail:
        raise RuntimeError("write_file tool failed (simulated failure)")
    return {
        "tool": "write_file",
        "output": f"[MOCK] Saved summary.txt with content: '{content}'",
        "cost": TOOL_COSTS["write_file"],
    }
