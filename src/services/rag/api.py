from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from .chroma_service import ChromaKnowledgeProvider

app = FastAPI(title="Nexus RAG Service", version="1.0.0")

# Initialize Provider (Singleton for the service)
provider = ChromaKnowledgeProvider()

class QueryRequest(BaseModel):
    query: str
    k: int = 3

class IngestRequest(BaseModel):
    file_path: str

class QueryResponse(BaseModel):
    result: str

class IngestResponse(BaseModel):
    doc_id: str
    message: str

@app.get("/")
def health_check():
    return {"status": "active", "service": "Nexus RAG"}

@app.post("/query", response_model=QueryResponse)
def query_knowledge(request: QueryRequest):
    try:
        result = provider.query(request.query, k=request.k)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ingest", response_model=IngestResponse)
def ingest_document(request: IngestRequest):
    try:
        doc_id = provider.ingest_document(request.file_path)
        return {"doc_id": doc_id, "message": "Ingestion successful"}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {request.file_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status")
def get_status():
    try:
        docs = provider.get_documents()
        return {
            "document_count": len(docs),
            "documents": docs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def start_server(host: str = "0.0.0.0", port: int = 8000):
    uvicorn.run(app, host=host, port=port)

if __name__ == "__main__":
    start_server()
