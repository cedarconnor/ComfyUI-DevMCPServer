/**
 * MCP Bridge - ComfyUI Frontend Integration
 * 
 * This script syncs the current workflow to the MCP server backend,
 * enabling AI agents to see and analyze the live workflow.
 */

import { app } from "../../scripts/app.js";
import { api } from "../../scripts/api.js";

const MCP_SYNC_DEBOUNCE_MS = 500;

let syncTimeout = null;

/**
 * Sync the current workflow to the MCP server.
 * Sends both UI format (graph) and API format (prompt) for maximum compatibility.
 */
async function syncWorkflow() {
    try {
        const graph = app.graph;
        if (!graph) {
            console.warn("[MCP Bridge] No graph available");
            return;
        }

        // Get UI format (the visual graph with positions, links, etc.)
        const uiWorkflow = graph.serialize();

        // Get API format (the prompt that can be sent to /prompt)
        // This is what ComfyUI actually executes
        let apiPrompt = null;
        try {
            apiPrompt = await app.graphToPrompt();
        } catch (e) {
            console.warn("[MCP Bridge] Could not generate API prompt:", e);
        }

        // Send to our backend
        const payload = {
            workflow: uiWorkflow,
            prompt: apiPrompt ? apiPrompt.output : null,
            timestamp: new Date().toISOString()
        };

        const response = await api.fetchApi("/mcp/workflow", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            console.warn("[MCP Bridge] Failed to sync workflow:", response.status);
        }
    } catch (error) {
        console.error("[MCP Bridge] Error syncing workflow:", error);
    }
}

/**
 * Debounced sync - avoids spamming the server on rapid changes.
 */
function debouncedSync() {
    if (syncTimeout) {
        clearTimeout(syncTimeout);
    }
    syncTimeout = setTimeout(syncWorkflow, MCP_SYNC_DEBOUNCE_MS);
}

/**
 * Register the extension with ComfyUI.
 */
app.registerExtension({
    name: "MCP.Bridge",

    async setup() {
        console.log("[MCP Bridge] Initializing...");

        // Sync on initial load
        setTimeout(syncWorkflow, 1000);

        // Listen for graph changes
        const originalSerialize = app.graph.serialize.bind(app.graph);
        app.graph.serialize = function (...args) {
            const result = originalSerialize(...args);
            debouncedSync();
            return result;
        };

        console.log("[MCP Bridge] Ready - workflow will sync to MCP server");
    },

    // Sync when nodes are added/removed
    async nodeCreated(node) {
        debouncedSync();
    },

    // Sync after workflow loads
    async loadedGraphNode(node) {
        debouncedSync();
    }
});

// Also sync when queue prompt is clicked (ensures API format is up to date)
const originalQueuePrompt = api.queuePrompt;
if (originalQueuePrompt) {
    api.queuePrompt = async function (...args) {
        await syncWorkflow();
        return originalQueuePrompt.apply(this, args);
    };
}

console.log("[MCP Bridge] Extension loaded");
