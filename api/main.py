from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import deps
from api.routers.cv import router as cv_router
from api.routers.jobs import router as jobs_router
from config import get_settings
from db.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    deps._db = Database()
    deps._db.init_schema()
    yield


app = FastAPI(
    title="Job Seeker Assistant API",
    description="REST API powering the job seeker assistant. Consumed by the Next.js frontend.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cv_router, prefix="/api")
app.include_router(jobs_router, prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    _s = get_settings()
    uvicorn.run("api.main:app", host=_s.api_host, port=_s.api_port, reload=_s.api_reload)
