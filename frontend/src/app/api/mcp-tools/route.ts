/**
 * MCP Tools API - Stubbed (White-box Reuse)
 * 
 * MCP Tools are now managed by the Python backend.
 * This route returns empty data to prevent errors.
 */

import { NextResponse } from "next/server";

export async function GET() {
  // MCP tools are managed by Python backend
  return NextResponse.json([]);
}
