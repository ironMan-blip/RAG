from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers.chat import router as chat_router
from api.routers.documents import router as documents_router


app = FastAPI(title="RAG AI Chat Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(documents_router, prefix="/api", tags=["documents"])

