from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

app = FastAPI(title="CrimeLensAI - Ingestion Service", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "ingestion", "version": "0.1.0"}
