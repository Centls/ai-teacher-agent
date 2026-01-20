import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";
// 后台任务模式下，文件保存很快，无需长超时
// 同步模式仍保留 10 分钟超时
export const maxDuration = 600;

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();

    // 创建 AbortController 用于超时控制
    const controller = new AbortController();
    // 后台任务模式：文件保存很快，30 秒足够
    // 同步模式：保留 10 分钟超时
    const isAsyncMode = formData.get("async_mode") !== "false";
    const timeoutMs = isAsyncMode ? 30 * 1000 : 10 * 60 * 1000;
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

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