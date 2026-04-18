"""
TechShop Sales Advisor — Production-ready AI Agent

Features:
  ✅ Local LLM via Ollama (qwen2.5:3b) + mock fallback
  ✅ Chat UI tại /
  ✅ Redis session (stateless)
  ✅ API key authentication
  ✅ Rate limiting (10 req/min)
  ✅ Cost guard
  ✅ Health + Readiness probe
  ✅ Graceful shutdown
  ✅ Structured JSON logging
  ✅ Security headers
"""
import os
import sys
import time
import signal
import logging
import json
import uuid
from datetime import datetime, timezone
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Security, Depends, Request, Response
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
try:
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    _has_static = True
except ImportError:
    _has_static = False
from pydantic import BaseModel, Field
import uvicorn

from app.config import settings
from utils.llm import ask as llm_ask

# ─────────────────────────────────────────────────────────
# Logging — Structured JSON
# ─────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format='{"ts":"%(asctime)s","lvl":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
_is_ready = False
_in_flight = 0
_request_count = 0

# ─────────────────────────────────────────────────────────
# Redis Session Storage (fallback to in-memory)
# ─────────────────────────────────────────────────────────
_use_redis = False
_redis = None
_memory_store: dict = {}

def _init_redis():
    global _redis, _use_redis
    if not settings.redis_url:
        return
    try:
        import redis as redis_lib
        _redis = redis_lib.from_url(settings.redis_url, decode_responses=True)
        _redis.ping()
        _use_redis = True
        logger.info(json.dumps({"event": "redis_connected", "url": settings.redis_url}))
    except Exception as e:
        logger.warning(json.dumps({"event": "redis_unavailable", "error": str(e)}))

def get_history(session_id: str) -> list:
    if _use_redis:
        raw = _redis.lrange(f"chat:{session_id}", 0, -1)
        return [json.loads(m) for m in raw]
    return _memory_store.get(f"chat:{session_id}", [])

def save_message(session_id: str, role: str, content: str):
    msg = json.dumps({"role": role, "content": content})
    if _use_redis:
        _redis.rpush(f"chat:{session_id}", msg)
        _redis.expire(f"chat:{session_id}", 3600)
    else:
        key = f"chat:{session_id}"
        _memory_store.setdefault(key, [])
        _memory_store[key].append({"role": role, "content": content})
        if len(_memory_store[key]) > 20:
            _memory_store[key] = _memory_store[key][-20:]

# ─────────────────────────────────────────────────────────
# Rate Limiter — Sliding Window
# ─────────────────────────────────────────────────────────
_rate_windows: dict[str, deque] = defaultdict(deque)

def check_rate_limit(key: str):
    now = time.time()
    window = _rate_windows[key]
    while window and window[0] < now - 60:
        window.popleft()
    if len(window) >= settings.rate_limit_per_minute:
        raise HTTPException(
            429,
            detail=f"Rate limit exceeded: {settings.rate_limit_per_minute} req/min. Thử lại sau 60 giây.",
            headers={"Retry-After": "60"},
        )
    window.append(now)

# ─────────────────────────────────────────────────────────
# Cost Guard
# ─────────────────────────────────────────────────────────
_daily_cost: dict[str, float] = defaultdict(float)
_global_cost = 0.0
_cost_day = time.strftime("%Y-%m-%d")

def check_cost(user_key: str, tokens: int = 100):
    global _global_cost, _cost_day
    today = time.strftime("%Y-%m-%d")
    if today != _cost_day:
        _daily_cost.clear()
        _global_cost = 0.0
        _cost_day = today
    if _global_cost >= settings.global_daily_budget_usd:
        raise HTTPException(503, "Service tạm thời không khả dụng do giới hạn ngân sách.")
    cost = (tokens / 1000) * 0.0002
    if _daily_cost[user_key] + cost >= settings.daily_budget_usd:
        raise HTTPException(402, "Ngân sách ngày của bạn đã hết. Thử lại vào ngày mai.")
    _daily_cost[user_key] += cost
    _global_cost += cost

