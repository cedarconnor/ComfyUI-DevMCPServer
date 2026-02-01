#!/usr/bin/env python3
"""
ComfyUI Development MCP Server

An MCP server that closes the loop between your coding agent and ComfyUI:
- Tails the ComfyUI log file and extracts errors/tracebacks
- Exposes tools for agents to query errors, logs, and node status
- Can trigger restarts and queue workflows via ComfyUI API
- Watches for file changes and can auto-reload nodes

Usage:
    python comfyui_mcp_server.py

Configure via environment variables or .env file:
    COMFYUI_PATH=/path/to/ComfyUI
    COMFYUI_LOG=/path/to/comfyui.log  (optional, defaults to COMFYUI_PATH/comfyui.log)
    COMFYUI_API=http://127.0.0.1:8188 (optional)
"""

import asyncio
import json
import os
import re
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Optional: for file watching
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileModifiedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# Optional: for HTTP requests to ComfyUI API
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False


# =============================================================================
# Configuration
# =============================================================================

def load_env():
    """Load .env file if present"""
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())

load_env()

COMFYUI_PATH = Path(os.environ.get("COMFYUI_PATH", "")) if os.environ.get("COMFYUI_PATH") else None
COMFYUI_LOG = None
if os.environ.get("COMFYUI_LOG"):
    COMFYUI_LOG = Path(os.environ.get("COMFYUI_LOG"))
elif COMFYUI_PATH:
    COMFYUI_LOG = COMFYUI_PATH / "comfyui.log"

COMFYUI_API = os.environ.get("COMFYUI_API", "http://127.0.0.1:8188")
MAX_LOG_LINES = int(os.environ.get("MAX_LOG_LINES", "1000"))  # Keep last N lines in memory
MAX_ERRORS = int(os.environ.get("MAX_ERRORS", "50"))  # Keep last N errors


# =============================================================================
# Error/Traceback Parser
# =============================================================================

@dataclass
class ParsedError:
    """A parsed error from ComfyUI logs"""
    timestamp: str
    error_type: str
    message: str
    traceback: list[str]
    node_name: Optional[str] = None
    node_file: Optional[str] = None
    raw_text: str = ""
    
    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "error_type": self.error_type,
            "message": self.message,
            "traceback": self.traceback,
            "node_name": self.node_name,
            "node_file": self.node_file,
        }
    
    def format_for_agent(self) -> str:
        """Format error for consumption by coding agent"""
        lines = [f"## Error: {self.error_type}"]
        lines.append(f"**Time:** {self.timestamp}")
        if self.node_name:
            lines.append(f"**Node:** {self.node_name}")
        if self.node_file:
            lines.append(f"**File:** {self.node_file}")
        lines.append(f"**Message:** {self.message}")
        if self.traceback:
            lines.append("\n**Traceback:**")
            lines.append("```python")
            lines.extend(self.traceback[-20:])  # Last 20 lines of traceback
            lines.append("```")
        return "\n".join(lines)


