import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request, Body, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import asyncio
import sqlite3
import uuid
from datetime import datetime
import aiosqlite

from src.core.factory import GraphFactory
from src.core.lifecycle import LifecycleManager
from src.agents.marketing import create_marketing_graph
from src.services.rag.pipeline import RAGPipeline
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from langgraph.store.memory import InMemoryStore

# Global Store (In-Memory for now, replace with persistent later)
store = InMemoryStore()

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
    
    # Update thread title if it's a new thread or generic title
    update_thread_title(thread_id, question)
    
    async def generate():
        # Clean implementation using from_conn_string
        async with AsyncSqliteSaver.from_conn_string("checkpoints.sqlite") as checkpointer:
            # Compile Graph
            marketing_graph = create_marketing_graph(checkpointer=checkpointer, store=store, with_hitl=True)
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # 初始输入
            inputs = {"question": question, "messages": [("user", question)]}
            
            try:
                async for event in marketing_graph.astream_events(inputs, config, version="v2"):
                    kind = event["event"]
                    
                    # 1. LLM 流式输出
                    if kind == "on_chat_model_stream":
                        content = event["data"]["chunk"].content
                        if content:
                            yield f"data: {json.dumps({'content': content, 'type': 'token'})}\n\n"
                    
                    # 2. 节点状态更新 (可选)
                    elif kind == "on_chain_start" and event["name"] in ["retrieve", "grade_documents", "generate", "transform_query"]:
                        yield f"data: {json.dumps({'type': 'status', 'node': event['name']})}\n\n"

                # 检查是否中断 (HITL)
                state = await marketing_graph.aget_state(config)
                if state.next:
                    yield f"data: {json.dumps({'type': 'interrupt', 'next': state.next})}\n\n"
                else:
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    
            except Exception as e:
                print(f"Stream Error: {e}")
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
            inputs = {"messages": [("user", question)]}
            
            try:
                async for event in supervisor_graph.astream_events(inputs, config, version="v2"):
                    kind = event["event"]
                    
                    if kind == "on_chat_model_stream":
                        content = event["data"]["chunk"].content
                        if content:
                            yield f"data: {json.dumps({'content': content, 'type': 'token'})}\n\n"
                    
                    elif kind == "on_chain_start":
                        # Detect which agent is running
                        node_name = event["name"]
                        if node_name in ["MarketingTeacher", "GeneralAssistant", "supervisor"]:
                            yield f"data: {json.dumps({'type': 'status', 'node': node_name})}\n\n"

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
                return {"status": "rejected", "message": "User rejected. Query will be refined."}
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
            
            # Format for frontend
            formatted_messages = []
            for msg in messages:
                role = "user" if msg.type == "human" else "assistant"
                formatted_messages.append({
                    "id": str(uuid.uuid4()),
                    "role": role,
                    "content": msg.content,
                    "createdAt": datetime.now().isoformat()
                })
            return formatted_messages
    except Exception as e:
        print(f"History Error: {e}")
        import traceback
        traceback.print_exc()
        # Return empty array instead of error for new threads
        return []

# =============================================================================
# File Upload (RAG)
# =============================================================================

rag_pipeline = RAGPipeline()

@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload and ingest a file into RAG pipeline
    """
    import tempfile
    import shutil
    
    ext = os.path.splitext(file.filename)[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name
    
    try:
        rag_pipeline.ingest(tmp_path, metadata={"original_filename": file.filename})
        return {"status": "success", "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        os.unlink(tmp_path)

# =============================================================================
# Startup / Health
# =============================================================================

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("src.server:app", host="0.0.0.0", port=8002, reload=True)
