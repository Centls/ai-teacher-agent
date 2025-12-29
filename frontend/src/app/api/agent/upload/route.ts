import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8002";

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();

    const response = await fetch(`${BACKEND_URL}/upload`, {
      method: "POST",
      body: formData,
      // fetch automatically sets Content-Type for FormData
    });

    if (!response.ok) {
      throw new Error(`Backend upload failed: ${response.statusText}`);
    }

    const result = await response.json();

    // Map backend response to frontend expected format
    return NextResponse.json({
      success: true,
      url: result.filename, // Use filename as URL/key since we don't have a real URL
      key: result.filename,
      name: result.filename,
      type: "application/octet-stream", // Dummy type
      size: 0, // Dummy size
    });

  } catch (error) {
    console.error("Upload proxy error:", error);
    return NextResponse.json(
      {
        error: error instanceof Error ? error.message : "Upload failed",
        field: "server",
      },
      { status: 500 },
    );
  }
}
