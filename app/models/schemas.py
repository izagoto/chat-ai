from typing import Literal

from pydantic import BaseModel, Field


SafetyMode = Literal["normal", "strict"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    session_id: str | None = "default"
    safety_mode: SafetyMode = "normal"
    temperature: float = Field(default=0.2, ge=0.0, le=1.5)


class ChatMessage(BaseModel):
    role: str
    content: str


class SafetyInfo(BaseModel):
    input_flagged: bool = False
    output_redacted: bool = False
    reasons: list[str] = Field(default_factory=list)


class ChatResponse(BaseModel):
    request_id: str
    session_id: str
    message: ChatMessage
    safety: SafetyInfo
    usage: dict | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=3, ge=1, le=8)
    safety_mode: SafetyMode = "normal"


class SourceItem(BaseModel):
    file: str
    excerpt: str
    score: float


class AskResponse(BaseModel):
    request_id: str
    answer: str
    sources: list[SourceItem]
    safety: SafetyInfo


class HealthResponse(BaseModel):
    status: str
    ollama: str
    model: str
    request_id: str
    detail: str | None = None


class ModelsResponse(BaseModel):
    models: list[str]
    active: str
    request_id: str


class SessionDeleteResponse(BaseModel):
    deleted: bool
    session_id: str
    request_id: str


class ErrorBody(BaseModel):
    request_id: str
    error: str
    detail: str | None = None
    reason: str | None = None
