"""Schemas Pydantic — contratos da API."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field


# ---------- Auth ----------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    name: str
    email: str
    role: str
    tenant_id: int

    class Config:
        from_attributes = True


# ---------- Leads ----------

class LeadCreate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    cpf_cnpj: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    source: str = "manual"
    source_detail: Optional[str] = None
    extra: Optional[dict[str, Any]] = None


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None


class LeadOut(BaseModel):
    id: int
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    company: Optional[str]
    city: Optional[str]
    state: Optional[str]
    source: str
    source_detail: Optional[str]
    status: str
    score: float
    propensity: Optional[str]
    enrichment_status: str
    enrichment_data: Optional[dict]
    first_seen_at: Optional[datetime]
    converted_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class Paginated(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[Any]


# ---------- Tracking ----------

class TrackEventIn(BaseModel):
    """Evento enviado pelo track.js."""
    token: str  # tracking_token público do tenant
    visitor_id: str
    session_key: str
    type: str  # pageview | click | scroll | form_submit | identify | custom
    url: Optional[str] = None
    data: Optional[dict[str, Any]] = None
    device: Optional[dict[str, Any]] = None  # {type, os, browser, screen, connection}
    referrer: Optional[str] = None
    utm: Optional[dict[str, str]] = None


class IdentifyIn(BaseModel):
    """Inforge.identify() — anônimo vira lead."""
    token: str
    visitor_id: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    company: Optional[str] = None


# ---------- Enriquecimento ----------

class EnrichRequestIn(BaseModel):
    lead_ids: list[int] = Field(..., min_length=1)
    service: str = "enrichment"  # enrichment | reactivation


class EnrichRequestOut(BaseModel):
    id: int
    service: str
    status: str
    records_sent: int
    credits_charged: int
    result: Optional[dict]
    created_at: datetime
    finished_at: Optional[datetime]

    class Config:
        from_attributes = True


# ---------- API keys ----------

class ApiKeyCreate(BaseModel):
    name: str


class ApiKeyOut(BaseModel):
    id: int
    name: str
    prefix: str
    is_active: bool
    last_used_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreated(ApiKeyOut):
    key: str  # mostrada UMA vez na criação
