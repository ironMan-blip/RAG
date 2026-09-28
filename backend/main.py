from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router as chat_router

app = FastAPI(title="RAG AI Chat Backend")

# Enable CORS to allow the frontend to communicate with this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins, adjust for production if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(chat_router, prefix="/api")

# Entry point instructions:
# Run with: uvicorn main:app --reload --port 8000
