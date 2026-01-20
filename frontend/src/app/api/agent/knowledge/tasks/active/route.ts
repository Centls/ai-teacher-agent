import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

/**
 * 获取当前活跃的上传任务
 */
export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/knowledge/tasks/active`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`Backend error: ${response.statusText}`);
    }

    const result = await response.json();
    return NextResponse.json(result);

  } catch (error) {
    console.error("Get active tasks error:", error);
    return NextResponse.json(null);
  }
}