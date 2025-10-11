import os
import logging
from fastapi import APIRouter
from supabase import create_client, Client

# Debug loggers
logger = logging.getLogger("supabase_handler")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

router = APIRouter()
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_ANON_KEY")
logger.debug(f"Loaded SUPABASE_URL: {supabase_url}")
logger.debug(f"Loaded SUPABASE_ANON_KEY: {'FOUND' if supabase_key else 'NOT FOUND'}")

supabase: Client = None

try:
    if supabase_url and supabase_key:
        supabase = create_client(supabase_url, supabase_key)
        logger.info("✅ Supabase client initialized successfully.")
    else:
        logger.warning("❌ Supabase environment variables missing.")
except Exception as e:
    logger.error(f"❌ Supabase client initialization failed: {e}")

@router.get("/api/supabase/ping")
async def ping_supabase():
    try:
        if not supabase:
            logger.error("Supabase client not initialized.")
            return {"status": "error", "detail": "Supabase client not initialized"}

        logger.info("Pinging Supabase...")
        result = supabase.table("your_table_name").select("*").limit(1).execute()
        logger.debug(f"Ping result: {result}")
        return {"status": "success", "result": result.data}
    except Exception as e:
        logger.error(f"❌ Error in ping_supabase: {e}")
        return {"status": "error", "detail": str(e)}

# Optional: expose client if needed in other modules
def get_supabase_client():
    return supabase
