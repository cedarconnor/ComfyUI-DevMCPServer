# ComfyUI-MCP-Server

**Your AI Agent's Gateway to ComfyUI.**

This tool lets your favorite AI coding assistant (Claude, Cursor, Windsurf, etc.) "talk" directly to ComfyUI. This means your agent can:
- 🚫 **See Errors automatically** without you copying logs.
- 🧐 **Understand your workflow** by reading the node graph.
- 🚀 **Run and fix workflows** directly from the chat.

It works by running a small "Server" that speaks the **Model Context Protocol (MCP)**, a standard language for AI tools.

---

## 📦 Installation

This project is installed as a **ComfyUI Custom Node**.

### Option 1: Manager (Recommended)
*Coming soon to ComfyUI Manager!*

### Option 2: Manual Install (Git)
1.  Open your terminal/command prompt.
2.  Navigate to your ComfyUI custom nodes folder:
    ```bash
    cd /path/to/ComfyUI/custom_nodes
    ```
3.  Clone this repository:
    ```bash
    git clone https://github.com/cedarconnor/ComfyUI-DevMCPServer.git
    ```
4.  **Restart ComfyUI**.

---

## 🤖 Connect Your Agent

Once installed, you need to tell your AI Agent where to find this server.

### 🟣 Claude Desktop / Claude Code
Add this to your `claude_desktop_config.json`:
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
*(Replace `/path/to/...` with the actual path to the folder)*

### 🔵 Cursor
1.  Go to **Settings** > **Features** > **MCP Servers**.
2.  Click **+ Add New MCP Server**.
3.  Fill in the details:
    *   **Name**: `comfyui`
    *   **Type**: `command`
    *   **Command**: `python /path/to/ComfyUI/custom_nodes/ComfyUI-DevMCPServer/mcp_server.py`

### 🌊 Windsurf / Gemini / Other CLI
Most CLI agents accept an MCP configuration flag or config file. Use the command:
```bash
python /path/to/ComfyUI/custom_nodes/ComfyUI-DevMCPServer/mcp_server.py
```

---

## 🛠 Features & Usage

Once connected, you can ask your agent to do things like:

### 1. "What is in my workflow?"
The agent uses **`get_workflow`** to see your current node graph. It can explain what your workflow does or suggest improvements.

### 2. "Fix this error"
If a generation fails, just ask "Why did that fail?". The agent skips the guessing game and uses **`get_status`** and log reading tools to see the exact error message and traceback from ComfyUI.

### 3. "Find a node for..."
Ask "Is there a node for IPAdapter?". The agent uses **`get_node_types`** to search your installed nodes and find the right one for the job.

### 4. "Check status"
Ask "Is the queue full?". The agent can check **`get_status`** to see running jobs, system resources (VRAM/RAM), and more.

---

## ❓ Troubleshooting

**"MCP Server connection failed"**
*   Make sure you used the full absolute path to `mcp_server.py`.
*   Ensure you have Python installed and accessible.

**"No workflow found"**
*   Make sure ComfyUI is running.
*   The server needs to be installed as a Custom Node (in `custom_nodes` folder) for it to see the live workflow.

**"Connection refused"**
*   By default, it tries to connect to `http://127.0.0.1:8188`. If you run ComfyUI on a different port, check the `.comfyui_url` file in the custom node folder.
