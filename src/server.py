import os
from dotenv import load_dotenv
load_dotenv() # Load env vars before importing other modules

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Body, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import asyncio
import sqlite3
import uuid
import re
from datetime import datetime
import aiosqlite

from src.core.factory import GraphFactory
from src.core.lifecycle import LifecycleManager
from src.agents.marketing import create_marketing_graph
from src.services.rag.multimodal_pipeline import MultimodalRAGPipeline
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from src.core.store import AsyncSQLiteStore

# Ensure data directory exists for all databases
os.makedirs("data", exist_ok=True)

# Global Store (Persistent SQLite-based long-term memory)
# 用于存储用户偏好规则等跨对话的持久化数据
store = AsyncSQLiteStore(db_path="data/user_preferences.db")

# Initialize App
app = FastAPI(
    title="AI Teacher Nexus API",
    description="Backend API for AI Teacher Nexus Workbench",
    version="2.0.0"
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "*"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class StreamRequest(BaseModel):
    question: str
    thread_id: str
    attachments: Optional[List[Dict]] = None
    enable_web_search: Optional[bool] = False  # 前端开关控制联网搜索

class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool
    feedback: Optional[str] = None
    deny_action: Optional[str] = None  # "retry" | "web_search" | "cancel"

class StateRequest(BaseModel):
    thread_id: str

class ThreadCreateRequest(BaseModel):
    title: Optional[str] = "New Chat"

# =============================================================================
# Core Chat Endpoints
# =============================================================================

@app.post("/chat/stream")
async def chat_stream(request: StreamRequest):
    """
    流式对话接口 (支持 HITL)
    """
    question = request.question
    thread_id = request.thread_id
    attachments = request.attachments or []
    enable_web_search = request.enable_web_search or False

    print(f"[SERVER] Received request: question='{question}', enable_web_search={enable_web_search}")

    # Process attachments: Append content to question
    # Store attachment metadata separately for history display
    attachment_metadata = []
    if attachments:
        attachment_text = "\n\n--- Attachments ---\n"
        for att in attachments:
            # att structure from frontend: { "name": "...", "content": "...", ... }
            # Also support legacy "filename" field for backwards compatibility
            if att.get("content"):
                file_name = att.get("name") or att.get("filename") or "Unknown"
                attachment_text += f"\n[File: {file_name}]\n{att.get('content')}\n"
                # Store metadata for history display
                attachment_metadata.append({
                    "key": att.get("key") or att.get("name") or file_name,
                    "name": file_name,
                    "type": att.get("type", "application/octet-stream"),
                    "size": att.get("size", 0),
                    "url": att.get("url", "")
                })

        question += attachment_text

    # Store original question (without attachments) for display
    original_question = request.question

    # Update thread title if it's a new thread or generic title
    update_thread_title(thread_id, question)

    async def generate():
        # Clean implementation using from_conn_string
        async with AsyncSqliteSaver.from_conn_string("data/checkpoints.sqlite") as checkpointer:
            # Compile Graph
            marketing_graph = create_marketing_graph(checkpointer=checkpointer, store=store, with_hitl=True)

            config = {"configurable": {"thread_id": thread_id}}

            # 初始输入 - 使用 HumanMessage 对象而不是元组
            from langchain_core.messages import HumanMessage
            # Store original question and attachment metadata in additional_kwargs for history display
            human_msg = HumanMessage(
                content=question,
                additional_kwargs={
                    "original_content": original_question,
                    "attachments": attachment_metadata
                } if attachment_metadata else {}
            )
            inputs = {
                "question": question,
                "messages": [human_msg],
                "force_web_search": enable_web_search,  # 传递前端开关状态
                "retry_count": 0,  # 每次新问答都重置重试计数
                "skip_hitl": False  # 确保不跳过审批
            }
            
            try:
                # 追踪当前正在执行的节点
                current_node = None

                async for event in marketing_graph.astream_events(inputs, config, version="v2"):
                    kind = event["event"]

                    # 追踪节点切换
                    if kind == "on_chain_start":
                        node_name = event.get("name", "")
                        if node_name in ["retrieve", "grade_documents", "generate", "transform_query", "check_answer_quality", "learning", "web_search"]:
                            current_node = node_name
                            yield f"data: {json.dumps({'type': 'status', 'node': node_name})}\n\n"

                    # 只流式输出 generate 节点的内容 (排除内部结构化输出)
                    if kind == "on_chat_model_stream" and current_node == "generate":
                        content = event["data"]["chunk"].content
                        if content:
                            yield f"data: {json.dumps({'content': content, 'type': 'token'})}\n\n"

                # 检查是否中断 (HITL)
                state = await marketing_graph.aget_state(config)
                if state.next:
                    # 获取 interrupt() 传递的上下文
                    interrupt_context = {}
                    if hasattr(state, 'tasks') and state.tasks:
                        # LangGraph v2: tasks 中包含 interrupt 数据
                        for task in state.tasks:
                            if hasattr(task, 'interrupts') and task.interrupts:
                                # interrupts 是列表，取第一个
                                interrupt_context = task.interrupts[0].value if task.interrupts else {}
                                break

                    yield f"data: {json.dumps({'type': 'interrupt', 'next': state.next, 'context': interrupt_context})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    
            except Exception as e:
                print(f"Stream Error: {e}")
                import traceback
                traceback.print_exc()

                # Enhanced error classification
                error_type = "backend_error"
                error_detail = str(e)
                user_message = "Backend error, check logs"

                # Detect OpenAI/Aliyun API errors
                if "openai" in str(type(e).__module__).lower():
                    error_type = "llm_api_error"

                    if "BadRequestError" in str(type(e).__name__):
                        error_type = "llm_bad_request"

                        if "Arrearage" in str(e) or "overdue" in str(e).lower():
                            user_message = "Aliyun account overdue, please top up"
                            error_detail = "Aliyun account balance insufficient, visit https://home.console.aliyun.com/"
                        elif "model" in str(e).lower() and "not found" in str(e).lower():
                            user_message = "Model name error, check .env config"
                            error_detail = f"Model not found: {str(e)}"
                        elif "api" in str(e).lower() and ("key" in str(e).lower() or "auth" in str(e).lower()):
                            user_message = "API Key invalid, check .env config"
                            error_detail = "Aliyun API Key invalid or expired"
                        else:
                            user_message = f"Model API request failed: {str(e)[:100]}"

                    elif "AuthenticationError" in str(type(e).__name__):
                        error_type = "llm_auth_error"
                        user_message = "API Key authentication failed"
                        error_detail = "API Key invalid or expired"

                    elif "RateLimitError" in str(type(e).__name__):
                        error_type = "llm_rate_limit"
                        user_message = "API rate limit exceeded, retry later"
                        error_detail = "Model API rate limit exceeded"

                    elif "APIConnectionError" in str(type(e).__name__):
                        error_type = "llm_connection_error"
                        user_message = "Cannot connect to model API"
                        error_detail = "Network connection failed or API unavailable"

                elif "ChromaDB" in str(e) or "chroma" in str(e).lower():
                    error_type = "vector_db_error"
                    user_message = "Knowledge base error"
                    error_detail = f"ChromaDB error: {str(e)}"

                elif "DuckDuckGo" in str(e) or "search" in str(e).lower():
                    error_type = "web_search_error"
                    user_message = "Web search failed"
                    error_detail = f"Search engine error: {str(e)}"

                # 构建错误响应
                error_response = json.dumps({
                    'type': 'error',
                    'error_type': error_type,
                    'message': user_message,
                    'detail': error_detail,
                    'technical_info': str(e)
                }, ensure_ascii=False)
                yield f"data: {error_response}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

from src.agents.supervisor.graph import create_nexus_supervisor

@app.post("/chat/supervisor")
async def chat_supervisor(request: StreamRequest):
    """
    Supervisor 2.0 对话接口 (多智能体调度)
    """
    question = request.question
    thread_id = request.thread_id
    
    update_thread_title(thread_id, question)
    
    async def generate():
        async with AsyncSqliteSaver.from_conn_string("data/checkpoints.sqlite") as checkpointer:
            # Create Supervisor Graph
            supervisor_graph = create_nexus_supervisor(checkpointer=checkpointer)
            
            config = {"configurable": {"thread_id": thread_id}}

            # 使用 HumanMessage 对象
            from langchain_core.messages import HumanMessage
            inputs = {"messages": [HumanMessage(content=question)]}
            
            try:
                # 追踪当前正在执行的节点
                current_node = None

                async for event in supervisor_graph.astream_events(inputs, config, version="v2"):
                    kind = event["event"]

                    # 追踪节点切换
                    if kind == "on_chain_start":
                        node_name = event.get("name", "")
                        if node_name in ["MarketingTeacher", "GeneralAssistant", "supervisor", "generate"]:
                            current_node = node_name
                            yield f"data: {json.dumps({'type': 'status', 'node': node_name})}\n\n"

                    # 只流式输出 agent 节点的内容 (排除内部结构化输出)
                    if kind == "on_chat_model_stream" and current_node in ["MarketingTeacher", "GeneralAssistant", "generate"]:
                        content = event["data"]["chunk"].content
                        if content:
                            yield f"data: {json.dumps({'content': content, 'type': 'token'})}\n\n"

                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    
            except Exception as e:
                print(f"Supervisor Error: {e}")
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )

@app.post("/chat/state")
async def get_state(request: StateRequest):
    """
    获取当前状态 (用于检查是否需要审批)
    """
    async with AsyncSqliteSaver.from_conn_string("data/checkpoints.sqlite") as checkpointer:
        marketing_graph = create_marketing_graph(checkpointer=checkpointer, store=store, with_hitl=True)
        
        config = {"configurable": {"thread_id": request.thread_id}}
        state = await marketing_graph.aget_state(config)
        
        return {
            "next": state.next,
            "values": {k: v for k, v in state.values.items() if k != "messages"}
        }

@app.post("/chat/approve")
async def approve_step(request: ApproveRequest):
    """
    审批并恢复执行

    deny_action 选项:
    - "retry": 重新检索知识库
    - "web_search": 使用 Web 搜索
    - "cancel": 取消（由前端处理，不会调用此端点）
    """
    print(f"[APPROVE] thread_id={request.thread_id}, approved={request.approved}, deny_action={request.deny_action}")

    async with AsyncSqliteSaver.from_conn_string("data/checkpoints.sqlite") as checkpointer:
        # CRITICAL: 始终使用 with_hitl=True 保持 graph 结构一致
        # 用户拒绝时，通过状态更新而非重新编译 graph 来控制流程
        marketing_graph = create_marketing_graph(checkpointer=checkpointer, store=store, with_hitl=True)

        config = {"configurable": {"thread_id": request.thread_id}}

        # Check current state first
        current_state = await marketing_graph.aget_state(config)
        print(f"[APPROVE] Current state next: {current_state.next if current_state else 'None'}")

        # 构建恢复值
        if request.approved:
            resume_value = "approved"
        else:
            # 根据 deny_action 确定恢复值
            deny_action = request.deny_action or "retry"
            if deny_action == "web_search":
                resume_value = "web_search"  # 触发 Web 搜索
            else:
                resume_value = "rejected"  # 重新检索

        if request.feedback:
            resume_value = request.feedback

        print(f"[APPROVE] Resuming with value: {resume_value}")

        try:
            # Use Command(resume=...) to resume from interrupt()
            result = await marketing_graph.ainvoke(Command(resume=resume_value), config)
            print(f"[APPROVE] Result keys: {result.keys() if result else 'None'}")

            # 检查是否再次中断（重新检索后需要再次审批）
            new_state = await marketing_graph.aget_state(config)
            if new_state.next:
                print(f"[APPROVE] Graph interrupted again at: {new_state.next}")
                # 获取 interrupt() 传递的上下文
                interrupt_context = {}
                if hasattr(new_state, 'tasks') and new_state.tasks:
                    for task in new_state.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            interrupt_context = task.interrupts[0].value if task.interrupts else {}
                            break

                return {
                    "status": "interrupt",
                    "next": list(new_state.next),
                    "context": interrupt_context
                }

            if request.approved:
                return {"status": "approved", "generation": result.get("generation")}
            else:
                # Deny: 返回最终生成的内容（如果有）
                generation = result.get("generation", "重新检索后未找到相关内容。")
                action_label = "Web 搜索" if request.deny_action == "web_search" else "重新检索"
                return {
                    "status": "rejected",
                    "action": request.deny_action or "retry",
                    "message": f"用户拒绝。执行{action_label}。",
                    "generation": generation
                }
        except Exception as e:
            print(f"[APPROVE] Error: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Thread Management (SQLite)
# =============================================================================

def get_db():
    conn = sqlite3.connect("data/threads.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS threads (
            id TEXT PRIMARY KEY,
            title TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def update_thread_title(thread_id: str, first_message: str):
    """Update thread title based on first message (if it's a new thread or generic title)"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT title FROM threads WHERE id = ?", (thread_id,))
    row = cursor.fetchone()
    
    if row is None:
        title = first_message[:50] + ("..." if len(first_message) > 50 else "")
        now = datetime.now().isoformat()
        cursor.execute("INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                       (thread_id, title, now, now))
        conn.commit()
    elif row["title"] == "New Chat":
        title = first_message[:50] + ("..." if len(first_message) > 50 else "")
        now = datetime.now().isoformat()
        cursor.execute("UPDATE threads SET title = ?, updated_at = ? WHERE id = ?",
                       (title, now, thread_id))
        conn.commit()
    
    conn.close()

@app.get("/threads")
async def list_threads():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, created_at, updated_at FROM threads ORDER BY updated_at DESC")
    threads = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return threads

@app.post("/threads")
async def create_thread(request: ThreadCreateRequest = Body(...)):
    thread_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("INSERT INTO threads (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                 (thread_id, request.title, now, now))
    conn.commit()
    conn.close()
    return {"id": thread_id, "title": request.title}

@app.delete("/threads")
async def delete_thread(request: Dict[str, str] = Body(...)):
    thread_id = request.get("id")
    if not thread_id:
        raise HTTPException(status_code=400, detail="Missing thread id")
    conn = get_db()
    conn.execute("DELETE FROM threads WHERE id = ?", (thread_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": thread_id}

@app.patch("/threads")
async def rename_thread(request: Dict[str, str] = Body(...)):
    """
    Rename a thread
    """
    thread_id = request.get("id")
    title = request.get("title", "Untitled")
    if not thread_id:
        raise HTTPException(status_code=400, detail="Missing thread id")
    
    now = datetime.now().isoformat()
    conn = get_db()
    conn.execute("UPDATE threads SET title = ?, updated_at = ? WHERE id = ?",
                 (title, now, thread_id))
    conn.commit()
    conn.close()
    return {"status": "updated", "id": thread_id, "title": title}


@app.get("/history/{thread_id}")
async def get_history(thread_id: str):
    """
    Get chat history from LangGraph checkpoint
    """
    try:
        async with AsyncSqliteSaver.from_conn_string("data/checkpoints.sqlite") as checkpointer:
            marketing_graph = create_marketing_graph(checkpointer=checkpointer, store=store, with_hitl=True)

            config = {"configurable": {"thread_id": thread_id}}
            state = await marketing_graph.aget_state(config)

            # Handle empty state
            if not state or not state.values:
                return []

            messages = state.values.get("messages", [])

            print(f"[HISTORY] thread_id={thread_id}, found {len(messages)} messages")
            for i, msg in enumerate(messages):
                msg_type = getattr(msg, 'type', 'unknown')
                content_preview = str(msg.content)[:50] if hasattr(msg, 'content') else 'N/A'
                print(f"  [{i}] {msg_type}: {content_preview}...")

            # Format for frontend (MessageResponse format)
            formatted_messages = []
            for msg in messages:
                # Determine message type
                msg_type = msg.type if hasattr(msg, 'type') else 'unknown'

                # Map LangChain message types to frontend types
                if msg_type == "human":
                    # Get additional_kwargs for attachment metadata
                    additional_kwargs = getattr(msg, 'additional_kwargs', {})

                    # Use original_content if available, otherwise clean up attachment content
                    if additional_kwargs.get("original_content"):
                        content = additional_kwargs["original_content"]
                    else:
                        # Fallback: clean up attachment content from human messages
                        content = msg.content
                        if isinstance(content, str) and "\n\n--- Attachments ---" in content:
                            content = content.split("\n\n--- Attachments ---")[0]

                    # Get attachment metadata
                    attachments = additional_kwargs.get("attachments", [])

                    formatted_messages.append({
                        "type": "human",
                        "data": {
                            "id": msg.id if (hasattr(msg, 'id') and msg.id) else str(uuid.uuid4()),
                            "content": content,
                            "attachments": attachments
                        }
                    })
                elif msg_type == "ai":
                    formatted_messages.append({
                        "type": "ai",
                        "data": {
                            "id": msg.id if (hasattr(msg, 'id') and msg.id) else str(uuid.uuid4()),
                            "content": msg.content,
                            "tool_calls": getattr(msg, 'tool_calls', []),
                            "additional_kwargs": getattr(msg, 'additional_kwargs', {}),
                            "response_metadata": getattr(msg, 'response_metadata', {})
                        }
                    })
                elif msg_type == "tool":
                    formatted_messages.append({
                        "type": "tool",
                        "data": {
                            "id": msg.id if (hasattr(msg, 'id') and msg.id) else str(uuid.uuid4()),
                            "content": msg.content,
                            "tool_call_id": getattr(msg, 'tool_call_id', ''),
                            "name": getattr(msg, 'name', ''),
                            "status": "success"
                        }
                    })

            # 检查是否有待处理的中断（审批卡片持久化）
            if state.next:
                print(f"[HISTORY] Pending interrupt detected: {state.next}")
                # 获取 interrupt() 传递的上下文
                interrupt_context = {}
                if hasattr(state, 'tasks') and state.tasks:
                    for task in state.tasks:
                        if hasattr(task, 'interrupts') and task.interrupts:
                            interrupt_context = task.interrupts[0].value if task.interrupts else {}
                            break

                # 添加一个 human_review tool_call 消息，触发前端显示审批卡片
                formatted_messages.append({
                    "type": "ai",
                    "data": {
                        "id": f"pending_approval_{thread_id}",
                        "content": "",
                        "tool_calls": [
                            {
                                "name": "human_review",
                                "id": f"call_pending_{thread_id}",
                                "args": interrupt_context
                            }
                        ]
                    }
                })

            return formatted_messages
    except Exception as e:
        print(f"History Error: {e}")
        import traceback
        traceback.print_exc()
        # Return empty array instead of error for new threads
        return []

# =============================================================================
# File Upload (RAG) & Knowledge Base Management
# =============================================================================

rag_pipeline = MultimodalRAGPipeline()
KNOWLEDGE_DB_PATH = "data/knowledge.db"
UPLOADS_DIR = "data/uploads"

# 知识类型定义（智立享营销知识库）
KNOWLEDGE_TYPES = {
    "product_raw": "产品原始资料",      # 产品参数、功能、原理
    "sales_raw": "销售经验/话术",       # 销售技巧、异议处理
    "material": "文案/素材",            # 营销素材、宣传文案
    "conclusion": "结论型知识",         # 总结性知识、FAQ
}

# Ensure uploads directory exists
os.makedirs(UPLOADS_DIR, exist_ok=True)

# =============================================================================
# Background Task Management (SQLite)
# =============================================================================

TASKS_DB_PATH = "data/tasks.db"

def get_tasks_db():
    conn = sqlite3.connect(TASKS_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_tasks_db():
    """Initialize task status table"""
    conn = get_tasks_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS upload_tasks (
            id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'pending',
            total_files INTEGER DEFAULT 0,
            completed_files INTEGER DEFAULT 0,
            current_file TEXT,
            results TEXT,
            error TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    # 清理已完成/失败的历史任务（保留最近 24 小时内的）
    conn.execute("""
        DELETE FROM upload_tasks
        WHERE status IN ('completed', 'failed')
        AND datetime(updated_at) < datetime('now', '-1 day')
    """)
    conn.commit()
    conn.close()

init_tasks_db()

async def process_upload_task(
    task_id: str,
    file_infos: list,
    knowledge_type: str,
    folder: str
):
    """
    后台处理上传任务

    Args:
        task_id: 任务 ID
        file_infos: 文件信息列表 [{"path": ..., "filename": ..., "file_id": ...}, ...]
        knowledge_type: 知识类型
        folder: 文件夹路径
    """
    conn = get_tasks_db()
    results = []

    try:
        for i, file_info in enumerate(file_infos):
            save_path = file_info["path"]
            filename = file_info["filename"]
            file_id = file_info["file_id"]
            file_size = file_info["file_size"]

            # 更新当前处理状态
            now = datetime.now().isoformat()
            conn.execute(
                "UPDATE upload_tasks SET status = 'processing', current_file = ?, completed_files = ?, updated_at = ? WHERE id = ?",
                (filename, i, now, task_id)
            )
            conn.commit()

            try:
                # 调用异步 ingest（Docling 解析 + 向量化）
                await rag_pipeline.async_ingest(save_path, metadata={
                    "original_filename": filename,
                    "type": "knowledge_base",
                    "knowledge_type": knowledge_type,
                    "doc_id": file_id
                })

                # 记录到知识库数据库
                knowledge_conn = get_knowledge_db()
                knowledge_conn.execute(
                    "INSERT INTO documents (id, filename, filepath, upload_time, file_size, status, knowledge_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (file_id, filename, save_path, now, file_size, "indexed", knowledge_type)
                )
                knowledge_conn.commit()
                knowledge_conn.close()

                results.append({
                    "status": "success",
                    "filename": filename,
                    "id": file_id,
                    "knowledge_type": knowledge_type
                })

            except Exception as e:
                print(f"[TASK {task_id}] Failed to process {filename}: {e}")
                results.append({
                    "status": "error",
                    "filename": filename,
                    "error": str(e)
                })
                # 清理失败的文件
                if os.path.exists(save_path):
                    try:
                        os.remove(save_path)
                    except:
                        pass

        # 任务完成
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE upload_tasks SET status = 'completed', completed_files = ?, current_file = NULL, results = ?, updated_at = ? WHERE id = ?",
            (len(file_infos), json.dumps(results, ensure_ascii=False), now, task_id)
        )
        conn.commit()
        print(f"[TASK {task_id}] Completed: {len(results)} files processed")

    except Exception as e:
        # 任务失败
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE upload_tasks SET status = 'failed', error = ?, results = ?, updated_at = ? WHERE id = ?",
            (str(e), json.dumps(results, ensure_ascii=False), now, task_id)
        )
        conn.commit()
        print(f"[TASK {task_id}] Failed: {e}")
    finally:
        conn.close()

def get_knowledge_db():
    conn = sqlite3.connect(KNOWLEDGE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/knowledge/tasks/active")
async def get_active_tasks():
    """
    获取当前活跃的上传任务（pending 或 processing 状态）

    用于前端重新打开对话框时恢复任务进度显示
    """
    conn = get_tasks_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, status, total_files, completed_files, current_file, results, error, created_at, updated_at FROM upload_tasks WHERE status IN ('pending', 'processing') ORDER BY created_at DESC LIMIT 1"
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    result = dict(row)
    if result.get("results"):
        try:
            result["results"] = json.loads(result["results"])
        except:
            pass

    return result

@app.get("/knowledge/task/{task_id}")
async def get_task_status(task_id: str):
    """
    查询上传任务状态

    Returns:
        - status: pending | processing | completed | failed
        - total_files: 总文件数
        - completed_files: 已完成文件数
        - current_file: 当前正在处理的文件名
        - results: 完成后的结果列表
        - error: 错误信息（如果失败）
    """
    conn = get_tasks_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, status, total_files, completed_files, current_file, results, error, created_at, updated_at FROM upload_tasks WHERE id = ?",
        (task_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Task not found")

    result = dict(row)
    # 解析 results JSON
    if result.get("results"):
        try:
            result["results"] = json.loads(result["results"])
        except:
            pass

    return result

@app.get("/knowledge/types")
async def get_knowledge_types():
    """
    获取知识类型列表
    """
    return [
        {"key": key, "label": label}
        for key, label in KNOWLEDGE_TYPES.items()
    ]

@app.get("/knowledge/folders")
async def get_knowledge_folders():
    """
    获取知识库中已存在的文件夹列表
    """
    folders = set()
    try:
        conn = get_knowledge_db()
        cursor = conn.cursor()
        cursor.execute("SELECT filepath FROM documents")

        for row in cursor.fetchall():
            filepath = row["filepath"] if row["filepath"] else ""
            if filepath and UPLOADS_DIR in filepath:
                rel_path = filepath.replace(UPLOADS_DIR, "").lstrip("/\\")
                folder = os.path.dirname(rel_path)
                if folder:
                    # 添加完整路径和所有父路径
                    parts = folder.replace("\\", "/").split("/")
                    for i in range(len(parts)):
                        folders.add("/".join(parts[:i+1]))

        conn.close()
    except Exception as e:
        print(f"Get folders error: {e}")

    return sorted(list(folders))

@app.delete("/knowledge/folders/{folder_path:path}")
async def delete_knowledge_folder(folder_path: str):
    """
    删除指定文件夹及其所有文件
    folder_path: 文件夹路径，如 "客户反馈" 或 "客户反馈/2026年"
    """
    if not folder_path:
        raise HTTPException(status_code=400, detail="文件夹路径不能为空")

    # 标准化路径分隔符
    folder_path = folder_path.replace("\\", "/")

    try:
        conn = get_knowledge_db()
        cursor = conn.cursor()

        # 查询该文件夹下的所有文件（包括子文件夹）
        cursor.execute("SELECT id, filepath, filename FROM documents")

        docs_to_delete = []
        for row in cursor.fetchall():
            filepath = row["filepath"] if row["filepath"] else ""
            if filepath and UPLOADS_DIR in filepath:
                rel_path = filepath.replace(UPLOADS_DIR, "").lstrip("/\\")
                doc_folder = os.path.dirname(rel_path).replace("\\", "/")
                # 匹配该文件夹或其子文件夹
                if doc_folder == folder_path or doc_folder.startswith(folder_path + "/"):
                    docs_to_delete.append({
                        "id": row["id"],
                        "filepath": filepath,
                        "filename": row["filename"]
                    })

        if not docs_to_delete:
            conn.close()
            raise HTTPException(status_code=404, detail=f"文件夹 '{folder_path}' 不存在或为空")

        deleted_count = 0
        for doc in docs_to_delete:
            try:
                # 1. 从向量库删除
                try:
                    rag_pipeline.delete_document(doc["filepath"])
                except Exception as e:
                    print(f"Vector delete error for {doc['id']}: {e}")

                # 2. 从磁盘删除
                if os.path.exists(doc["filepath"]):
                    try:
                        os.remove(doc["filepath"])
                    except OSError:
                        pass

                # 3. 从数据库删除
                cursor.execute("DELETE FROM documents WHERE id = ?", (doc["id"],))
                deleted_count += 1
            except Exception as e:
                print(f"Error deleting {doc['id']}: {e}")

        conn.commit()
        conn.close()

        # 尝试删除空的文件夹目录
        folder_full_path = os.path.join(UPLOADS_DIR, folder_path)
        if os.path.exists(folder_full_path) and os.path.isdir(folder_full_path):
            try:
                # 递归删除空目录
                for root, dirs, files in os.walk(folder_full_path, topdown=False):
                    for d in dirs:
                        try:
                            os.rmdir(os.path.join(root, d))
                        except OSError:
                            pass
                os.rmdir(folder_full_path)
            except OSError:
                pass  # 目录非空或其他原因无法删除

        return {
            "status": "success",
            "folder": folder_path,
            "deleted_count": deleted_count,
            "message": f"已删除文件夹 '{folder_path}' 及其 {deleted_count} 个文件"
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete folder error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/knowledge/list")
async def list_knowledge(knowledge_type: str = None):
    """
    List all documents in the knowledge base

    Args:
        knowledge_type: 可选，按知识类型过滤
    """
    try:
        conn = get_knowledge_db()
        cursor = conn.cursor()

        if knowledge_type:
            cursor.execute(
                "SELECT id, filename, filepath, upload_time, file_size, status, knowledge_type FROM documents WHERE knowledge_type = ? ORDER BY upload_time DESC",
                (knowledge_type,)
            )
        else:
            cursor.execute(
                "SELECT id, filename, filepath, upload_time, file_size, status, knowledge_type FROM documents ORDER BY upload_time DESC"
            )

        docs = []
        for row in cursor.fetchall():
            doc = dict(row)
            # 添加知识类型标签
            kt = doc.get("knowledge_type", "product_raw")
            doc["knowledge_type_label"] = KNOWLEDGE_TYPES.get(kt, kt)

            # 从 filepath 解析出文件夹路径
            filepath = doc.get("filepath", "")
            if filepath and UPLOADS_DIR in filepath:
                # 提取相对于 uploads 目录的路径
                rel_path = filepath.replace(UPLOADS_DIR, "").lstrip("/\\")
                # 获取文件夹部分（不包含文件名）
                folder = os.path.dirname(rel_path)
                doc["folder"] = folder if folder else ""
            else:
                doc["folder"] = ""

            docs.append(doc)

        conn.close()
        return docs
    except Exception as e:
        print(f"List Knowledge Error: {e}")
        return []

@app.delete("/knowledge/{doc_id}")
async def delete_knowledge(doc_id: str):
    """
    Delete a document from Knowledge Base (File + Metadata + Vector Store)
    """
    try:
        conn = get_knowledge_db()
        cursor = conn.cursor()
        
        # Get file info
        cursor.execute("SELECT filepath, filename FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Document not found")
            
        filepath = row["filepath"]
        filename = row["filename"]
        
        # 1. Delete from Vector Store
        rag_pipeline.delete_document(filepath)
        
        # 2. Delete from Disk
        if os.path.exists(filepath):
            os.remove(filepath)
            
        # 3. Delete from DB
        cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()
        conn.close()
        
        return {"status": "success", "id": doc_id, "message": f"Deleted {filename}"}

    except Exception as e:
        print(f"Delete Knowledge Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/knowledge/batch/delete")
async def batch_delete_knowledge(request: Dict[str, List[str]] = Body(...)):
    """
    Batch delete documents
    """
    ids = request.get("ids", [])
    if not ids:
        return {"status": "no_action", "count": 0}

    conn = get_knowledge_db()
    cursor = conn.cursor()
    
    deleted_count = 0
    for doc_id in ids:
        try:
            # Get file info
            cursor.execute("SELECT filepath FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()
            
            if row:
                filepath = row["filepath"]
                
                # 1. Delete from Vector Store
                try:
                    rag_pipeline.delete_document(filepath)
                except Exception as e:
                    print(f"Vector delete error for {doc_id}: {e}")

                # 2. Delete from Disk
                if os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass
            
            # 3. Delete from DB
            cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            deleted_count += 1
        except Exception as e:
            print(f"Error deleting {doc_id}: {e}")
        
    conn.commit()
    conn.close()
    return {"status": "deleted", "count": deleted_count}

@app.post("/knowledge/batch/update")
async def batch_update_knowledge(request: Dict[str, Any] = Body(...)):
    """
    Batch update knowledge type (fast metadata-only update, no re-embedding)
    """
    ids = request.get("ids", [])
    knowledge_type = request.get("knowledge_type")

    if not ids or not knowledge_type:
         raise HTTPException(status_code=400, detail="Missing ids or knowledge_type")

    if knowledge_type not in KNOWLEDGE_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid knowledge type: {knowledge_type}")

    conn = get_knowledge_db()
    cursor = conn.cursor()

    updated_count = 0
    for doc_id in ids:
        try:
            # Get file info
            cursor.execute("SELECT filepath FROM documents WHERE id = ?", (doc_id,))
            row = cursor.fetchone()

            if row:
                filepath = row["filepath"]

                # Update Vector Store Metadata directly (fast, no re-embedding)
                try:
                    rag_pipeline.update_metadata(filepath, {
                        "knowledge_type": knowledge_type
                    })
                except Exception as e:
                    print(f"Vector metadata update error for {doc_id}: {e}")

            # Update DB
            cursor.execute("UPDATE documents SET knowledge_type = ? WHERE id = ?", (knowledge_type, doc_id))
            updated_count += 1
        except Exception as e:
            print(f"Error updating {doc_id}: {e}")

    conn.commit()
    conn.close()
    return {"status": "updated", "count": updated_count}

class UpdateKnowledgeTypeRequest(BaseModel):
    knowledge_type: str

@app.patch("/knowledge/{doc_id}")
async def update_knowledge_type(doc_id: str, request: UpdateKnowledgeTypeRequest):
    """
    修改知识文档的类型标签

    仅更新数据库中的 knowledge_type 字段，向量库中的 metadata 在下次检索时会自动匹配。
    注意：ChromaDB 的 metadata 更新需要重新 ingest，但为了简化操作，
    这里仅更新数据库记录。如果需要严格一致，可以调用 delete + re-ingest。
    """
    knowledge_type = request.knowledge_type

    # 验证知识类型
    if knowledge_type not in KNOWLEDGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的知识类型: {knowledge_type}，可选值: {list(KNOWLEDGE_TYPES.keys())}"
        )

    try:
        conn = get_knowledge_db()
        cursor = conn.cursor()

        # 检查文档是否存在
        cursor.execute("SELECT id, filepath FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="文档不存在")

        filepath = row["filepath"]

        # 更新数据库中的知识类型
        cursor.execute(
            "UPDATE documents SET knowledge_type = ? WHERE id = ?",
            (knowledge_type, doc_id)
        )
        conn.commit()

        # 同步更新向量库中的 metadata (fast, no re-embedding)
        try:
            rag_pipeline.update_metadata(filepath, {
                "knowledge_type": knowledge_type
            })
        except Exception as ve:
            print(f"Vector store update warning: {ve}")
            # 向量库更新失败不影响主流程，数据库已更新

        conn.close()

        return {
            "status": "success",
            "id": doc_id,
            "knowledge_type": knowledge_type,
            "knowledge_type_label": KNOWLEDGE_TYPES[knowledge_type]
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Update Knowledge Type Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload/knowledge")
async def upload_knowledge(
    files: List[UploadFile] = File(...),
    knowledge_type: str = Form(default="product_raw"),
    folder: str = Form(default=""),
    async_mode: bool = Form(default=True)
):
    """
    Upload and ingest multiple files into PERMANENT Knowledge Base (ChromaDB)
    Saves original files to data/uploads/ and records metadata in SQLite.

    后台任务模式（async_mode=True，默认）：
    - 快速保存文件到磁盘
    - 立即返回 task_id
    - Docling 解析和向量化在后台异步执行
    - 前端通过 /knowledge/task/{task_id} 轮询进度

    同步模式（async_mode=False）：
    - 等待所有文件处理完成后返回
    - 适用于单文件或小文件快速上传

    Args:
        files: 上传的文件列表
        knowledge_type: 知识类型
        folder: 可选的文件夹路径（如 "产品资料" 或 "产品资料/子目录"）
        async_mode: 是否使用后台任务模式（默认 True）
    """
    import shutil

    # 验证知识类型
    if knowledge_type not in KNOWLEDGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的知识类型: {knowledge_type}，可选值: {list(KNOWLEDGE_TYPES.keys())}"
        )

    # 清理文件夹路径（防止路径遍历攻击）
    if folder:
        # 移除危险字符，只保留中文、字母、数字、下划线、斜杠、横杠
        folder = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9_/\-]', '_', folder)
        folder = folder.strip('/').replace('..', '')  # 防止路径遍历

    # ========== 阶段1：快速保存文件到磁盘 ==========
    file_infos = []
    for file in files:
        try:
            file_id = str(uuid.uuid4())
            safe_filename = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9._-]', '_', file.filename)
            save_filename = f"{file_id}_{safe_filename}"

            # 确定保存目录（支持文件夹）
            if folder:
                save_dir = os.path.join(UPLOADS_DIR, folder)
                os.makedirs(save_dir, exist_ok=True)
            else:
                save_dir = UPLOADS_DIR

            save_path = os.path.join(save_dir, save_filename)

            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_size = os.path.getsize(save_path)

            file_infos.append({
                "path": save_path,
                "filename": file.filename,
                "file_id": file_id,
                "file_size": file_size
            })
        except Exception as e:
            print(f"Failed to save {file.filename}: {e}")
            # 清理已保存的文件
            for info in file_infos:
                if os.path.exists(info["path"]):
                    try:
                        os.remove(info["path"])
                    except:
                        pass
            raise HTTPException(status_code=500, detail=f"文件保存失败: {str(e)}")

    if not file_infos:
        raise HTTPException(status_code=400, detail="没有有效的文件")

    # ========== 阶段2：后台任务模式 vs 同步模式 ==========
    if async_mode:
        # 后台任务模式：创建任务记录，启动后台处理
        task_id = str(uuid.uuid4())
        now = datetime.now().isoformat()

        conn = get_tasks_db()
        # 创建新任务前，清理已完成/失败的历史任务（保留最近 24 小时内的）
        conn.execute("""
            DELETE FROM upload_tasks
            WHERE status IN ('completed', 'failed')
            AND datetime(updated_at) < datetime('now', '-1 day')
        """)
        conn.execute(
            "INSERT INTO upload_tasks (id, status, total_files, completed_files, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (task_id, "pending", len(file_infos), 0, now, now)
        )
        conn.commit()
        conn.close()

        # 启动后台任务（不阻塞响应）
        asyncio.create_task(process_upload_task(task_id, file_infos, knowledge_type, folder))

        print(f"[UPLOAD] Task {task_id} created: {len(file_infos)} files queued for processing")

        return {
            "mode": "async",
            "task_id": task_id,
            "total_files": len(file_infos),
            "message": f"已接收 {len(file_infos)} 个文件，正在后台处理。请通过 /knowledge/task/{task_id} 查询进度。"
        }

    else:
        # 同步模式：等待所有文件处理完成
        results = []
        conn = get_knowledge_db()

        try:
            for file_info in file_infos:
                save_path = file_info["path"]
                filename = file_info["filename"]
                file_id = file_info["file_id"]
                file_size = file_info["file_size"]

                try:
                    # Ingest into RAG (Vector Store)
                    await rag_pipeline.async_ingest(save_path, metadata={
                        "original_filename": filename,
                        "type": "knowledge_base",
                        "knowledge_type": knowledge_type,
                        "doc_id": file_id
                    })

                    # Record Metadata in DB
                    now = datetime.now().isoformat()
                    conn.execute(
                        "INSERT INTO documents (id, filename, filepath, upload_time, file_size, status, knowledge_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (file_id, filename, save_path, now, file_size, "indexed", knowledge_type)
                    )

                    results.append({
                        "status": "success",
                        "filename": filename,
                        "id": file_id,
                        "knowledge_type": knowledge_type
                    })
                except Exception as e:
                    print(f"Failed to process {filename}: {e}")
                    results.append({
                        "status": "error",
                        "filename": filename,
                        "error": str(e)
                    })
                    # Cleanup if failed
                    if os.path.exists(save_path):
                        try:
                            os.remove(save_path)
                        except:
                            pass

            conn.commit()
            return {"mode": "sync", "results": results}
        except Exception as e:
            conn.rollback()
            print(f"Batch Upload Error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            conn.close()

@app.post("/upload/attachment")
async def upload_attachment(file: UploadFile = File(...)):
    """
    Upload a temporary attachment. 
    Returns the extracted text content directly for inclusion in the conversation context.
    Does NOT ingest into the permanent vector DB.
    """
    import tempfile
    import shutil
    
    ext = os.path.splitext(file.filename)[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    try:
        # Reuse RAGPipeline's loader logic but DO NOT ingest
        docs = rag_pipeline.load_document(tmp_path)
        full_text = "\n\n".join([d.page_content for d in docs])
        
        # Return text content directly
        return {
            "status": "success", 
            "filename": file.filename, 
            "type": "attachment",
            "content": full_text,
            "summary": f"Content of {file.filename} ({len(full_text)} chars)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Legacy endpoint. Defaults to /upload/attachment for safety.
    """
    return await upload_attachment(file)

# =============================================================================
# Startup / Health
# =============================================================================

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("src.server:app", host="0.0.0.0", port=8001, reload=False)