class LogParser:
    """Parses ComfyUI log output for errors and tracebacks"""
    
    # Patterns for detecting errors
    TRACEBACK_START = re.compile(r"Traceback \(most recent call last\):")
    ERROR_LINE = re.compile(r"^(\w+Error|\w+Exception|Error|Exception):\s*(.+)$", re.MULTILINE)
    FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)')
    NODE_PATTERN = re.compile(r"custom_nodes[/\\]([^/\\]+)")
    
    # Common ComfyUI error patterns
    COMFY_ERRORS = [
        re.compile(r"Cannot import (.+) custom node"),
        re.compile(r"Error loading custom node (.+):"),
        re.compile(r"Failed to validate prompt for output"),
        re.compile(r"Got an OOM|CUDA out of memory"),
        re.compile(r"RuntimeError: .+"),
        re.compile(r"ValueError: .+"),
        re.compile(r"TypeError: .+"),
        re.compile(r"AttributeError: .+"),
        re.compile(r"ModuleNotFoundError: .+"),
        re.compile(r"ImportError: .+"),
    ]
    
    def __init__(self):
        self.current_traceback: list[str] = []
        self.in_traceback = False
        self.errors: deque[ParsedError] = deque(maxlen=MAX_ERRORS)
        
    def parse_line(self, line: str) -> Optional[ParsedError]:
        """Parse a single log line, return error if complete traceback found"""
        line = line.rstrip()
        
        # Detect traceback start
        if self.TRACEBACK_START.search(line):
            self.in_traceback = True
            self.current_traceback = [line]
            return None
            
        # Accumulate traceback lines
        if self.in_traceback:
            self.current_traceback.append(line)
            
            # Check if this is the error line (ends traceback)
            error_match = self.ERROR_LINE.match(line)
            if error_match:
                error = self._build_error(error_match.group(1), error_match.group(2))
                self.in_traceback = False
                self.current_traceback = []
                self.errors.append(error)
                return error
                
            # Cap traceback length to avoid memory issues
            if len(self.current_traceback) > 100:
                self.in_traceback = False
                self.current_traceback = []
                
        # Check for standalone error patterns
        for pattern in self.COMFY_ERRORS:
            match = pattern.search(line)
            if match:
                error = ParsedError(
                    timestamp=datetime.now().isoformat(),
                    error_type=match.group(0).split(":")[0] if ":" in match.group(0) else "Error",
                    message=line,
                    traceback=[],
                    raw_text=line
                )
                self.errors.append(error)
                return error
                
        return None
    
    def _build_error(self, error_type: str, message: str) -> ParsedError:
        """Build a ParsedError from accumulated traceback"""
        # Extract node info from traceback
        node_name = None
        node_file = None
        for line in self.current_traceback:
            file_match = self.FILE_LINE.search(line)
            if file_match:
                filepath = file_match.group(1)
                node_match = self.NODE_PATTERN.search(filepath)
                if node_match:
                    node_name = node_match.group(1)
                    node_file = filepath
                    
        return ParsedError(
            timestamp=datetime.now().isoformat(),
            error_type=error_type,
            message=message,
            traceback=self.current_traceback.copy(),
            node_name=node_name,
            node_file=node_file,
            raw_text="\n".join(self.current_traceback)
        )
    
    def get_recent_errors(self, n: int = 5) -> list[ParsedError]:
        """Get the N most recent errors"""
        return list(self.errors)[-n:]
    
    def clear_errors(self):
        """Clear error history"""
        self.errors.clear()


# =============================================================================
# Log Watcher
# =============================================================================

class LogWatcher:
    """Watches ComfyUI log file for changes"""
    
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.parser = LogParser()
        self.log_buffer: deque[str] = deque(maxlen=MAX_LOG_LINES)
        self.last_position = 0
        self.last_inode = None
        
        except Exception as e:
            print(f"Error reading log: {e}", file=sys.stderr)
            
        return new_lines
    

        
    def get_recent_logs(self, n: int = 100) -> list[str]:
        """Get recent log lines"""
        return list(self.log_buffer)[-n:]
    
    def get_errors(self, n: int = 5) -> list[ParsedError]:
        """Get recent errors"""
        return self.parser.get_recent_errors(n)
    
    def search_logs(self, pattern: str, n: int = 50) -> list[str]:
        """Search logs for pattern"""
        try:
            regex = re.compile(pattern, re.IGNORECASE)
        except re.error:
            return [f"Error: Invalid regex pattern '{pattern}'"]

        matches = []
        for line in self.log_buffer:
            if regex.search(line):
                matches.append(line)
                if len(matches) >= n:
                    break
        return matches


# =============================================================================
# ComfyUI API Client
# =============================================================================

