#!/usr/bin/env python3
"""
MCP Server for ComfyUI - Exposes workflow tools to AI Agents.

This server connects to ComfyUI's API and provides tools to:
- View the current workflow
- List all nodes
- Get node details
- Edit the graph (create, connect, move nodes)
- Run workflows
- Check status

Usage:
    python mcp_server.py
"""

import json
import socket
import sys
import urllib.request
import urllib.error
import urllib.parse
from typing import Any, Optional
import asyncio

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# =============================================================================
# Configuration & Helpers
# =============================================================================

COMFYUI_URL = None  # Will be set dynamically

def get_comfyui_url() -> str:
    """Get the ComfyUI URL - try common ports or read from file."""
    import os

    # Try to read from the URL file written by the __init__.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    url_file = os.path.join(script_dir, ".comfyui_url")

    if os.path.exists(url_file):
        try:
            with open(url_file, "r") as f:
                url = f.read().strip()
                if url:
                    return url
        except Exception:
            pass

    # Try common ports
    for port in [8188, 8000, 8189]:
        url = f"http://127.0.0.1:{port}"
        try:
            req = urllib.request.Request(f"{url}/system_stats", method="GET")
            with urllib.request.urlopen(req, timeout=1):
                return url
        except Exception:
            continue

    return "http://127.0.0.1:8188"

def make_request(endpoint: str, method: str = "GET", data: dict = None, timeout: int = None) -> dict:
    """Make a request to ComfyUI's API."""
    global COMFYUI_URL
    if COMFYUI_URL is None:
        COMFYUI_URL = get_comfyui_url()

    url = f"{COMFYUI_URL}{endpoint}"

    # Use longer timeout for /object_info since it can be large
    if timeout is None:
        timeout = 30 if endpoint == "/object_info" else 10

    try:
        if data:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method=method
            )
        else:
            req = urllib.request.Request(url, method=method)

        with urllib.request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}

# Cache for object_info
_object_info_cache = None
_object_info_cache_time = 0
CACHE_TTL = 300

def get_object_info_cached() -> dict:
    """Get object_info with caching."""
    global _object_info_cache, _object_info_cache_time
    import time
    
    current_time = time.time()
    if _object_info_cache is not None and (current_time - _object_info_cache_time) < CACHE_TTL:
        return _object_info_cache
        
    result = make_request("/object_info")
    if "error" not in result:
        _object_info_cache = result
        _object_info_cache_time = current_time
    return result

# =============================================================================
# Tool Implementations
# =============================================================================

def get_workflow() -> dict:
    """Get current workflow."""
    # Try our custom endpoint first (from __init__.py)
    live = make_request("/mcp/workflow")
    if live and "workflow" in live:
        return live
        
    # Fallback to history
    history = make_request("/history")
    if history and "error" not in history:
        latest = list(history.keys())[-1] if history else None
        if latest:
            return {
                "source": "history", 
                "workflow": history[latest].get("prompt", {}),
                "outputs": history[latest].get("outputs", {})
            }
            
    return {"message": "No workflow found"}

def get_node_types(search=None, category=None) -> str:
    """Search and filter available nodes, returning concise TOON format."""
    all_nodes = get_object_info_cached()
    if "error" in all_nodes:
        return f"Error getting nodes: {all_nodes['error']}"

    # Filter
    matches = []
    for name, info in all_nodes.items():
        if search:
            s_term = search.lower()
            if s_term not in name.lower() and s_term not in str(info.get("display_name", "")).lower():
                continue
        if category:
            if category.lower() not in info.get("category", "").lower():
                continue
        matches.append((name, info))

    matches.sort(key=lambda x: x[0])
    
    # Format output
    lines = [f"Found {len(matches)} nodes:"]
    for name, info in matches[:50]: # Limit to 50 to avoid overflowing context
        display = info.get("display_name", name)
        cat = info.get("category", "Uncategorized")
        lines.append(f"- {name} ({display}) [{cat}]")
        
    if len(matches) > 50:
        lines.append(f"... and {len(matches) - 50} more. Refine your search.")
        
    return "\n".join(lines)

