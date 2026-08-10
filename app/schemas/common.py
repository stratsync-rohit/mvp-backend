"""Shared Pydantic schemas used across multiple resources."""
from pydantic import BaseModel, Field


class Vessel(BaseModel):
    id: str
    name: str


class ActionButton(BaseModel):
    key: str
    label: str


class ErrorResponse(BaseModel):
    detail: str


class SuccessResponse(BaseModel):
    success: bool = True
    message: str | None = None


class DeleteRiskResponse(BaseModel):
    success: bool = True
    riskId: str


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    database: str | None = None
