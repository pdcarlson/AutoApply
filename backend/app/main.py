"""FastAPI entry point. Run with: uvicorn app.main:app --reload"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import Base, engine
from app.routers import answers, applications, profile, users


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # TODO: switch to Alembic migrations once the schema settles
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Auto Apply API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


app.include_router(users.router)
app.include_router(profile.router)
app.include_router(answers.router)
app.include_router(applications.router)
