from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


SafetyMode = Literal["normal", "strict"]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = None
    session_id: str | None = "default"
    collection_id: str | None = None
    use_documents: bool = True
    safety_mode: SafetyMode = "normal"
    temperature: float = Field(default=0.5, ge=0.0, le=1.5)
    edit_message_id: int | None = None


class ChatMessage(BaseModel):
    role: str
    content: str


class SafetyInfo(BaseModel):
    input_flagged: bool = False
    output_redacted: bool = False
    reasons: list[str] = Field(default_factory=list)


class SourceItem(BaseModel):
    file: str
    excerpt: str
    score: float
    document_id: str | None = None
    evidence_id: str | None = None  # legacy alias
    artifact_type: str | None = None
    location: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    session_id: str
    conversation_id: str | None = None
    message: ChatMessage
    sources: list[SourceItem] = Field(default_factory=list)
    safety: SafetyInfo
    usage: dict | None = None


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    top_k: int = Field(default=3, ge=1, le=8)
    safety_mode: SafetyMode = "normal"


class AskResponse(BaseModel):
    request_id: str
    answer: str
    sources: list[SourceItem]
    safety: SafetyInfo


class DocumentRecordItem(BaseModel):
    document_id: str
    filename: str
    artifact_type: str
    sha256: str
    ingested_at: str
    chunk_count: int
    status: str = "ready"
    error: str | None = None
    source_url: str | None = None


class UrlIngestRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)


class DocumentUploadResponse(BaseModel):
    request_id: str
    collection_id: str
    document: DocumentRecordItem


class DocumentListResponse(BaseModel):
    request_id: str
    collection_id: str
    documents: list[DocumentRecordItem]
    total_chunks: int


class ImageAnalysisResponse(BaseModel):
    request_id: str
    result: dict[str, Any]


class VideoAnalysisResponse(BaseModel):
    request_id: str
    result: dict[str, Any]


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


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(BaseModel):
    id: int
    email: EmailStr
    fullname: str
    role: str


class LoginResponse(BaseModel):
    request_id: str
    token: str
    user: UserOut


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: str
    sources: list[SourceItem] = Field(default_factory=list)


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    request_id: str
    conversations: list[ConversationOut]


class ConversationResponse(BaseModel):
    request_id: str
    conversation: ConversationDetail


class PromptUpdateRequest(BaseModel):
    prompt: str = Field(default="", max_length=12000)


class PromptResponse(BaseModel):
    request_id: str
    prompt: str
    default_prompt: str
    is_custom: bool