# ─────────────────────────────────────────────────────────
# Authentication
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            401,
            detail="API key không hợp lệ. Thêm header: X-API-Key: <key>",
        )
    return api_key

# ─────────────────────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    _init_redis()
    logger.info(json.dumps({
        "event": "startup",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.environment,
        "redis": _use_redis,
    }))
    _is_ready = True
    logger.info(json.dumps({"event": "ready"}))
    yield
    _is_ready = False
    timeout, elapsed = 30, 0
    while _in_flight > 0 and elapsed < timeout:
        time.sleep(1); elapsed += 1
    logger.info(json.dumps({"event": "shutdown"}))

# ─────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs" if settings.environment != "production" else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)

@app.middleware("http")
async def middleware(request: Request, call_next):
    global _in_flight, _request_count
    _in_flight += 1
    _request_count += 1
    start = time.time()
    try:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        if "server" in response.headers:
            del response.headers["server"]
        logger.info(json.dumps({
            "event": "request",
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "ms": round((time.time() - start) * 1000, 1),
        }))
        return response
    finally:
        _in_flight -= 1

# Static files (Chat UI)
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# ─────────────────────────────────────────────────────────
# Models
# ─────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = None

class ChatResponse(BaseModel):
    session_id: str
    question: str
    answer: str
    model: str
    timestamp: str

# ─────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
def ui():
    index = os.path.join(static_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return {"app": settings.app_name, "ui": "static/index.html not found"}


@app.post("/chat", response_model=ChatResponse, tags=["Sales Advisor"])
async def chat(body: ChatRequest, _key: str = Depends(verify_api_key)):
    """Gửi câu hỏi đến Sales Advisor. Yêu cầu header X-API-Key."""
    check_rate_limit(_key[:8])
    check_cost(_key[:8], tokens=len(body.question.split()) * 3)

    session_id = body.session_id or str(uuid.uuid4())
    history = get_history(session_id)

    save_message(session_id, "user", body.question)

    answer, backend = llm_ask(body.question, history)

    save_message(session_id, "assistant", answer)

    logger.info(json.dumps({
        "event": "chat",
        "session": session_id[:8],
        "backend": backend,
        "q_len": len(body.question),
    }))

    return ChatResponse(
        session_id=session_id,
        question=body.question,
        answer=answer,
        model=backend,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@app.delete("/chat/{session_id}", tags=["Sales Advisor"])
def clear_session(session_id: str, _key: str = Depends(verify_api_key)):
    """Xóa lịch sử hội thoại."""
    if _use_redis:
        _redis.delete(f"chat:{session_id}")
    else:
        _memory_store.pop(f"chat:{session_id}", None)
    return {"deleted": session_id}


@app.get("/health", tags=["Ops"])
def health():
    return {
        "status": "ok",
        "version": settings.app_version,
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "total_requests": _request_count,
        "redis": _use_redis,
        "llm": "groq" if os.getenv("GROQ_API_KEY") else "ollama/mock",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready", tags=["Ops"])
def ready():
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    if _use_redis:
        try:
            _redis.ping()
        except Exception:
            raise HTTPException(503, "Redis unavailable")
    return {"ready": True, "in_flight": _in_flight}


# ─────────────────────────────────────────────────────────
# Graceful Shutdown
# ─────────────────────────────────────────────────────────
def _handle_signal(signum, _frame):
    global _is_ready
    _is_ready = False
    logger.info(json.dumps({"event": "signal", "signum": signum}))
    timeout, elapsed = 30, 0
    while _in_flight > 0 and elapsed < timeout:
        time.sleep(1); elapsed += 1
    logger.info(json.dumps({"event": "shutdown_complete"}))
    sys.exit(0)

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


if __name__ == "__main__":
    logger.info(f"Starting {settings.app_name} on port {settings.port}")
    logger.info(f"API Key: {settings.agent_api_key[:4]}****")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        timeout_graceful_shutdown=30,
    )
