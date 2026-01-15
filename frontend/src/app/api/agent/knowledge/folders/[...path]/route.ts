import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

/**
 * 删除指定文件夹及其所有文件
 * DELETE /api/agent/knowledge/folders/[...path]
 */
export async function DELETE(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    const { path } = await params;
    const folderPath = path.join("/");

    if (!folderPath) {
      return NextResponse.json(
        { error: "文件夹路径不能为空" },
        { status: 400 }
      );
    }

    const response = await fetch(
      `${BACKEND_URL}/knowledge/folders/${encodeURIComponent(folderPath)}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      return NextResponse.json(
        { error: errorData.detail || `后端错误: ${response.statusText}` },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    console.error("Delete folder error:", error);
    return NextResponse.json(
      { error: error.message || "删除文件夹失败" },
      { status: 500 }
    );
  }
}
