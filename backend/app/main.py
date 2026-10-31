import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routers import agent, auth, knowledge, meeting_rooms, reservations, stats, users, venues
from app.core.config import settings
from app.init_db import init_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("meeting-room-agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.INIT_DB_ON_STARTUP:
        init_database()
        logger.info("数据库初始化完成")
    yield


app = FastAPI(title="智能会议室预约系统 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.CORS_ORIGINS.split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """把参数校验错误转换成前端可直接提示的文案。"""
    errors = exc.errors()
    if errors:
        first = errors[0]
        message = first.get("msg", "请求参数不合法")
        message = message.replace("Value error, ", "")
        return JSONResponse(status_code=422, content={"detail": message})
    return JSONResponse(status_code=422, content={"detail": "请求参数不合法"})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(venues.router)
app.include_router(meeting_rooms.router)
app.include_router(reservations.router)
app.include_router(stats.router)
app.include_router(knowledge.router)
app.include_router(agent.router)


@app.get("/")
def root():
    return {"message": "智能会议室预约系统 API 已启动", "docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok"}
