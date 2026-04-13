from fastapi import APIRouter
from database import get_pool

router = APIRouter()


@router.get("/")
async def root():
    return {"message": "Finanzas 4.0 API", "version": "1.0.0"}


@router.get("/health")
async def health():
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}
