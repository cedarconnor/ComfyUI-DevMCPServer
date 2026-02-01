# ComfyUI Dev MCP Server

An MCP server that closes the development loop between your coding agent (Claude Code, Cursor, Claude.ai, etc.) and ComfyUI. No more manual copy-pasting of error logs!

## What It Does

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│ Your Code   │────>│   ComfyUI        │────>│  Log File    │
│   Editor    │     │   (running)      │     │              │
└─────────────┘     └──────────────────┘     └──────┬───────┘
       ▲                                            │
       │            ┌──────────────────┐            │
       │            │  MCP Server      │<───────────┘
       └────────────│  (this tool)     │  watches & parses
                    └──────────────────┘
```

**Features:**
- **Error Detection**: Automatically parses ComfyUI logs for Python tracebacks, extracting error type, message, file locations, and which custom node caused it
- **Log Tailing**: Query recent logs or search for specific patterns
- **File Watching**: See which files changed in custom_nodes (useful for knowing what triggered a reload)
- **ComfyUI API**: Check status, queue workflows, interrupt execution, query available nodes
- **Agent-Friendly Output**: Errors formatted with markdown for easy consumption by LLMs

## Quick Start

### 1. Install

```bash
# Clone or download this directory
cd comfyui-dev-mcp

# Install with pip
pip install -e .

# Or just install dependencies
pip install mcp httpx watchdog
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env with your paths:
#   COMFYUI_PATH=/path/to/ComfyUI
#   COMFYUI_LOG=/path/to/ComfyUI/comfyui.log
```

### 3. Run ComfyUI with Logging

ComfyUI doesn't write to a log file by default. Run it like this:

```bash
cd /path/to/ComfyUI
python main.py 2>&1 | tee comfyui.log
```

Or on Windows:
```powershell
python main.py 2>&1 | Tee-Object -FilePath comfyui.log
```

### 4. Connect Your Agent

See setup instructions for your specific tool below.

---

## Setup for Different Tools

### Claude Code

Add to your Claude Code MCP config (`~/.claude/claude_desktop_config.json` or project-level):

```json
{
  "mcpServers": {
    "comfyui-dev": {
      "command": "python",
      "args": ["/path/to/comfyui-dev-mcp/comfyui_mcp_server.py"],
      "env": {
        "COMFYUI_PATH": "/path/to/ComfyUI",
        "COMFYUI_LOG": "/path/to/ComfyUI/comfyui.log"
      }
    }
  }
}
```

Then in Claude Code, you can say things like:
- "Check for any ComfyUI errors"
- "What's in the recent ComfyUI logs?"
- "Is ComfyUI running?"

### Cursor

Add to your Cursor MCP settings (Settings → MCP Servers):

```json
{
  "comfyui-dev": {
    "command": "python",
    "args": ["/path/to/comfyui-dev-mcp/comfyui_mcp_server.py"],
    "env": {
      "COMFYUI_PATH": "/path/to/ComfyUI",
      "COMFYUI_LOG": "/path/to/ComfyUI/comfyui.log"
    }
  }
}
```

### Claude.ai Desktop (with MCP)

If you have MCP enabled in Claude.ai desktop, add to your config:

```json
{
  "mcpServers": {
    "comfyui-dev": {
      "command": "python",
      "args": ["/path/to/comfyui-dev-mcp/comfyui_mcp_server.py"],
      "env": {
        "COMFYUI_PATH": "/path/to/ComfyUI",
        "COMFYUI_LOG": "/path/to/ComfyUI/comfyui.log"
      }
    }
  }
}
```

### Other MCP-Compatible Tools

The server uses standard MCP protocol over stdio. Any MCP client can connect by running:

```bash
python /path/to/comfyui_mcp_server.py
```

---

## Available Tools

### `get_comfy_errors`
Get recent errors and tracebacks from ComfyUI.

```
Arguments:
  count: int = 5      # Number of errors to return
  clear: bool = false # Clear error history after returning
```

Example output:
```markdown
## Error: ModuleNotFoundError
**Time:** 2024-01-15T10:30:45
**Node:** ComfyUI-MyCustomNode
**File:** /path/to/custom_nodes/ComfyUI-MyCustomNode/nodes.py
**Message:** No module named 'some_package'

**Traceback:**
```python
Traceback (most recent call last):
  File "/path/to/custom_nodes/ComfyUI-MyCustomNode/nodes.py", line 5, in <module>
    import some_package
ModuleNotFoundError: No module named 'some_package'
```
```

### `get_comfy_logs`
Get recent log output from ComfyUI.

```
Arguments:
  count: int = 100  # Number of lines to return
  search: str       # Optional regex pattern to filter
```

### `get_comfy_status`
Check if ComfyUI is running and get system stats.

Returns:
- Running status
- Queue status (pending/running jobs)
- System stats (memory, GPU info if available)
- Error count in buffer

### `get_file_changes`
See recent file changes in custom_nodes directory.

```
Arguments:
  count: int = 20  # Number of changes to return
```

### `queue_workflow`
Queue a workflow for execution.

```
Arguments:
  workflow: object  # The ComfyUI workflow JSON
```

### `interrupt_comfy`
Interrupt the currently running execution.

### `get_node_info`
Get information about available nodes.

```
Arguments:
  node_name: str  # Optional - specific node to query, or list all
```

---

## Combining with Hot Reload

For the best development experience, combine this with ComfyUI-HotReloadHack or ComfyUI_devtools:

1. Install hot reload: `cd custom_nodes && git clone https://github.com/logtd/ComfyUI-HotReloadHack`
2. Run ComfyUI with logging
3. Connect your agent via MCP

Now your workflow becomes:
```
Edit code → Auto-reload (HotReloadHack) → Error appears → Agent sees it (MCP) → Agent suggests fix
```

---

## Example Agent Interactions

### "Fix my node error"

Agent will:
1. Call `get_comfy_errors` to see what failed
2. See the traceback pointing to your file
3. Suggest the fix based on the error

### "Run my test workflow and check for errors"

Agent will:
1. Call `queue_workflow` with your workflow JSON
2. Wait a moment
3. Call `get_comfy_errors` to see if anything failed
4. Report results or suggest fixes

### "What changed since my last edit?"

Agent will:
1. Call `get_file_changes` to see modified files
2. Call `get_comfy_logs` with a search for those files
3. Summarize what happened

---

## Troubleshooting

### "Log watcher not initialized"
- Make sure `COMFYUI_LOG` points to an existing file
- Make sure ComfyUI is running with `2>&1 | tee comfyui.log`

### "Could not get node info. Is ComfyUI running?"
- Check that ComfyUI is running
- Check `COMFYUI_API` URL is correct (default: http://127.0.0.1:8188)

### "File watcher not initialized"
- Install watchdog: `pip install watchdog`
- Make sure `COMFYUI_PATH` points to your ComfyUI directory

### No errors showing up
- Errors are parsed from the log file in real-time
- Make sure your ComfyUI output is going to the log file
- Try `get_comfy_logs` to see if logs are being captured

---

## License

MIT
