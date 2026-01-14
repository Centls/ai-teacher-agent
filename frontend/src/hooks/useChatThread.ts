import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { MessageOptions, MessageResponse, AIMessageData } from "@/types/message";
import { createMessageStream, SSEController } from "@/services/chatService";
import { fetchMessageHistory } from "@/services/chatService";

interface UseChatThreadOptions {
  threadId: string | null;
}

export interface UseChatThreadReturn {
  messages: MessageResponse[];
  isLoadingHistory: boolean;
  isSending: boolean;
  currentNode: string | null;  // 当前正在执行的节点 (用于显示 Web Search 状态)
  historyError: Error | null;
  sendError: Error | null;
  sendMessage: (text: string, opts?: MessageOptions) => Promise<void>;
  refetchMessages: () => Promise<unknown>;
  approveToolExecution: (toolCallId: string, action: "allow" | "deny") => Promise<void>;
}

export function useChatThread({ threadId }: UseChatThreadOptions): UseChatThreadReturn {
  const queryClient = useQueryClient();
  const streamRef = useRef<SSEController | null>(null);
  const currentMessageRef = useRef<MessageResponse | null>(null);
  const [sendError, setSendError] = useState<Error | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [currentNode, setCurrentNode] = useState<string | null>(null);  // 追踪当前节点

  const {
    data: messages = [],
    isLoading: isLoadingHistory,
    error: historyError,
    refetch: refetchMessagesQuery,
  } = useQuery<MessageResponse[]>({
    queryKey: ["messages", threadId],
    enabled: !!threadId,
    queryFn: () => (threadId ? fetchMessageHistory(threadId) : Promise.resolve([])),
  });

  // Ensure we fetch once the threadId becomes available (guards initial undefined cases)
  useEffect(() => {
    if (threadId) {
      void refetchMessagesQuery();
    }
  }, [threadId, refetchMessagesQuery]);

  // Shared function to handle SSE streaming for both sendMessage and approveToolExecution
  const handleStreamResponse = useCallback(
    async (streamParams: { threadId: string; text?: string; opts?: MessageOptions }) => {
      const { threadId, text = "", opts } = streamParams;

      setIsSending(true);
      setSendError(null);

      // If another stream is active, close it before starting a new one
      if (streamRef.current) {
        try {
          streamRef.current.close();
        } catch {}
      }

      try {
        // Open SSE stream to generate the assistant response
        // 使用新的回调式 API
        const stream = createMessageStream(threadId, text, opts, {
          onOpen: () => {
            // 连接已建立
          },
          onMessage: (event: MessageEvent) => {
            try {
              // Parse streaming data
              const parsed = JSON.parse(event.data);

              // Handle status events (node tracking)
              if (parsed.type === "status" && parsed.node) {
                setCurrentNode(parsed.node);
                return;
              }

              // Handle error events
              if (parsed.type === "error") {
                const errorMsg: MessageResponse = {
                  type: "error",
                  data: {
                    id: `err-${Date.now()}`,
                    content: parsed.data?.content || `⚠️ ${parsed.data?.raw_message || "发生错误"}`
                  },
                };
                queryClient.setQueryData(["messages", threadId], (old: MessageResponse[] = []) => [
                  ...old,
                  errorMsg,
                ]);
                return;
              }

              // Handle message responses
              const messageResponse = parsed as MessageResponse;

              // Extract the data from the MessageResponse
              const data = messageResponse.data as AIMessageData;

              // First chunk for this response id: create a new message entry
              if (!currentMessageRef.current || currentMessageRef.current.data.id !== data.id) {
                currentMessageRef.current = messageResponse;
                queryClient.setQueryData(["messages", threadId], (old: MessageResponse[] = []) => [
                  ...old,
                  currentMessageRef.current!,
                ]);
              } else {
                // Subsequent chunks: append content if it's a string, otherwise replace
                const currentData = currentMessageRef.current.data as AIMessageData;
                const newContent =
                  typeof data.content === "string" && typeof currentData.content === "string"
                    ? currentData.content + data.content
                    : data.content;

                currentMessageRef.current = {
                  ...currentMessageRef.current,
                  data: {
                    ...currentData,
                    content: newContent,
                    // Update tool call data if present
                    ...(data.tool_calls && { tool_calls: data.tool_calls }),
                    ...(data.additional_kwargs && { additional_kwargs: data.additional_kwargs }),
                    ...(data.response_metadata && { response_metadata: data.response_metadata }),
                  },
                };
                queryClient.setQueryData(["messages", threadId], (old: MessageResponse[] = []) => {
                  // Find the in-flight assistant message by its stable response id
                  const idx = old.findIndex((m) => m.data?.id === currentMessageRef.current!.data.id);
                  // If it's not in the cache (race or refresh), keep existing state
                  if (idx === -1) return old;
                  // Immutable update so React Query subscribers are notified
                  const clone = [...old];
                  // Replace only the updated message entry with the latest accumulated content
                  clone[idx] = currentMessageRef.current!;
                  return clone;
                });
              }
            } catch {
              // Ignore malformed chunks to keep the stream alive
            }
          },
          onError: (error: Error) => {
            // Surface the error in the chat as a message
            const errorMsg: MessageResponse = {
              type: "error",
              data: { id: `err-${Date.now()}`, content: `⚠️ ${error.message || "发生错误"}` },
            };
            queryClient.setQueryData(["messages", threadId], (old: MessageResponse[] = []) => [
              ...old,
              errorMsg,
            ]);
            // Clean up
            setIsSending(false);
            setCurrentNode(null);
            currentMessageRef.current = null;
            streamRef.current = null;
          },
          onComplete: () => {
            // 流完成，清理状态
            setIsSending(false);
            setCurrentNode(null);
            currentMessageRef.current = null;
            streamRef.current = null;
          },
        });

        streamRef.current = stream;

      } catch (err: unknown) {
        // Network/setup failure before the stream started: capture and expose the error
        setSendError(err as Error);
        setIsSending(false);
        currentMessageRef.current = null;
      }
    },
    [queryClient],
  );

  const sendMessage = useCallback(
    async (text: string, opts?: MessageOptions) => {
      // Guard: require a thread to target
      if (!threadId) return;

      // Optimistic UI: append the user's message immediately
      const tempId = `temp-${Date.now()}`;
      const userMessage: MessageResponse = {
        type: "human",
        data: {
          id: tempId,
          content: text,
          attachments: opts?.attachments,
        },
      };
      queryClient.setQueryData(["messages", threadId], (old: MessageResponse[] = []) => [
        ...old,
        userMessage,
      ]);

      // Handle the streaming response
      await handleStreamResponse({ threadId, text, opts });
    },
    [threadId, queryClient, handleStreamResponse],
  );

  const approveToolExecution = useCallback(
    async (toolCallId: string, action: "allow" | "deny") => {
      if (!threadId) return;

      // Handle the streaming response with allowTool parameter, empty content since we're resuming
      await handleStreamResponse({
        threadId,
        text: "",
        opts: { allowTool: action },
      });
    },
    [threadId, handleStreamResponse],
  );

  useEffect(
    () => () => {
      if (streamRef.current) {
        try {
          streamRef.current.close();
        } catch {}
      }
    },
    [],
  );

  return {
    messages,
    isLoadingHistory,
    isSending,
    currentNode,  // 暴露当前节点状态
    historyError: historyError as Error | null,
    sendError,
    sendMessage,
    refetchMessages: refetchMessagesQuery,
    approveToolExecution,
  };
}
