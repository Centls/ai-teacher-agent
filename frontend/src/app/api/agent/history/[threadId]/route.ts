import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8002";

export async function GET(_req: Request, { params }: { params: Promise<{ threadId: string }> }) {
  try {
    const { threadId } = await params;
    const res = await fetch(`${BACKEND_URL}/history/${threadId}`);
    if (!res.ok) throw new Error(res.statusText);
    const data = await res.json();
    return NextResponse.json(data, { status: 200 });
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
