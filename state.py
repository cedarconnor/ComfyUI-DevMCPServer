"""
Persistent state for the MCP server.
This module is NOT reloaded during hot-reload, preserving data.
"""

# Store the current workflow state (pushed from frontend or retrieved)
current_workflow = {}

# Error history (max 20 entries)
error_history = []
MAX_ERROR_HISTORY = 20

# Last error with full context
last_error = None


def add_error(error_info: dict):
    """Add an error to the history."""
    global last_error, error_history
    
    last_error = error_info
    error_history.append(error_info)
    
    # Trim to max size
    if len(error_history) > MAX_ERROR_HISTORY:
        error_history = error_history[-MAX_ERROR_HISTORY:]
