"""Minimal FastAPI application scaffold for the project."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    api_version: str


app = FastAPI(
    title="AI Realtime Video Summary Generator API",
    description="Backend entry point for the meeting summarization pipeline.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    """Report that the API process is ready to receive requests."""
    return HealthResponse(status="ok", service="backend", api_version="v1")