class ComfyUIClient:
    """Client for ComfyUI HTTP API"""
    
    def __init__(self, base_url: str = COMFYUI_API):
        self.base_url = base_url.rstrip("/")
        
    async def is_running(self) -> bool:
        """Check if ComfyUI is running"""
        if not HTTPX_AVAILABLE:
            return False
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/system_stats", timeout=2.0)
                return resp.status_code == 200
        except:
            return False
            
    async def get_system_stats(self) -> Optional[dict]:
        """Get ComfyUI system stats"""
        if not HTTPX_AVAILABLE:
            return None
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/system_stats", timeout=5.0)
                return resp.json()
        except:
            return None
            
    async def get_queue(self) -> Optional[dict]:
        """Get current queue status"""
        if not HTTPX_AVAILABLE:
            return None
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/queue", timeout=5.0)
                return resp.json()
        except:
            return None
            
    async def queue_prompt(self, workflow: dict) -> Optional[dict]:
        """Queue a workflow for execution"""
        if not HTTPX_AVAILABLE:
            return None
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.base_url}/prompt",
                    json={"prompt": workflow},
                    timeout=10.0
                )
                return resp.json()
        except Exception as e:
            return {"error": str(e)}
            
    async def interrupt(self) -> bool:
        """Interrupt current execution"""
        if not HTTPX_AVAILABLE:
            return False
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(f"{self.base_url}/interrupt", timeout=5.0)
                return resp.status_code == 200
        except:
            return False
            
    async def get_object_info(self) -> Optional[dict]:
        """Get info about all available nodes"""
        if not HTTPX_AVAILABLE:
            return None
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{self.base_url}/object_info", timeout=30.0)
                return resp.json()
        except:
            return None


# =============================================================================
# File Watcher for Hot Reload
# =============================================================================

@dataclass
class FileChange:
    """Record of a file change"""
    path: str
    timestamp: str
    event_type: str
    node_name: Optional[str] = None