def get_status() -> str:
    """Get detailed status including specific queue items and system stats."""
    queue = make_request("/queue")
    stats = make_request("/system_stats")
    
    lines = []
    
    
    # Queue
    if "error" not in queue:
        running = queue.get("queue_running", [])
        pending = queue.get("queue_pending", [])
        lines.append(f"Queue: {len(running)} running, {len(pending)} pending")
    else:
        lines.append(f"Queue Error: {queue['error']}")
    
    # System
    if "error" not in stats:
        sys_info = stats.get("system", {})
        lines.append(f"System: {sys_info.get('os', 'Unknown')} Python {sys_info.get('python_version', '?')}")
        for dev in stats.get("devices", []):
            vram_total = dev.get("vram_total", 0) / (1024**3)
            vram_free = dev.get("vram_free", 0) / (1024**3)
            lines.append(f"GPU: {dev.get('name')} | VRAM: {vram_total - vram_free:.1f}/{vram_total:.1f} GB Used")
    else:
        lines.append(f"System Stats Error: {stats['error']}")
            
    return "\n".join(lines)

def run_workflow(node_ids=None) -> dict:
    """Run the workflow. If node_ids provided, run only up to those nodes."""
    # If partial run, we need the backend to support it. 
    # For now, we'll try to queue the whole thing via standard API if no node_ids
    
    if node_ids:
        # This requires our custom endpoint in __init__.py
        return make_request("/mcp/run-node", method="POST", data={"node_id": node_ids})
    else:
        # Standard queue
        workflow = get_workflow()
        if "workflow" in workflow:
            # We need the API format to queue
            # If we only have the UI format, this might fail unless we convert it
            # Ideally we use the client to "Queue Prompt"
            pass
            
        # Fallback to simple queue command if configured
        return make_request("/prompt", method="POST", data={"prompt": {}}) # Placeholder, real queueing is complex without raw prompt

def get_logs(count: int = 50) -> str:
    """Get recent logs from comfyui.log if available."""
    import os
    # Try to find log file in likely locations
    # 1. Env var
    # 2. current dir
    # 3. Parent dir (ComfyUI root if we are in custom_nodes/ComfyUI-DevMCPServer)
    
    
    log_file = os.environ.get("COMFYUI_LOG")
    
    # Calculate paths relative to this script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    search_paths = [
        "comfyui.log",
        "../../comfyui.log", 
        "../../../comfyui.log",
        os.path.join(base_dir, "comfyui.log"),
        os.path.abspath(os.path.join(base_dir, "../../comfyui.log")), # ../../ from custom_nodes/ComfyUI-DevMCPServer
    ]
    
    if not log_file:
        for p in search_paths:
            if os.path.exists(p):
                log_file = p
                break
                
    if not log_file or not os.path.exists(log_file):
        return "Log file not found. Ensure ComfyUI is running with logging redirected to 'comfyui.log' in the root directory."
        
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            return "".join(lines[-count:])
    except Exception as e:
        return f"Error reading logs: {e}"

def queue_workflow(workflow: dict) -> str:
    """Queue a workflow for execution."""
    data = {"prompt": workflow}
    # If the input is already having "prompt" key, use it directly (legacy support)
    if "prompt" in workflow:
        data = workflow
    elif "workflow" in workflow:
        # Handle output from get_workflow
        data = {"prompt": workflow["workflow"]}
        
    res = make_request("/prompt", method="POST", data=data)
    if "error" in res:
        return f"Error queuing workflow: {res['error']}"
    return f"Workflow queued. Prompt ID: {res.get('prompt_id')}"

