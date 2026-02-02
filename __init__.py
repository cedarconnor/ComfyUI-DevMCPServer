
import server
import aiohttp
from aiohttp import web
import os
import json
import importlib
from . import handlers

# Define the directory for the node (standard boilerplate)
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}
WEB_DIRECTORY = "./js"

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]

# =============================================================================
# Routes & Handlers (Hot Reload Proxy)
# =============================================================================

async def workflow_handler(request):
    """Proxy to handlers.workflow_handler with auto-reload."""
    importlib.reload(handlers)
    return await handlers.workflow_handler(request)

async def run_node_handler(request):
    """Proxy to handlers.run_node_handler with auto-reload."""
    importlib.reload(handlers)
    return await handlers.run_node_handler(request)

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
