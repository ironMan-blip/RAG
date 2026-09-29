from fastapi import APIRouter, UploadFile, File, HTTPException
from pydantic import BaseModel
import psycopg2
from core.config import settings
import json

# Add these models
class FileGroupCreate(BaseModel):
    name: str

class FileGroupAddDocument(BaseModel):
    document_id: int

# We'll just append this to the routes file.