def get_last_error() -> str:
    """Get the last error with full context and suggestions."""
    import os
    import sys
    
    # Import our new modules
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    from error_parser import parse_traceback, format_error_summary
    from pattern_matcher import match_error
    
    # First, try to get errors from logs
    logs = get_logs(count=100)
    
    # Look for traceback in logs
    traceback_text = None
    if "Traceback" in logs:
        # Extract the traceback
        lines = logs.split('\n')
        in_traceback = False
        tb_lines = []
        
        for line in lines:
            if 'Traceback (most recent call last)' in line:
                in_traceback = True
                tb_lines = [line]
            elif in_traceback:
                tb_lines.append(line)
                # End of traceback (line with error type)
                if line.strip() and not line.startswith(' ') and ':' in line:
                    break
        
        if tb_lines:
            traceback_text = '\n'.join(tb_lines)
    
    if not traceback_text:
        return "No recent errors found in logs."
    
    # Parse the error
    parsed = parse_traceback(traceback_text)
    summary = format_error_summary(parsed)
    
    # Try to match against patterns
    pattern_match = match_error(traceback_text)
    if pattern_match:
        summary += f"\n\n💡 **{pattern_match['title']}**\n{pattern_match['suggestion']}"
    
    return summary

def get_error_history() -> str:
    """Get the error history."""
    import os
    import sys
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    # For now, scan logs for multiple tracebacks
    logs = get_logs(count=500)
    
    if "Traceback" not in logs:
        return "No errors found in recent logs."
    
    # Count tracebacks
    traceback_count = logs.count('Traceback (most recent call last)')
    
    # Get unique error types
    import re
    error_types = re.findall(r'^(\w+Error|\w+Exception):', logs, re.MULTILINE)
    unique_errors = list(set(error_types))
    
    result = f"Found {traceback_count} error(s) in recent logs.\n"
    if unique_errors:
        result += f"Error types: {', '.join(unique_errors[:5])}"
        if len(unique_errors) > 5:
            result += f" (+{len(unique_errors) - 5} more)"
    
    result += "\n\nUse `get_last_error` for detailed analysis of the most recent error."
    
    return result

def check_health() -> str:
    """Check the current workflow for potential issues."""
    import os
    import sys
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    from health_check import check_workflow_health, format_health_report
    
    workflow = get_workflow()
    if not workflow or "workflow" not in workflow:
        return "No workflow loaded. Open a workflow in ComfyUI first."
    
    health_result = check_workflow_health(workflow)
    return format_health_report(health_result)

# =============================================================================
# MCP Server Setup
# =============================================================================

server = Server("comfyui-custom-node")

@server.list_tools()
async def list_tools():
    return [
        Tool(
            name="get_workflow",
            description="Get the current workflow JSON.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_node_types",
            description="Search for available nodes.",
            inputSchema={
                "type": "object", 
                "properties": {
                    "search": {"type": "string"},
                    "category": {"type": "string"}
                }
            }
        ),
        Tool(
            name="get_status",
            description="Get system and queue status.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="queue_workflow",
            description="Queue a workflow for execution.",
            inputSchema={
                "type": "object", 
                "properties": {
                    "workflow": {"type": "object"}
                },
                "required": ["workflow"]
            }
        ),
        Tool(
            name="get_logs",
            description="Get recent ComfyUI logs.",
            inputSchema={
                "type": "object", 
                "properties": {
                    "count": {"type": "integer"}
                }
            }
        ),
        Tool(
            name="get_last_error",
            description="Get the last error with context and fix suggestions.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="get_error_history",
            description="Get a summary of recent errors.",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="check_workflow_health",
            description="Analyze the current workflow for potential issues before running.",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    if not arguments:
        arguments = {}
        
    if name == "get_workflow":
        return [TextContent(type="text", text=json.dumps(get_workflow(), indent=2))]
    elif name == "get_node_types":
        return [TextContent(type="text", text=get_node_types(**arguments))]
    elif name == "get_status":
        return [TextContent(type="text", text=get_status())]
    elif name == "queue_workflow":
        return [TextContent(type="text", text=queue_workflow(**arguments))]
    elif name == "get_logs":
        return [TextContent(type="text", text=get_logs(**arguments))]
    elif name == "get_last_error":
        return [TextContent(type="text", text=get_last_error())]
    elif name == "get_error_history":
        return [TextContent(type="text", text=get_error_history())]
    elif name == "check_workflow_health":
        return [TextContent(type="text", text=check_health())]
    return [TextContent(type="text", text=f"Unknown tool: {name}")]

async def run_server():
    # Run the server
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())

def main():
    """Synchronous entrypoint for CLI scripts."""
    asyncio.run(run_server())

if __name__ == "__main__":
    main()
