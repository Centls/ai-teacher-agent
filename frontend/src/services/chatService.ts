import type { MessageOptions, MessageResponse, Thread } from "@/types/message";

export interface ChatServiceConfig {
  baseUrl?: string;
  endpoints?: {
    history?: string;
    chat?: string;
    stream?: string;
    threads?: string;
  };
  headers?: Record<string, string>;
}

const config: ChatServiceConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_BASE_URL || "/api/agent",
  endpoints: {
    history: "/history",
    chat: "/chat",
    stream: "/stream",
    threads: "/threads",
  },
};

function getUrl(endpoint: keyof Required<ChatServiceConfig>["endpoints"]): string {
  return `${config.baseUrl}${config.endpoints?.[endpoint] || ""}`;
}

export async function fetchMessageHistory(threadId: string): Promise<MessageResponse[]> {
  const response = await fetch(`${getUrl("history")}/${threadId}`, {
    headers: config.headers,
  });
  if (!response.ok) {
    throw new Error("Failed to load history");
  }
  const data = await response.json();
  return data as MessageResponse[];
}

/**
 * SSE 事件处理器接口
 */
export interface SSEHandlers {
  onMessage?: (event: MessageEvent) => void;
  onError?: (error: Error) => void;
  onOpen?: () => void;
  onComplete?: () => void;  // 流完成时调用
}

/**
 * SSE 连接控制器
 */
export interface SSEController {
  close: () => void;
}

/**
 * 创建消息流 - 使用 POST 请求避免 URL 参数过长导致 431 错误
 * 返回一个控制器对象，用于关闭连接
 */
export function createMessageStream(
  threadId: string,
  message: string,
  opts?: MessageOptions,
  handlers?: SSEHandlers,
): SSEController {
  const abortController = new AbortController();

  // 构建请求体
  const body = {
    content: message,
    threadId,
    model: opts?.model,
    tools: opts?.tools,
    allowTool: opts?.allowTool,
    denyAction: opts?.denyAction,  // 拒绝后的操作选项
    approveAllTools: opts?.approveAllTools,
    enableWebSearch: opts?.enableWebSearch,
    attachments: opts?.attachments || [],
  };

  // 使用 fetch + POST 发送请求
  fetch(getUrl("stream"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...config.headers,
    },
    body: JSON.stringify(body),
    signal: abortController.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      handlers?.onOpen?.();

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error("No response body");
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data.trim()) {
              // 创建模拟的 MessageEvent
              const event = new MessageEvent("message", { data });
              handlers?.onMessage?.(event);
            }
          } else if (line.startsWith("event: done")) {
            // 流结束
            handlers?.onComplete?.();
            return;
          } else if (line.startsWith("event: error")) {
            // 等待下一行获取错误数据
            continue;
          }
        }
      }
    })
    .catch((error) => {
      if (error.name !== "AbortError") {
        handlers?.onError?.(error);
      }
    });

  return {
    close: () => abortController.abort(),
  };
}

export async function fetchThreads(): Promise<Thread[]> {
  const response = await fetch(getUrl("threads"), {
    headers: config.headers,
  });
  if (!response.ok) {
    throw new Error("Failed to load threads");
  }
  return await response.json();
}

export async function createNewThread(): Promise<Thread> {
  const response = await fetch(getUrl("threads"), {
    method: "POST",
    headers: config.headers,
  });
  if (!response.ok) {
    throw new Error("Failed to create thread");
  }
  return await response.json();
}

export async function deleteThread(threadId: string): Promise<void> {
  const response = await fetch(getUrl("threads"), {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...config.headers,
    },
    body: JSON.stringify({ id: threadId }),
  });
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error || "Failed to delete thread");
  }
}
