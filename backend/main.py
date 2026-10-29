import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routers.chat import router as chat_router
from api.routers.chats import router as chats_router
from api.routers.documents import router as documents_router
from services import document_service, upload_jobs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        document_service.resume_uploads()
    except Exception:
        logger.exception("Could not resume unfinished uploads")
    yield
    upload_jobs.stopping = True


app = FastAPI(title="RAG AI Chat Backend", lifespan=lifespan)


# Registered before CORS so CORS wraps it and 500s still carry CORS headers
@app.middleware("http")
async def unhandled_errors(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(chats_router, prefix="/api", tags=["chats"])
app.include_router(documents_router, prefix="/api", tags=["documents"])
