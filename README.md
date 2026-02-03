# ComfyUI-MCP-Server

**Your AI Assistant's Direct Line to ComfyUI.**

This tool lets AI assistants like Claude, Cursor, Windsurf, and Gemini "talk" directly to ComfyUI. Instead of you copying error messages or describing your workflow, your AI can see it all automatically.

---

## ✨ What Can Your AI Do With This?

Once connected, your AI assistant gains powerful superpowers:

| Ask Your AI... | What Happens |
|----------------|--------------|
| "Why did that fail?" | AI reads the error, identifies the problem node, and suggests a fix |
| "Check my workflow before I run it" | AI scans for missing connections or potential issues |
| "What's in my current workflow?" | AI reads your node graph and can explain or improve it |
| "Find a node that does X" | AI searches through all your installed nodes |
| "Is ComfyUI busy right now?" | AI checks the queue and system resources |
| "Run my workflow" | AI queues it for execution |

---

## 📦 Installation

### Option 1: ComfyUI Manager (Recommended)
*Coming soon!*

### Option 2: Manual Install
1.  Open your terminal
2.  Go to your ComfyUI custom nodes folder:
    ```bash
    cd /path/to/ComfyUI/custom_nodes
    ```
3.  Clone this repository:
    ```bash
    git clone https://github.com/cedarconnor/ComfyUI-DevMCPServer.git
    ```
4.  **Restart ComfyUI**

---

## 🤖 Connect Your AI Assistant

Add this server to your AI tool's MCP configuration.

### Claude Desktop / Claude Code
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "comfyui": {
      "command": "python",
      "args": ["/path/to/ComfyUI/custom_nodes/ComfyUI-DevMCPServer/mcp_server.py"]
    }
  }
}
```

### Cursor
1.  Go to **Settings** → **Features** → **MCP Servers**
2.  Click **+ Add New MCP Server**
3.  Fill in:
    - **Name**: `comfyui`
    - **Type**: `command`
    - **Command**: `python /path/to/ComfyUI/custom_nodes/ComfyUI-DevMCPServer/mcp_server.py`

### Other AI Tools (Windsurf, Gemini CLI, etc.)
Use this command:
```bash
python /path/to/ComfyUI/custom_nodes/ComfyUI-DevMCPServer/mcp_server.py
```

> **Important**: Replace `/path/to/ComfyUI` with the actual path on your computer!

---

## 🛠️ All Available Tools

Your AI has access to these tools:

### Workflow Tools
| Tool | What It Does |
|------|--------------|
| `get_workflow` | Reads your current workflow (the nodes and connections you see in ComfyUI) |
| `queue_workflow` | Runs your workflow (same as clicking "Queue Prompt") |
| `check_workflow_health` | Scans your workflow for problems like missing connections or null inputs |

### Debugging Tools
| Tool | What It Does |
|------|--------------|
| `get_last_error` | Gets the most recent error with:<br>• The exact file and line number<br>• Which **node** caused the problem<br>• A **suggested fix** from 20+ known error patterns |
| `get_error_history` | Shows a summary of recent errors |
| `get_logs` | Reads the raw ComfyUI log output |

### Information Tools
| Tool | What It Does |
|------|--------------|
| `get_node_types` | Searches installed nodes (e.g., "find IPAdapter nodes") |
| `get_status` | Shows queue status, running jobs, GPU memory usage |

---

## 🔧 Example Conversations

**Debugging an Error:**
> **You:** "My generation just failed. What happened?"
> 
> **AI:** *Uses `get_last_error`*
> 
> "The error was a **CUDA Out of Memory** in the KSampler node (ID: 42). Try reducing your image resolution from 1024 to 768, or enable `--lowvram` mode."

**Checking Before Running:**
> **You:** "Is my workflow ready to run?"
> 
> **AI:** *Uses `check_workflow_health`*
> 
> "⚠️ Found 2 warnings: Node 15 (ControlNet) has a null input for 'image'. Node 23 appears disconnected from the rest of the workflow."

**Finding a Node:**
> **You:** "Is there a node for upscaling images?"
> 
> **AI:** *Uses `get_node_types`*
> 
> "Yes! You have several upscale nodes installed: ImageUpscaleWithModel, UpscaleImage, and UltimateSDUpscale from the Ultimate SD Upscale pack."

---

## ❓ Troubleshooting

| Problem | Solution |
|---------|----------|
| "MCP Server connection failed" | Make sure you used the **full absolute path** to `mcp_server.py` |
| "No workflow found" | Make sure ComfyUI is running and you have a workflow open |
| "Connection refused" | ComfyUI might be on a different port. Check the `.comfyui_url` file in this folder |

---

## 🧑‍💻 For Developers: Hot Reload

This project includes a **hot reload** feature that makes development much faster. You can change the code while ComfyUI is running, and your changes take effect immediately — no restart needed!

### How It Works

The code is split into two parts:

| File | Purpose | Hot Reloads? |
|------|---------|--------------|
| `handlers.py` | All the API logic (this is where you make changes) | ✅ **Yes** |
| `state.py` | Data storage (your workflow, error history) | ❌ No (data persists) |

When ComfyUI receives an API request, it automatically reloads `handlers.py`. This means:

1. **Edit** `handlers.py`
2. **Save** the file
3. **Make an API call** (or ask your AI to do something)
4. Your changes are now live!

Your data (like the current workflow) stays safe in `state.py` and isn't affected by reloads.

### Example: Adding a New Feature

Let's say you want to add a "ping" endpoint that just returns "pong":

1. Open `handlers.py`
2. Add this function:
   ```python
   async def ping_handler(request):
       return web.json_response({"message": "pong"})
   ```
3. Save the file
4. The next API request will use your new code!

### For Broader Custom Node Development

If you're developing other custom nodes (not just this MCP server), we recommend [ComfyUI_devtools](https://github.com/Comfy-Org/ComfyUI_devtools). It provides hot-reload for the entire ComfyUI ecosystem.

---

## 📁 Project Structure

```
ComfyUI-DevMCPServer/
├── mcp_server.py        # MCP server (AI connects here)
├── __init__.py          # ComfyUI custom node setup
├── handlers.py          # API handlers (edit this for hot reload!)
├── state.py             # Persistent data storage
├── error_parser.py      # Extracts error details from tracebacks
├── pattern_matcher.py   # 20+ error patterns with fix suggestions
├── health_check.py      # Workflow validation logic
└── js/
    └── mcp_bridge.js    # Syncs your workflow to the server
```

---

## 📄 License

MIT License - feel free to use and modify!

---

## 🤝 Contributing

Found a bug? Have an idea? Open an issue or PR on [GitHub](https://github.com/cedarconnor/ComfyUI-DevMCPServer)!
