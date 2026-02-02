"""
Persistent state for the MCP server.
This module is NOT reloaded during hot-reload, preserving data.
"""

# Store the current workflow state (pushed from frontend or retrieved)
current_workflow = {}
