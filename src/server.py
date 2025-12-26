import os
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
import asyncio

from src.core.factory import GraphFactory
from src.core.lifecycle import LifecycleManager

# Initialize App
app = FastAPI(
    title="AI Teacher Nexus API",
    description="Backend API for AI Teacher Nexus Workbench",
    version="1.0.0"
)

# CORS Configuration
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request Models
class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Message]
    session_id: Optional[str] = "default"
    teacher_id: Optional[str] = None
    rag_config: Optional[Dict[str, Any]] = None

# Lifecycle Manager
lifecycle = LifecycleManager()

@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """
    Streaming Chat Endpoint using Vercel AI SDK Data Stream Protocol.
    Format: 0:"text"\n for text chunks
    """
    async def stream_generator():
        try:
            # Extract last user message
            user_message = request.messages[-1].content if request.messages else ""
            
            # Routing Logic
            if request.teacher_id == "researcher":
                from gpt_researcher import GPTResearcher
                print(f"--- Starting Researcher for: {user_message} ---")
                
                # Send immediate feedback
                yield f'0:{json.dumps("🔍 正在进行深度研究...")}\n'
                await asyncio.sleep(0.1)
                
                try:
                    researcher = GPTResearcher(query=user_message, report_type="research_report")
                    
                    yield f'0:{json.dumps("📡 正在搜索相关信息...")}\n'
                    await asyncio.sleep(0.1)
                    
                    print("Researcher: Conducting research...")
                    await researcher.conduct_research()
                    print("Researcher: Research finished.")
                    
                    yield f'0:{json.dumps("📝 正在生成报告...")}\n'
                    await asyncio.sleep(0.1)
                    
                    print("Researcher: Writing report...")
                    report = await researcher.write_report()
                    print(f"Researcher: Report generated (length: {len(report)})")
                    
                    # Stream the report in chunks
                    yield f'0:{json.dumps("\n\n--- 研究报告 ---\n\n")}\n'
                    chunk_size = 100
                    for i in range(0, len(report), chunk_size):
                        chunk = report[i:i+chunk_size]
                        yield f'0:{json.dumps(chunk)}\n'
                        await asyncio.sleep(0.01)
                        
                except Exception as e:
                    print(f"Researcher Error: {e}")
                    import traceback
                    traceback.print_exc()
                    yield f'0:{json.dumps(f"❌ 研究出错: {str(e)}")}\n'
            else:
                # Fallback for other teachers (Mock)
                print(f"--- Mock Response for: {request.teacher_id} ---")
                response_text = f"Received: {user_message}. Teacher: {request.teacher_id}. (Not implemented yet)"
                chunk_size = 10
                for i in range(0, len(response_text), chunk_size):
                    chunk = response_text[i:i+chunk_size]
                    yield f'0:{json.dumps(chunk)}\n'
                    await asyncio.sleep(0.02)

                    
        except Exception as e:
            print(f"Error: {e}")
            yield f'0:"{json.dumps(f"Error: {str(e)}")[1:-1]}"\n'

    return StreamingResponse(
        stream_generator(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Vercel-AI-Data-Stream": "v1",
        }
    )



if __name__ == "__main__":
    uvicorn.run("src.server:app", host="0.0.0.0", port=8001, reload=True)
