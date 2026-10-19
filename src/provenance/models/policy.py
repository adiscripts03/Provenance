"""Policy and document metadata schemas."""

from __future__ import annotations

from enum import Enum, IntEnum
from typing import Optional
from pydantic import BaseModel, Field

class PrecedenceLevel(IntEnum):
    """Authority precedence levels per README specification."""

    LEVEL_1_UPDATE_EXCEPTION = 1
    LEVEL_2_REGIONAL_DEPT = 2
    LEVEL_3_ENTERPRISE = 3
    LEVEL_4_OPERATIONAL_SOP = 4
    LEVEL_5_HISTORICAL = 5

class DocumentStatus(str, Enum):
    """Lifecycle and trust status of enterprise documents."""

    ACTIVE = "active"
    SUPERSEDED = "superseded"
    DRAFT = "draft"
    EXPIRED = "expired"
    UNTRUSTED = "untrusted"

class DocumentMetadata(BaseModel):
    """Frontmatter metadata extracted from policy markdown documents."""

    doc_id: str = Field(description="Unique document identifier, e.g. POL-PROC-2025-001")
    title: str = Field(description="Official policy title")
    doc_type: str = Field(description="Document type (policy, sop, memo, exception_waiver, etc.)")
    level: PrecedenceLevel = Field(description="Precedence level 1 through 5")
    owner: str = Field(description="Role or executive owning the policy")
    department: Optional[str] = Field(default=None, description="Department scope")
    region: Optional[str] = Field(default=None, description="Regional scope (Global, Mumbai, APAC, etc.)")
    legal_entity: Optional[str] = Field(default=None, description="Legal entity applicability")
    effective_date: str = Field(description="ISO date YYYY-MM-DD")
    expiry_date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD or None")
    status: DocumentStatus = Field(description="Document status")
    supersedes: Optional[str] = Field(default=None, description="doc_id of superseded document if any")

class PolicyChunk(BaseModel):
    """Section-level chunk of a policy document with stable identifier."""

    chunk_id: str = Field(description="Stable chunk id formatted as {doc_id}#{section_id}")
    doc_id: str = Field(description="Parent document ID")
    section_id: str = Field(description="Section number, e.g. §4.2")
    section_title: str = Field(description="Section heading title")
    content: str = Field(description="Full text content of the section")
    metadata: DocumentMetadata = Field(description="Parent document metadata")
