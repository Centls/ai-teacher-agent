import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8002";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const content = searchParams.get("content") || "";
  const threadId = searchParams.get("threadId") || "unknown";
  const allowTool = searchParams.get("allowTool");
  const attachmentsStr = searchParams.get("attachments");

  let attachments = [];
  if (attachmentsStr) {
    try {
      attachments = JSON.parse(attachmentsStr);
    } catch (e) {
      console.error("Failed to parse attachments", e);
    }
  }

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      const send = (data: any) => {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
      };

      try {
        // 1. 处理审批请求 (HITL Resume)
        if (allowTool) {
          const response = await fetch(`${BACKEND_URL}/chat/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              thread_id: threadId,
              approved: allowTool === "allow",
            }),
          });

          if (!response.ok) {
            throw new Error(`Backend error: ${response.statusText}`);
          }

          const result = await response.json();

          // 发送生成结果
          if (result.generation) {
            // Allow 或 Deny 后都有 generation
            const prefix = result.status === "rejected"
              ? "✖️ 已拒绝审核。重新检索后的回答：\n\n"
              : "";

            send({
              type: "ai",
              data: {
                id: Date.now().toString(),
                content: prefix + result.generation,
              },
            });
          } else {
            // Fallback: 没有生成内容
            send({
              type: "ai",
              data: {
                id: Date.now().toString(),
                content: "已拒绝。重新检索未找到相关内容。",
              },
            });
          }

          // 结束流
          controller.enqueue(encoder.encode("event: done\n"));
          controller.enqueue(encoder.encode("data: {}\n\n"));
          controller.close();
          return;
        }

        // 2. 处理正常对话请求 (Start Chat)
        const response = await fetch(`${BACKEND_URL}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question: content,
            thread_id: threadId,
            attachments: attachments,
          }),
        });

        if (!response.ok) {
          throw new Error(`Backend error: ${response.statusText}`);
        }

        if (!response.body) {
          throw new Error("No response body");
        }

        // 读取 FastAPI SSE 流
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const dataStr = line.slice(6);
              try {
                const data = JSON.parse(dataStr);

                // 转换格式
                if (data.type === "token") {
                  send({
                    type: "ai",
                    data: {
                      id: Date.now().toString(), // ID 应该保持一致，但在流式中每次生成新ID可能会导致追加问题，前端逻辑是追加
                      content: data.content,
                    },
                  });
                } else if (data.type === "interrupt") {
                  // 伪装成 Tool Call 触发前端审批 UI
                  // data.next 包含中断的节点列表，通常是 ["human_approval"]
                  send({
                    type: "ai",
                    data: {
                      id: Date.now().toString(),
                      content: "",
                      tool_calls: [
                        {
                          name: "human_review",
                          id: `call_${Date.now()}`,
                          args: data.context || {},  // 传递后端的审核上下文
                        },
                      ],
                    },
                  });
                } else if (data.type === "error") {
                  send({
                    type: "error",
                    data: { content: data.message }
                  });
                }
              } catch (e) {
                console.error("Error parsing backend data:", e);
              }
            }
          }
        }

        controller.enqueue(encoder.encode("event: done\n"));
        controller.enqueue(encoder.encode("data: {}\n\n"));
        controller.close();

      } catch (error: any) {
        console.error("Proxy error:", error);
        controller.enqueue(encoder.encode("event: error\n"));
        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({ message: error.message || "Stream error" })}\n\n`
          )
        );
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      "Connection": "keep-alive",
    },
  });
}

