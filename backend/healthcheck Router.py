from fastapi import APIRouter
from datetime import datetime
import socket

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "✅ OK",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "host": socket.gethostname()
    }
