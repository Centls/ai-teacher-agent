/**
 * Agent Service - Adapted for Python Backend (White-box Reuse)
 * 
 * This file has been modified to remove Prisma and LangGraph.js dependencies.
 * All agent logic is now handled by the Python backend.
 * This service simply provides helper functions for API calls.
 */

import type { MessageResponse } from "@/types/message";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8002";

/**
 * Fetch thread history from Python backend.
 */
export async function fetchThreadHistory(threadId: string): Promise<MessageResponse[]> {
  try {
    const response = await fetch(`${BACKEND_URL}/history/${threadId}`);
    if (!response.ok) {
      console.error("Failed to fetch thread history:", response.statusText);
      return [];
    }
    const data = await response.json();

    // Transform backend format to frontend MessageResponse format
    return data.messages.map((msg: { role: string; content: string }) => ({
      type: msg.role === "human" ? "human" : "ai",
      data: {
        id: Date.now().toString(),
        content: msg.content,
      },
    }));
  } catch (e) {
    console.error("fetchThreadHistory error", e);
    return [];
  }
}

/**
 * Create a new thread on the Python backend.
 */
export async function createThread(title?: string): Promise<{ id: string; title: string } | null> {
  try {
    const response = await fetch(`${BACKEND_URL}/threads`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title || "New Chat" }),
    });
    if (!response.ok) {
      console.error("Failed to create thread:", response.statusText);
      return null;
    }
    return await response.json();
  } catch (e) {
    console.error("createThread error", e);
    return null;
  }
}

/**
 * List all threads from Python backend.
 */
export async function listThreads(): Promise<Array<{ id: string; title: string }>> {
  try {
    const response = await fetch(`${BACKEND_URL}/threads`);
    if (!response.ok) {
      console.error("Failed to list threads:", response.statusText);
      return [];
    }
    return await response.json();
  } catch (e) {
    console.error("listThreads error", e);
    return [];
  }
}

/**
 * Delete a thread from Python backend.
 */
export async function deleteThread(threadId: string): Promise<boolean> {
  try {
    const response = await fetch(`${BACKEND_URL}/threads/${threadId}`, {
      method: "DELETE",
    });
    return response.ok;
  } catch (e) {
    console.error("deleteThread error", e);
    return false;
  }
}
