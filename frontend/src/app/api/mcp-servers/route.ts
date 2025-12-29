/**
 * MCP Servers API - Stubbed (White-box Reuse)
 * 
 * MCP Server configuration is now managed by the Python backend.
 * This route returns empty data to prevent errors.
 */

import { NextResponse } from "next/server";

export async function GET() {
  // MCP servers are managed by Python backend
  return NextResponse.json([]);
}

export async function POST() {
  return NextResponse.json({ error: "MCP configuration is managed by backend" }, { status: 501 });
}

export async function DELETE() {
  return NextResponse.json({ error: "MCP configuration is managed by backend" }, { status: 501 });
}
