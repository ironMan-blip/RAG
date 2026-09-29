import asyncio
from httpx import AsyncClient
from backend.main import app

async def test():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        response = await ac.post("/api/chat", json={"message": "hello", "attached_filename": "test.txt"})
        print(response.status_code)
        print(response.json())

asyncio.run(test())
