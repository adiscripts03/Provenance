"""Scenario understanding and extracted facts schemas."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

class ScenarioFacts(BaseModel):
    """Structured facts extracted from plain English business scenario.

    Per AGENTS.md: Never invent facts. Missing facts must be recorded explicitly.
    """

    department: Optional[str] = Field(default=None, description="Department involved, e.g. Operations, Procurement, IT")
    region: Optional[str] = Field(default=None, description="Geographic region/city, e.g. Mumbai, Bangalore, Global")
    legal_entity: Optional[str] = Field(default=None, description="Operating legal entity name if stated")
    action_type: Optional[str] = Field(default=None, description="Type of proposed action (e.g., purchase, software_integration, write_off)")
    amount: Optional[float] = Field(default=None, description="Monetary value of proposed transaction")
    currency: Optional[str] = Field(default="INR", description="Currency symbol/code, default INR")
    vendor_status: Optional[str] = Field(default=None, description="Vendor classification: 'new', 'unreviewed', 'existing_approved', etc.")
    approvals_obtained: list[str] = Field(default_factory=list, description="Roles/individuals who already approved")
    effective_date: Optional[str] = Field(default=None, description="Date of proposed action (YYYY-MM-DD) if specified")
    free_text_notes: Optional[str] = Field(default=None, description="Relevant contextual facts extracted verbatim")
    missing_facts: list[str] = Field(default_factory=list, description="List of required or ambiguous facts not provided in scenario")
