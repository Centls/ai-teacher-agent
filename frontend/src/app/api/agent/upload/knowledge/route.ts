import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
// 后台任务模式：文件传输 + 保存，2 分钟超时
export const maxDuration = 120;

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();

    // 创建 AbortController 用于超时控制（2 分钟）
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120 * 1000);

    // Forward to backend knowledge upload endpoint
    const response = await fetch(`${BACKEND_URL}/upload/knowledge`, {
      method: "POST",
      body: formData,
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    if (!response.ok) {
      const errorText = await response.text();
      console.error("Backend upload error:", errorText);
      throw new Error(`Backend upload failed: ${response.statusText}`);
    }

    const result = await response.json();
    return NextResponse.json(result);

  } catch (error) {
    console.error("Knowledge upload proxy error:", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Upload failed",
      },
      { status: 500 },
    );
  }
}