class NodeFileWatcher:
    """Watches custom_nodes directory for file changes"""
    
    def __init__(self, comfyui_path: Path):
        self.custom_nodes_path = comfyui_path / "custom_nodes"
        self.changes: deque[FileChange] = deque(maxlen=100)
        self.observer = None
        
    def start(self):
        """Start watching for file changes"""
        if not WATCHDOG_AVAILABLE:
            return
            
        if not self.custom_nodes_path.exists():
            return
            
        handler = self._make_handler()
        self.observer = Observer()
        self.observer.schedule(handler, str(self.custom_nodes_path), recursive=True)
        self.observer.start()
        
    def stop(self):
        """Stop watching"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            
    def _make_handler(self):
        """Create file system event handler"""
        watcher = self
        
        class Handler(FileSystemEventHandler):
            def on_modified(self, event):
                if event.is_directory:
                    return
                if event.src_path.endswith('.py'):
                    watcher._record_change(event.src_path, "modified")
                    
            def on_created(self, event):
                if event.is_directory:
                    return
                if event.src_path.endswith('.py'):
                    watcher._record_change(event.src_path, "created")
                    
        return Handler()
        
    def _record_change(self, path: str, event_type: str):
        """Record a file change"""
        # Extract node name from path
        node_name = None
        path_obj = Path(path)
        try:
            # Get relative path from custom_nodes
            rel = path_obj.relative_to(self.custom_nodes_path)
            node_name = rel.parts[0] if rel.parts else None
        except ValueError:
            pass
            
        change = FileChange(
            path=path,
            timestamp=datetime.now().isoformat(),
            event_type=event_type,
            node_name=node_name
        )
        self.changes.append(change)
        
    def get_recent_changes(self, n: int = 20) -> list[FileChange]:
        """Get recent file changes"""
        return list(self.changes)[-n:]


# =============================================================================
# MCP Server
# =============================================================================

# Global state
log_watcher: Optional[LogWatcher] = None
file_watcher: Optional[NodeFileWatcher] = None
comfyui_client: Optional[ComfyUIClient] = None

# Create server
server = Server("comfyui-dev")


@server.list_tools()
async def list_tools():
    """List available tools"""
    tools = [
        Tool(
            name="get_comfy_errors",
            description="Get recent errors and tracebacks from ComfyUI. Returns parsed errors with file locations, node names, and full tracebacks formatted for debugging.",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of recent errors to return (default: 5)",
                        "default": 5
                    },
                    "clear": {
                        "type": "boolean",
                        "description": "Clear error history after returning (default: false)",
                        "default": False
                    }
                }
            }
        ),
        Tool(
            name="get_comfy_logs",
            description="Get recent log output from ComfyUI. Useful for seeing what ComfyUI is doing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of recent log lines to return (default: 100)",
                        "default": 100
                    },
                    "search": {
                        "type": "string",
                        "description": "Optional regex pattern to filter logs"
                    }
                }
            }
        ),
        Tool(
            name="get_comfy_status",
            description="Get ComfyUI server status including whether it's running, queue status, and system stats.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_file_changes",
            description="Get recent file changes in the custom_nodes directory. Useful for seeing what files were modified.",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {
                        "type": "integer",
                        "description": "Number of recent changes to return (default: 20)",
                        "default": 20
                    }
                }
            }
        ),
        Tool(
            name="queue_workflow",
            description="Queue a ComfyUI workflow for execution. Pass the workflow JSON.",
            inputSchema={
                "type": "object",
                "properties": {
                    "workflow": {
                        "type": "object",
                        "description": "The ComfyUI workflow JSON to execute"
                    }
                },
                "required": ["workflow"]
            }
        ),
        Tool(
            name="interrupt_comfy",
            description="Interrupt the currently running ComfyUI execution.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_node_info",
            description="Get information about a specific node type or list all available nodes.",
            inputSchema={
                "type": "object",
                "properties": {
                    "node_name": {
                        "type": "string",
                        "description": "Name of the node to get info for. If not provided, returns list of all nodes."
                    }
                }
            }
        ),
    ]
    return tools


@server.call_tool()
async def call_tool(name: str, arguments: dict):
    """Handle tool calls"""
    global log_watcher, file_watcher, comfyui_client
    
    if name == "get_comfy_errors":
        if not log_watcher:
            return [TextContent(type="text", text="Log watcher not initialized. Set COMFYUI_LOG path.")]
            
        count = arguments.get("count", 5)
        clear = arguments.get("clear", False)
        
        # Read any new lines first
        log_watcher.read_new_lines()
        
        errors = log_watcher.get_errors(count)
        
        if clear:
            log_watcher.parser.clear_errors()
            
        if not errors:
            return [TextContent(type="text", text="No errors found in recent logs.")]
            
        result = f"Found {len(errors)} recent error(s):\n\n"
        result += "\n---\n\n".join(e.format_for_agent() for e in errors)
        
        return [TextContent(type="text", text=result)]
        
    elif name == "get_comfy_logs":
        if not log_watcher:
            return [TextContent(type="text", text="Log watcher not initialized. Set COMFYUI_LOG path.")]
            
        count = arguments.get("count", 100)
        search = arguments.get("search")
        
        # Read any new lines first
        log_watcher.read_new_lines()
        
        if search:
            lines = log_watcher.search_logs(search, count)
        else:
            lines = log_watcher.get_recent_logs(count)
            
        if not lines:
            return [TextContent(type="text", text="No log lines found.")]
            
        return [TextContent(type="text", text="\n".join(lines))]
        
    elif name == "get_comfy_status":
        if not comfyui_client:
            comfyui_client = ComfyUIClient()

        # Update logs before checking status so error count is fresh
        if log_watcher:
            log_watcher.read_new_lines()
            
        running = await comfyui_client.is_running()
        
        result = {
            "running": running,
            "api_url": COMFYUI_API,
        }
        
        if running:
            stats = await comfyui_client.get_system_stats()
            queue = await comfyui_client.get_queue()
            if stats:
                result["system_stats"] = stats
            if queue:
                result["queue"] = queue
                
        # Add log watcher status
        if log_watcher:
            result["log_file"] = str(COMFYUI_LOG)
            result["log_exists"] = COMFYUI_LOG.exists()
            result["error_count"] = len(log_watcher.parser.errors)
            
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
    elif name == "get_file_changes":
        if not file_watcher:
            return [TextContent(type="text", text="File watcher not initialized. Install watchdog and set COMFYUI_PATH.")]
            
        count = arguments.get("count", 20)
        changes = file_watcher.get_recent_changes(count)
        
        if not changes:
            return [TextContent(type="text", text="No recent file changes detected.")]
            
        result = "Recent file changes:\n\n"
        for c in changes:
            result += f"- [{c.event_type}] {c.path}"
            if c.node_name:
                result += f" (node: {c.node_name})"
            result += f"\n  at {c.timestamp}\n"
            
        return [TextContent(type="text", text=result)]
        
    elif name == "queue_workflow":
        if not comfyui_client:
            comfyui_client = ComfyUIClient()
            
        workflow = arguments.get("workflow")
        if not workflow:
            return [TextContent(type="text", text="No workflow provided.")]
            
        result = await comfyui_client.queue_prompt(workflow)
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
        
    elif name == "interrupt_comfy":
        if not comfyui_client:
            comfyui_client = ComfyUIClient()
            
        success = await comfyui_client.interrupt()
        return [TextContent(type="text", text=f"Interrupt {'successful' if success else 'failed'}")]
        
    elif name == "get_node_info":
        if not comfyui_client:
            comfyui_client = ComfyUIClient()
            
        info = await comfyui_client.get_object_info()
        if not info:
            return [TextContent(type="text", text="Could not get node info. Is ComfyUI running?")]
            
        node_name = arguments.get("node_name")
        
        if node_name:
            if node_name in info:
                return [TextContent(type="text", text=json.dumps(info[node_name], indent=2))]
            else:
                # Search for partial match
                matches = [k for k in info.keys() if node_name.lower() in k.lower()]
                if matches:
                    return [TextContent(type="text", text=f"Node '{node_name}' not found. Did you mean:\n" + "\n".join(matches[:20]))]
                return [TextContent(type="text", text=f"Node '{node_name}' not found.")]
        else:
            # Return list of all nodes grouped by category
            categories = {}
            for name, data in info.items():
                cat = data.get("category", "uncategorized")
                if cat not in categories:
                    categories[cat] = []
                categories[cat].append(name)
                
            result = f"Available nodes ({len(info)} total):\n\n"
            for cat in sorted(categories.keys()):
                result += f"**{cat}** ({len(categories[cat])})\n"
                
            return [TextContent(type="text", text=result)]
            
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def run():
    """Main entry point"""
    global log_watcher, file_watcher, comfyui_client
    
    print("ComfyUI Dev MCP Server starting...", file=sys.stderr)
    print(f"  COMFYUI_PATH: {COMFYUI_PATH or 'not set'}", file=sys.stderr)
    print(f"  COMFYUI_LOG: {COMFYUI_LOG or 'not set'}", file=sys.stderr)
    print(f"  COMFYUI_API: {COMFYUI_API}", file=sys.stderr)
    
    # Initialize log watcher
    if COMFYUI_LOG and (COMFYUI_LOG.exists() or COMFYUI_LOG.parent.exists()):
        log_watcher = LogWatcher(COMFYUI_LOG)
        # Do initial read
        log_watcher.read_new_lines()
        print(f"  Log watcher initialized", file=sys.stderr)
    else:
        print(f"  Warning: Log file not found, log watching disabled", file=sys.stderr)
        
    # Initialize file watcher
    if WATCHDOG_AVAILABLE and COMFYUI_PATH and COMFYUI_PATH.exists():
        file_watcher = NodeFileWatcher(COMFYUI_PATH)
        file_watcher.start()
        print(f"  File watcher initialized", file=sys.stderr)
    elif not WATCHDOG_AVAILABLE:
        print(f"  Warning: watchdog not installed, file watching disabled", file=sys.stderr)
        
    # Initialize API client
    comfyui_client = ComfyUIClient()
    
    # Run MCP server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main():
    """Synchronous entry point for console script"""
    asyncio.run(run())


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    asyncio.run(main())
