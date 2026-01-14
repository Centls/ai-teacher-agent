import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

// 使用 POST 请求避免 URL 参数过长导致 431 错误
export async function POST(req: NextRequest) {
  const body = await req.json();
  const content = body.content || "";
  const threadId = body.threadId || "unknown";
  const allowTool = body.allowTool;
  const attachments = body.attachments || [];
  const enableWebSearch = body.enableWebSearch === true;

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
            enable_web_search: enableWebSearch,
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
        // 生成一个固定的消息 ID 用于整个流式会话
        const streamMessageId = `msg_${Date.now()}`;

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
                      id: streamMessageId, // 使用固定 ID 以便前端正确追加内容
                      content: data.content,
                    },
                  });
                } else if (data.type === "status") {
                  // 转发状态事件给前端
                  send({
                    type: "status",
                    node: data.node,
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
                  // 增强错误展示：显示详细的错误信息
                  let errorContent = `❌ **错误**\n\n`;

                  // 根据错误类型显示不同的图标和说明
                  const errorIcons = {
                    llm_api_error: "🌐",
                    llm_bad_request: "⚠️",
                    llm_auth_error: "🔑",
                    llm_rate_limit: "⏱️",
                    llm_connection_error: "📡",
                    vector_db_error: "📚",
                    web_search_error: "🔍",
                    backend_error: "⚙️"
                  };

                  const icon = errorIcons[data.error_type as keyof typeof errorIcons] || "❌";

                  // 构建错误消息
                  errorContent += `${icon} **${data.message || "未知错误"}**\n\n`;

                  // 显示详细信息
                  if (data.detail) {
                    errorContent += `**详细信息:**\n${data.detail}\n\n`;
                  }

                  // 针对特定错误类型给出建议
                  if (data.error_type === "llm_bad_request" && data.message.includes("欠费")) {
                    errorContent += `**解决方案:**\n`;
                    errorContent += `1. 访问阿里云控制台充值: https://home.console.aliyun.com/\n`;
                    errorContent += `2. 或切换到其他模型（修改 .env 文件）\n`;
                  } else if (data.error_type === "llm_auth_error") {
                    errorContent += `**解决方案:**\n`;
                    errorContent += `检查 .env 文件中的 OPENAI_API_KEY 是否正确\n`;
                  } else if (data.error_type === "llm_connection_error") {
                    errorContent += `**解决方案:**\n`;
                    errorContent += `1. 检查网络连接\n`;
                    errorContent += `2. 确认 API 地址是否正确\n`;
                  }

                  // 显示技术细节（可折叠）
                  if (data.technical_info && data.technical_info !== data.detail) {
                    errorContent += `\n<details>\n<summary>技术细节（点击展开）</summary>\n\n\`\`\`\n${data.technical_info}\n\`\`\`\n</details>`;
                  }

                  send({
                    type: "error",
                    data: {
                      content: errorContent,
                      error_type: data.error_type,
                      raw_message: data.message
                    }
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
