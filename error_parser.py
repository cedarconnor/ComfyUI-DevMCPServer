"""
Error Parser - Extract node context and structured error information from tracebacks.
"""

import re
from typing import Optional, Dict, Any

def parse_traceback(traceback_text: str) -> Dict[str, Any]:
    """
    Parse a Python traceback and extract structured information.
    
    Returns:
        dict with keys: error_type, error_message, file_path, line_number, node_context
    """
    result = {
        "error_type": None,
        "error_message": None,
        "file_path": None,
        "line_number": None,
        "node_context": None,
        "raw_traceback": traceback_text
    }
    
    if not traceback_text:
        return result
    
    lines = traceback_text.strip().split('\n')
    
    # Extract error type and message from last line
    # Format: "ErrorType: message" or just "ErrorType"
    if lines:
        last_line = lines[-1].strip()
        if ':' in last_line:
            parts = last_line.split(':', 1)
            result["error_type"] = parts[0].strip()
            result["error_message"] = parts[1].strip() if len(parts) > 1 else None
        else:
            result["error_type"] = last_line
    
    # Extract file and line from traceback
    # Format: File "path", line N, in function
    file_pattern = r'File "([^"]+)", line (\d+)'
    matches = re.findall(file_pattern, traceback_text)
    if matches:
        # Take the last match (closest to the error)
        result["file_path"] = matches[-1][0]
        result["line_number"] = int(matches[-1][1])
    
    # Extract node context if present in ComfyUI execution
    result["node_context"] = extract_node_context(traceback_text)
    
    return result


def extract_node_context(traceback_text: str) -> Optional[Dict[str, str]]:
    """
    Extract ComfyUI node context from a traceback.
    
    Looks for patterns like:
    - "Error occurred when executing [NodeClassName]"
    - Node ID patterns in execution traces
    """
    context = {}
    
    # Pattern 1: ComfyUI execution error format
    # "Error occurred when executing NodeClassName"
    exec_pattern = r'Error occurred when executing (\w+)'
    match = re.search(exec_pattern, traceback_text)
    if match:
        context["node_class"] = match.group(1)
    
    # Pattern 2: Look for node ID in prompt execution
    # Often appears as: 'node_id': '42' or executing node 42
    node_id_patterns = [
        r"'node_id':\s*'(\d+)'",
        r'"node_id":\s*"(\d+)"',
        r'executing node (\d+)',
        r'node (\d+)',
    ]
    
    for pattern in node_id_patterns:
        match = re.search(pattern, traceback_text, re.IGNORECASE)
        if match:
            context["node_id"] = match.group(1)
            break
    
    # Pattern 3: Look for custom node path
    custom_node_pattern = r'custom_nodes[/\\]([^/\\]+)[/\\]'
    match = re.search(custom_node_pattern, traceback_text)
    if match:
        context["custom_node"] = match.group(1)
    
    return context if context else None


def format_error_summary(parsed_error: Dict[str, Any]) -> str:
    """
    Format a parsed error into a human-readable summary.
    """
    parts = []
    
    if parsed_error.get("error_type"):
        parts.append(f"**{parsed_error['error_type']}**")
        
    if parsed_error.get("error_message"):
        parts.append(f": {parsed_error['error_message']}")
    
    if parsed_error.get("file_path"):
        parts.append(f"\n📍 Location: `{parsed_error['file_path']}` line {parsed_error.get('line_number', '?')}")
    
    node_ctx = parsed_error.get("node_context")
    if node_ctx:
        if node_ctx.get("node_class"):
            parts.append(f"\n🔧 Node Class: `{node_ctx['node_class']}`")
        if node_ctx.get("node_id"):
            parts.append(f"\n🆔 Node ID: `{node_ctx['node_id']}`")
        if node_ctx.get("custom_node"):
            parts.append(f"\n📦 Custom Node: `{node_ctx['custom_node']}`")
    
    return "".join(parts) if parts else "No error details available."
