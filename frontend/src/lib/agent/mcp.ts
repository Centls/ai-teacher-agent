/**
 * MCP Configuration - Stubbed (White-box Reuse)
 * 
 * MCP Server configuration is now managed by the Python backend.
 * This file is a stub to prevent import errors.
 */

export async function loadMCPServers(): Promise<unknown[]> {
  // MCP servers are managed by Python backend
  console.log("[MCP] MCP servers are managed by Python backend.");
  return [];
}

export async function getMCPTools(): Promise<unknown[]> {
  // MCP tools are injected by Python backend
  return [];
}
