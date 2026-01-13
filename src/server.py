import os
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
    if attachments:
        attachment_text = "\n\n--- Attachments ---\n"
        for att in attachments:
            # att structure from frontend: { "name": "...", "content": "...", ... }
            # Also support legacy "filename" field for backwards compatibility
            if att.get("content"):
                file_name = att.get("name") or att.get("filename") or "Unknown"
                attachment_text += f"\n[File: {file_name}]\n{att.get('content')}\n"

        question += attachment_text

    # Update thread title if it's a new thread or generic title
    update_thread_title(thread_id, question)

    async def generate():
        # Clean implementation using from_conn_string
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
            # Compile Graph
            marketing_graph = create_marketing_graph(checkpointer=checkpointer, store=store, with_hitl=True)

            config = {"configurable": {"thread_id": thread_id}}

            # 初始输入 - 使用 HumanMessage 对象而不是元组
            from langchain_core.messages import HumanMessage
            inputs = {
                "question": question,
                "messages": [HumanMessage(content=question)],
                "force_web_search": enable_web_search  # 传递前端开关状态
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
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
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
    async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
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
    """
    print(f"[APPROVE] thread_id={request.thread_id}, approved={request.approved}")

    async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
        # CRITICAL: 始终使用 with_hitl=True 保持 graph 结构一致
        # 用户拒绝时，通过状态更新而非重新编译 graph 来控制流程
        marketing_graph = create_marketing_graph(checkpointer=checkpointer, store=store, with_hitl=True)

        config = {"configurable": {"thread_id": request.thread_id}}

        # Check current state first
        current_state = await marketing_graph.aget_state(config)
        print(f"[APPROVE] Current state next: {current_state.next if current_state else 'None'}")

        if request.feedback:
            resume_value = request.feedback
        else:
            resume_value = "approved" if request.approved else "rejected"
        print(f"[APPROVE] Resuming with value: {resume_value}")

        try:
            # Use Command(resume=...) to resume from interrupt()
            result = await marketing_graph.ainvoke(Command(resume=resume_value), config)
            print(f"[APPROVE] Result keys: {result.keys() if result else 'None'}")

            if request.approved:
                return {"status": "approved", "generation": result.get("generation")}
            else:
                # Deny: 返回最终生成的内容（如果有）
                generation = result.get("generation", "重新检索后未找到相关内容。")
                return {"status": "rejected", "message": "User rejected. Query refined.", "generation": generation}
        except Exception as e:
            print(f"[APPROVE] Error: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Thread Management (SQLite)
# =============================================================================

def get_db():
    conn = sqlite3.connect("threads.db")
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
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
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
                    formatted_messages.append({
                        "type": "human",
                        "data": {
                            "id": msg.id if (hasattr(msg, 'id') and msg.id) else str(uuid.uuid4()),
                            "content": msg.content
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

def get_knowledge_db():
    conn = sqlite3.connect(KNOWLEDGE_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/knowledge/types")
async def get_knowledge_types():
    """
    获取知识类型列表
    """
    return [
        {"key": key, "label": label}
        for key, label in KNOWLEDGE_TYPES.items()
    ]

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
                "SELECT id, filename, upload_time, file_size, status, knowledge_type FROM documents WHERE knowledge_type = ? ORDER BY upload_time DESC",
                (knowledge_type,)
            )
        else:
            cursor.execute(
                "SELECT id, filename, upload_time, file_size, status, knowledge_type FROM documents ORDER BY upload_time DESC"
            )

        docs = []
        for row in cursor.fetchall():
            doc = dict(row)
            # 添加知识类型标签
            kt = doc.get("knowledge_type", "product_raw")
            doc["knowledge_type_label"] = KNOWLEDGE_TYPES.get(kt, kt)
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

        # 同步更新向量库中的 metadata
        # 策略：删除旧向量 → 重新 ingest（确保 metadata 一致性）
        try:
            rag_pipeline.delete_document(filepath)
            rag_pipeline.ingest(filepath, metadata={
                "type": "knowledge_base",
                "knowledge_type": knowledge_type,
                "doc_id": doc_id
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
    file: UploadFile = File(...),
    knowledge_type: str = Form(default="product_raw")
):
    """
    Upload and ingest a file into PERMANENT Knowledge Base (ChromaDB)
    Saves original file to data/uploads/ and records metadata in SQLite.

    Args:
        file: 上传的文件
        knowledge_type: 知识类型，可选值：
            - product_raw: 产品原始资料
            - sales_raw: 销售经验/话术
            - material: 文案/素材
            - conclusion: 结论型知识
    """
    import shutil

    # 验证知识类型
    if knowledge_type not in KNOWLEDGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"无效的知识类型: {knowledge_type}，可选值: {list(KNOWLEDGE_TYPES.keys())}"
        )

    try:
        # 1. Save file to disk (Permanent)
        # Use UUID + Sanitized Filename to avoid encoding issues while keeping readability
        file_id = str(uuid.uuid4())

        # Sanitize filename: allow Chinese, letters, numbers, dots, underscores, hyphens
        # Replace everything else with underscore
        safe_filename = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9._-]', '_', file.filename)

        save_filename = f"{file_id}_{safe_filename}"
        save_path = os.path.join(UPLOADS_DIR, save_filename)

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_size = os.path.getsize(save_path)

        # 2. Ingest into RAG (Vector Store) with knowledge_type metadata
        # We pass original_filename in metadata so the AI knows the real name
        rag_pipeline.ingest(save_path, metadata={
            "original_filename": file.filename,
            "type": "knowledge_base",
            "knowledge_type": knowledge_type,  # 知识类型标签
            "doc_id": file_id
        })

        # 3. Record Metadata in DB (including knowledge_type)
        conn = get_knowledge_db()
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO documents (id, filename, filepath, upload_time, file_size, status, knowledge_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (file_id, file.filename, save_path, now, file_size, "indexed", knowledge_type)
        )
        conn.commit()
        conn.close()

        return {
            "status": "success",
            "filename": file.filename,
            "id": file_id,
            "type": "knowledge_base",
            "knowledge_type": knowledge_type,
            "knowledge_type_label": KNOWLEDGE_TYPES[knowledge_type]
        }
    except Exception as e:
        # Cleanup if failed
        if 'save_path' in locals() and os.path.exists(save_path):
            os.remove(save_path)
        print(f"Upload Knowledge Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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
