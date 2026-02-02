
import server
import aiohttp
from aiohttp import web
import os
import json

# Define the directory for the node (standard boilerplate)
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

# =============================================================================
# Routes & Handlers
# =============================================================================

# Store the current workflow state (pushed from frontend or retrieved)
current_workflow = {}

async def workflow_handler(request):
    """Handle get/set of current workflow."""
    global current_workflow
    if request.method == "POST":
        data = await request.json()
        # Ensure we store it in the expected structure
        if "workflow" in data:
             current_workflow = data
        else:
             current_workflow = {"workflow": data}
        return web.json_response({"status": "ok"})
    else:
        # Return nested structure if it's just raw data
        if "workflow" not in current_workflow and current_workflow:
            return web.json_response({"workflow": current_workflow})
        return web.json_response(current_workflow)

async def run_node_handler(request):
    """Run specific nodes."""
    try:
        data = await request.json()
        node_id = data.get("node_id")
        
        # Access ComfyUI's PromptServer instance
        s = server.PromptServer.instance
        
        # We need the current workflow prompt to queue it
        # If we have the live workflow state, use it
        prompt = current_workflow.get("workflow", {})
        if not prompt:
             return web.json_response({"error": "No active workflow to run"}, status=400)

        # Generate a prompt ID
        import uuid
        prompt_id = str(uuid.uuid4())
        
        # This is a simplified queue method. 
        # In a real scenario, we might want to filter the prompt to only the sub-graph upstream of node_id
        # For now, we queue the whole thing but typically we'd use the backend API logic
        
        # Queue using the internal prompt queue
        # (number, prompt_id, prompt, extra_data, outputs_to_execute)
        # outputs_to_execute is what limits execution to specific nodes!
        node_ids_to_execute = [str(node_id)] if node_id else []
        
        s.prompt_queue.put(
            (0, prompt_id, prompt, {"client_id": "claude-mcp"}, node_ids_to_execute)
        )
        
        return web.json_response({"status": "queued", "prompt_id": prompt_id, "node_id": node_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)

# =============================================================================
# Setup
# =============================================================================

def setup_routes():
    """Register routes with ComfyUI server."""
    s = server.PromptServer.instance
    s.app.router.add_get("/mcp/workflow", workflow_handler)
    s.app.router.add_post("/mcp/workflow", workflow_handler)
    s.app.router.add_post("/mcp/run-node", run_node_handler)

def write_connection_info():
    """Write the ComfyUI URL to a file for mcp_server.py to use."""
    s = server.PromptServer.instance
    port = s.port
    address = s.address
    # Handle 0.0.0.0 case
    if address == "0.0.0.0":
        address = "127.0.0.1"
        
    url = f"http://{address}:{port}"
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    url_file = os.path.join(script_dir, ".comfyui_url")
    
    with open(url_file, "w") as f:
        f.write(url)
    print(f"[ComfyUI-MCP] Registered at {url}")

# Run setup
setup_routes()
write_connection_info()
