from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from core.countries import COUNTRY_OPTIONS
from services import user_service

router = APIRouter()


class NewUser(BaseModel):
    name: str
    country: str


@router.get("/users")
async def get_users():
    return {"users": await run_in_threadpool(user_service.list_users), "countries": COUNTRY_OPTIONS}


@router.post("/users", status_code=201)
async def create_user(user: NewUser):
    try:
        return {"user": await run_in_threadpool(user_service.create_user, user.name, user.country)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except user_service.UserExists as e:
        raise HTTPException(status_code=409, detail=str(e))
