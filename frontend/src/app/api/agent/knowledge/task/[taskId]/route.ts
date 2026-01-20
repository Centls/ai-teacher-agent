import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

/**
 * 查询上传任务状态
 *
 * 返回：
 * - status: pending | processing | completed | failed
 * - total_files: 总文件数
 * - completed_files: 已完成文件数
 * - current_file: 当前正在处理的文件名
 * - results: 完成后的结果列表
 * - error: 错误信息（如果失败）
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ taskId: string }> }
) {
  try {
    const { taskId } = await params;

    const response = await fetch(`${BACKEND_URL}/knowledge/task/${taskId}`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    if (!response.ok) {
      if (response.status === 404) {
        return NextResponse.json(
          { error: "Task not found" },
          { status: 404 }
        );
      }
      throw new Error(`Backend error: ${response.statusText}`);
    }

    const result = await response.json();
    return NextResponse.json(result);

  } catch (error) {
    console.error("Task status query error:", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Query failed",
      },
      { status: 500 }
    );
  }
}