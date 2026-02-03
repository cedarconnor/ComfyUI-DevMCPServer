"""
Health Check - Validate workflows for common issues before running.
"""

from typing import Dict, Any, List

def check_workflow_health(workflow: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze a workflow for potential issues.
    
    Args:
        workflow: The ComfyUI workflow JSON (API format or UI format)
    
    Returns:
        dict with keys: healthy, issues, warnings, node_count
    """
    result = {
        "healthy": True,
        "issues": [],
        "warnings": [],
        "node_count": 0,
        "summary": ""
    }
    
    if not workflow:
        result["healthy"] = False
        result["issues"].append({
            "type": "empty_workflow",
            "message": "Workflow is empty or not loaded"
        })
        return result
    
    # Handle nested structures from our state
    if "workflow" in workflow:
        workflow = workflow["workflow"]
    if "prompt" in workflow and isinstance(workflow.get("prompt"), dict):
        # If we have an API prompt, use that
        workflow = workflow["prompt"]
    
    # Detect format: UI format has "nodes" as a list, API format has node IDs as keys
    is_ui_format = "nodes" in workflow and isinstance(workflow.get("nodes"), list)
    
    if is_ui_format:
        # UI Format: { nodes: [...], links: [...], groups: [...], ... }
        nodes_list = workflow.get("nodes", [])
        result["node_count"] = len(nodes_list)
        
        if not nodes_list:
            result["warnings"].append({
                "type": "no_nodes",
                "message": "Workflow contains no nodes"
            })
            result["summary"] = "⚠️ Workflow contains no nodes"
            return result
        
        # Build node lookup by ID
        nodes_by_id = {}
        for node in nodes_list:
            if isinstance(node, dict) and "id" in node:
                nodes_by_id[node["id"]] = node
        
        # Check links for issues
        links = workflow.get("links", [])
        linked_nodes = set()
        
        for link in links:
            if isinstance(link, list) and len(link) >= 4:
                # link format: [link_id, source_node, source_slot, target_node, target_slot, type]
                source_node = link[1]
                target_node = link[3]
                linked_nodes.add(source_node)
                linked_nodes.add(target_node)
        
        # Find orphan nodes
        all_ids = set(nodes_by_id.keys())
        orphans = all_ids - linked_nodes
        
        # Exclude common source nodes
        source_types = {"LoadImage", "LoadCheckpoint", "CheckpointLoaderSimple", "EmptyLatentImage", "CLIPTextEncode", "KSampler"}
        
        for orphan_id in orphans:
            node = nodes_by_id.get(orphan_id, {})
            node_type = node.get("type", "Unknown")
            if node_type not in source_types:
                result["warnings"].append({
                    "type": "orphan_node",
                    "node_id": orphan_id,
                    "node_class": node_type,
                    "message": f"Node {orphan_id} ({node_type}) appears disconnected"
                })
    else:
        # API Format: { "1": { class_type: ..., inputs: {...} }, "2": {...}, ... }
        # Filter to only include node entries (skip non-dict values and meta keys)
        nodes = {}
        for k, v in workflow.items():
            if isinstance(v, dict) and "class_type" in v:
                nodes[k] = v
        
        result["node_count"] = len(nodes)
        
        if not nodes:
            result["warnings"].append({
                "type": "no_nodes",
                "message": "Workflow contains no nodes (or unsupported format)"
            })
            result["summary"] = "⚠️ No valid nodes found"
            return result
        
        # Track connections
        connected_inputs = set()
        connected_outputs = set()
        
        for node_id, node_data in nodes.items():
            inputs = node_data.get("inputs", {})
            class_type = node_data.get("class_type", "Unknown")
            
            for input_name, input_value in inputs.items():
                if input_value is None:
                    result["warnings"].append({
                        "type": "null_input",
                        "node_id": node_id,
                        "node_class": class_type,
                        "input_name": input_name,
                        "message": f"Node {node_id} ({class_type}) has null input '{input_name}'"
                    })
                
                # Track connections
                if isinstance(input_value, list) and len(input_value) == 2:
                    source_node = str(input_value[0])
                    connected_outputs.add(source_node)
                    connected_inputs.add(node_id)
        
        # Find orphans
        all_node_ids = set(str(nid) for nid in nodes.keys())
        orphans = all_node_ids - connected_inputs - connected_outputs
        
        source_types = {"LoadImage", "LoadCheckpoint", "CheckpointLoaderSimple", "EmptyLatentImage", "CLIPTextEncode", "KSampler"}
        
        for orphan_id in orphans:
            node_data = nodes.get(orphan_id, {})
            class_type = node_data.get("class_type", "")
            if class_type not in source_types:
                result["warnings"].append({
                    "type": "orphan_node",
                    "node_id": orphan_id,
                    "node_class": class_type,
                    "message": f"Node {orphan_id} ({class_type}) appears disconnected"
                })
    
    # Set overall health
    if result["issues"]:
        result["healthy"] = False
    
    # Generate summary
    issue_count = len(result["issues"])
    warning_count = len(result["warnings"])
    
    if issue_count == 0 and warning_count == 0:
        result["summary"] = f"✅ Workflow looks healthy ({result['node_count']} nodes)"
    elif issue_count == 0:
        result["summary"] = f"⚠️ {warning_count} warning(s) found ({result['node_count']} nodes)"
    else:
        result["summary"] = f"❌ {issue_count} issue(s), {warning_count} warning(s) ({result['node_count']} nodes)"
    
    return result


def format_health_report(health_result: Dict[str, Any]) -> str:
    """Format a health check result as a readable report."""
    lines = [health_result["summary"], ""]
    
    if health_result["issues"]:
        lines.append("**Issues:**")
        for issue in health_result["issues"]:
            lines.append(f"- ❌ {issue['message']}")
        lines.append("")
    
    if health_result["warnings"]:
        lines.append("**Warnings:**")
        for warning in health_result["warnings"][:10]:  # Limit to 10
            lines.append(f"- ⚠️ {warning['message']}")
        if len(health_result["warnings"]) > 10:
            lines.append(f"- ... and {len(health_result['warnings']) - 10} more")
    
    return "\n".join(lines)
