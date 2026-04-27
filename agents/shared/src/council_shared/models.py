"""Pydantic models — must match TypeScript types in packages/specialty-lens-mcp/src/lenses/types.ts."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Specialty = Literal[
    "cardiology",
    "oncology",
    "nephrology",
    "endocrinology",
    "obstetrics",
    "developmental_pediatrics",
    "psychiatry",
    "anesthesia",
]


class ProposedPlan(BaseModel):
    continue_: list[str] = Field(default_factory=list, alias="continue")
    start: list[str] = Field(default_factory=list)
    stop: list[str] = Field(default_factory=list)
    monitor: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class SpecialtyView(BaseModel):
    specialty: Specialty
    patient_id: str
    patient_summary_excerpt: str
    relevant_conditions: list[str] = Field(default_factory=list)
    relevant_medications: list[str] = Field(default_factory=list)
    relevant_observations: list[str] = Field(default_factory=list)
    applicable_guidelines: list[str] = Field(default_factory=list)
    primary_concerns: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    proposed_plan: ProposedPlan
    confidence_notes: str
    reasoning_trace: list[str] = Field(default_factory=list)
    fhir_refs: list[str] = Field(default_factory=list)


class Position(BaseModel):
    specialty: Specialty
    position: str


class Conflict(BaseModel):
    id: str
    topic: str
    parties: list[Specialty]
    positions: list[Position]
    severity: Literal["low", "medium", "high"]
    resolution_required_by_round: int | None = None


class Agreement(BaseModel):
    topic: str
    parties: list[Specialty]
    unified_position: str


class Abstention(BaseModel):
    specialty: Specialty
    topic: str
    reason: str


class ConflictMatrix(BaseModel):
    patient_id: str
    specialties: list[Specialty]
    conflicts: list[Conflict] = Field(default_factory=list)
    agreements: list[Agreement] = Field(default_factory=list)
    abstentions: list[Abstention] = Field(default_factory=list)


class BriefPlan(BaseModel):
    continue_: list[str] = Field(default_factory=list, alias="continue")
    start: list[str] = Field(default_factory=list)
    stop: list[str] = Field(default_factory=list)
    monitor: list[str] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class Brief(BaseModel):
    summary: str
    rationale: str
    plan: BriefPlan
    timing_notes: list[str] = Field(default_factory=list)


class ConflictLogEntry(BaseModel):
    topic: str
    parties: list[Specialty]
    initial_positions: list[Position]
    resolution: str
    method: Literal[
        "harmonized",
        "deferred-to-specialty",
        "guideline-aligned",
        "patient-preference",
        "unresolved",
    ]


class ActionItem(BaseModel):
    description: str
    owner: str  # 'primary-care' or a Specialty literal
    due_within: str
    priority: Literal["urgent", "high", "routine"]


class Dissent(BaseModel):
    specialty: Specialty
    position: str
    rationale: str


class AuditSummary(BaseModel):
    total_messages: int
    total_rounds: int
    fhir_resources_touched: int


class ConcordantPlan(BaseModel):
    patient_id: str
    generated_at: str
    specialties_consulted: list[Specialty]
    brief: Brief
    conflict_log: list[ConflictLogEntry] = Field(default_factory=list)
    action_items: list[ActionItem] = Field(default_factory=list)
    dissents: list[Dissent] = Field(default_factory=list)
    audit_summary: AuditSummary
