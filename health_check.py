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
    
    # Handle nested workflow structure
    if "workflow" in workflow:
        workflow = workflow["workflow"]
    
    # Get nodes (could be dict or list depending on format)
    nodes = workflow if isinstance(workflow, dict) else {}
    result["node_count"] = len(nodes)
    
    if not nodes:
        result["warnings"].append({
            "type": "no_nodes",
            "message": "Workflow contains no nodes"
        })
    
    # Track connections for orphan detection
    connected_inputs = set()
    connected_outputs = set()
    
    for node_id, node_data in nodes.items():
        if not isinstance(node_data, dict):
            continue
            
        # Check for missing inputs
        inputs = node_data.get("inputs", {})
        class_type = node_data.get("class_type", "Unknown")
        
        # Check for None/null required inputs (common issue)
        for input_name, input_value in inputs.items():
            if input_value is None:
                result["warnings"].append({
                    "type": "null_input",
                    "node_id": node_id,
                    "node_class": class_type,
                    "input_name": input_name,
                    "message": f"Node {node_id} ({class_type}) has null input '{input_name}'"
                })
            
            # Track connections (input_value is [node_id, output_index] for connections)
            if isinstance(input_value, list) and len(input_value) == 2:
                source_node = str(input_value[0])
                connected_outputs.add(source_node)
                connected_inputs.add(node_id)
    
    # Find orphan nodes (nodes with no connections to other nodes)
    all_node_ids = set(str(nid) for nid in nodes.keys())
    orphans = all_node_ids - connected_inputs - connected_outputs
    
    # Exclude common source nodes that don't need inputs
    source_node_types = {"LoadImage", "LoadCheckpoint", "KSampler", "EmptyLatent", "CLIPTextEncode"}
    
    for orphan_id in orphans:
        node_data = nodes.get(orphan_id) or nodes.get(int(orphan_id), {})
        if isinstance(node_data, dict):
            class_type = node_data.get("class_type", "")
            if class_type not in source_node_types:
                result["warnings"].append({
                    "type": "orphan_node",
                    "node_id": orphan_id,
                    "node_class": class_type,
                    "message": f"Node {orphan_id} ({class_type}) appears disconnected from the workflow"
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
