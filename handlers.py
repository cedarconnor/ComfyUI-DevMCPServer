
import server
from aiohttp import web
# Import the persistent state
from . import state

async def workflow_handler(request):
    """Handle get/set of current workflow."""
    if request.method == "POST":
        data = await request.json()
        
        # Store the full payload (may contain workflow, prompt, timestamp)
        state.current_workflow = data
        
        # Also store the API-ready prompt separately if provided
        if "prompt" in data and data["prompt"]:
            state.current_prompt = data["prompt"]
        
        return web.json_response({"status": "ok"})
    else:
        # Return the stored workflow data
        return web.json_response(state.current_workflow if state.current_workflow else {})

async def run_node_handler(request):
    """Run specific nodes."""
    try:
        data = await request.json()
        node_ids = data.get("node_ids") or data.get("node_id")
        
        # Normalize to list
        if node_ids is None:
            node_ids_to_execute = []
        elif isinstance(node_ids, list):
            node_ids_to_execute = [str(nid) for nid in node_ids]
        else:
            node_ids_to_execute = [str(node_ids)]
        
        # Access ComfyUI's PromptServer instance
        s = server.PromptServer.instance
        
        # Use API-ready prompt if available, otherwise try workflow
        prompt = state.current_prompt
        if not prompt:
            prompt = state.current_workflow.get("prompt")
        if not prompt:
            # Last resort: try to use workflow (may not work)
            prompt = state.current_workflow.get("workflow", {})
        
        if not prompt:
            return web.json_response({"error": "No active workflow to run. Open a workflow in ComfyUI first."}, status=400)

        # Generate a prompt ID
        import uuid
        prompt_id = str(uuid.uuid4())
        
        # Queue using the internal prompt queue
        s.prompt_queue.put(
            (0, prompt_id, prompt, {"client_id": "mcp-server"}, node_ids_to_execute)
        )
        
        return web.json_response({"status": "queued", "prompt_id": prompt_id, "node_ids": node_ids_to_execute})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)
