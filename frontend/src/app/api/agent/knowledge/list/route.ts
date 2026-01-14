import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

export async function GET(req: NextRequest) {
  try {
    const response = await fetch(`${BACKEND_URL}/knowledge/list`, {
      method: "GET",
    });

    if (!response.ok) {
      return NextResponse.json(
        { error: `Backend error: ${response.statusText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    console.error("List knowledge error:", error);
    return NextResponse.json(
      { error: error.message || "List failed" },
      { status: 500 }
    );
  }
}
