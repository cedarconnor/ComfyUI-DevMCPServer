
import server
from aiohttp import web
# Import the persistent state
from . import state

async def workflow_handler(request):
    """Handle get/set of current workflow."""
    if request.method == "POST":
        data = await request.json()
        # Ensure we store it in the expected structure
        if "workflow" in data:
             state.current_workflow = data
        else:
             state.current_workflow = {"workflow": data}
        return web.json_response({"status": "ok"})
    else:
        # Return nested structure if it's just raw data
        if "workflow" not in state.current_workflow and state.current_workflow:
            return web.json_response({"workflow": state.current_workflow})
        return web.json_response(state.current_workflow)

async def run_node_handler(request):
    """Run specific nodes."""
    try:
        data = await request.json()
        node_id = data.get("node_id")
        
        # Access ComfyUI's PromptServer instance
        s = server.PromptServer.instance
        
        # We need the current workflow prompt to queue it
        # If we have the live workflow state, use it
        prompt = state.current_workflow.get("workflow", {})
        if not prompt:
             return web.json_response({"error": "No active workflow to run"}, status=400)

        # Generate a prompt ID
        import uuid
        prompt_id = str(uuid.uuid4())
        
        # Queue using the internal prompt queue
        node_ids_to_execute = [str(node_id)] if node_id else []
        
        s.prompt_queue.put(
            (0, prompt_id, prompt, {"client_id": "claude-mcp"}, node_ids_to_execute)
        )
        
        return web.json_response({"status": "queued", "prompt_id": prompt_id, "node_id": node_id})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)
