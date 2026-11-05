from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# Enums & Core Verdicts
class Verdict(str, Enum):
    """Final audit verdict emitted by the rules engine."""

    APPROVE = "Approve"
    REJECT = "Reject"
    NEEDS_REVIEW = "Needs a person to check"


#  Domain Data Contracts
class PRItem(BaseModel):
    """
    A single line item parsed from purchase-request.csv.

    Columns match the CSV header exactly; all monetary values are in the
    document's native currency.
    """

    pr_number: str = Field(..., description="Purchase request identifier, e.g. 'PR-2024-001'.")
    item_code: str = Field(..., description="Unique item / SKU code.")
    description: str = Field(..., description="Human-readable item description.")
    unit: str = Field(..., description="Unit of measure, e.g. 'pcs', 'box', 'liter'.")
    quantity_requested: float = Field(..., gt=0, description="Quantity approved for procurement.")
    max_unit_price: float = Field(..., gt=0, description="Ceiling unit price authorised by procurement policy.")


class QuotationItem(BaseModel):
    """
    A single line item extracted from a supplier's quotation document.
    """

    item_code: str = Field(..., description="Item / SKU code as stated in the quote.")
    description: str = Field(..., description="Item description as stated in the quote.")
    quantity: float = Field(..., description="Quoted quantity.")
    unit: str = Field(..., description="Unit of measure stated in the quote.")
    unit_price: float = Field(..., description="Quoted unit price.")
    amount: float = Field(..., description="Line total as stated in the quote (quantity × unit_price).")


class QuotationDocument(BaseModel):
    """
    Fully structured representation of a supplier quotation PDF after parsing.

    Boolean and numeric fields default to safe/unknown values so that the
    rules engine can distinguish 'not found' from 'explicitly zero'.
    """

    # Provenance
    source_file: str = Field(..., description="Filename or path of the originating PDF.")
    supplier_name: str = Field(default="", description="Supplier / vendor name as printed on the document.")
    quotation_no: str = Field(default="", description="Quotation or reference number.")
    date: str = Field(default="", description="Document date as a string (ISO-8601 preferred).")
    reference_pr: str = Field(default="", description="Purchase-request number this quote responds to.")

    # Line Items 
    items: List[QuotationItem] = Field(default_factory=list, description="Ordered list of quoted line items.")

    # Financials 
    subtotal: float = Field(default=0.0, description="Pre-tax subtotal as stated in the document.")
    vat_percent: float = Field(default=0.0, description="VAT rate as a percentage (e.g. 12.0 for 12 %).")
    vat_amount: float = Field(default=0.0, description="VAT amount as stated in the document.")
    total: float = Field(default=0.0, description="Grand total as stated in the document.")
    is_vat_inclusive: bool = Field(
        default=False,
        description="True when the quoted prices already include VAT.",
    )

    # Tax Registration 
    tin: str = Field(default="", description="Supplier Tax Identification Number (TIN), if present.")
    bin: str = Field(default="", description="Supplier Business Identification Number (BIN), if present.")
    has_tin_or_bin: bool = Field(
        default=False,
        description="True when at least one of TIN or BIN was found on the document.",
    )

    # Payment Terms 
    advance_percent: float = Field(
        default=0.0,
        description="Advance / down-payment percentage required before delivery.",
    )
    payment_terms_days: int = Field(
        default=0,
        description="Net payment period in days as extracted from the document.",
    )
    payment_terms_max_days: int = Field(
        default=30,
        description="Policy ceiling for acceptable payment terms (days).",
    )
    payment_terms_text: str = Field(
        default="",
        description="Raw payment-terms string as it appears in the document.",
    )
    is_payment_terms_unclear_or_out_of_range: bool = Field(
        default=False,
        description="True when the payment period could not be parsed or exceeds policy limits.",
    )

    # Delivery & Penalties 
    delivery_days: int = Field(default=0, description="Promised delivery lead-time in calendar days.")
    delivery_text: str = Field(default="", description="Raw delivery-schedule string from the document.")
    has_late_penalty_clause: bool = Field(
        default=False,
        description="True when the document explicitly includes a late-delivery penalty clause.",
    )
    late_penalty_percent_per_week: float = Field(
        default=0.0,
        description="Stated late-delivery penalty as a percentage per week.",
    )
    late_penalty_text: str = Field(
        default="",
        description="Raw late-penalty clause text as extracted from the document.",
    )

    # Validity 
    validity_days: int = Field(
        default=0,
        description="Number of calendar days for which the quotation price is valid.",
    )
    validity_text: str = Field(default="", description="Raw validity-period string from the document.")

    # Full Text Payload 
    raw_text: str = Field(
        default="",
        description="Complete raw text extracted from the PDF for audit-trail and RAG purposes.",
    )


#  Validation & Guardrail Schemas
class RuleViolation(BaseModel):
    """
    A single policy violation identified by the rules engine.

    ``rule_category`` maps directly to the Verdict hierarchy:
    - ``'REJECT'``        → hard failure; quote must be rejected outright.
    - ``'NEEDS_PERSON'``  → soft flag; a human reviewer must sign off.
    """

    rule_category: str = Field(
        ...,
        description="Severity bucket: 'REJECT' or 'NEEDS_PERSON'.",
        pattern="^(REJECT|NEEDS_PERSON)$",
    )
    rule_id: str = Field(..., description="Machine-readable rule identifier, e.g. 'R-FIN-02'.")
    rule_title: str = Field(..., description="Short human-readable rule title.")
    detail: str = Field(..., description="Explanation of how and why this specific quote violates the rule.")
    exact_citation: str = Field(
        ...,
        description="Verbatim excerpt from the policy document that mandates this rule.",
    )


class MathCheckResult(BaseModel):
    """
    Outcome of the deterministic arithmetic verification pass.

    All ``calculated_*`` fields are computed from first principles; ``stated_*``
    fields are taken directly from the :class:`QuotationDocument`.
    """

    is_mathematically_sound: bool = Field(
        ...,
        description="True only when every sub-check (line totals, subtotal, VAT, total) passes.",
    )

    # Per-check pass/fail flags 
    line_total_correct: bool = Field(
        ...,
        description="True when every line's stated amount equals quantity × unit_price (within tolerance).",
    )
    subtotal_correct: bool = Field(
        ...,
        description="True when the stated subtotal equals the sum of all line amounts (within tolerance).",
    )
    vat_correct: bool = Field(
        ...,
        description="True when the stated VAT amount equals subtotal × (vat_percent / 100) (within tolerance).",
    )
    total_correct: bool = Field(
        ...,
        description="True when the stated grand total equals subtotal + vat_amount (within tolerance).",
    )

    # Computed vs stated deltas 
    calculated_line_total: float = Field(
        ...,
        description="Sum of (quantity × unit_price) recomputed across all line items.",
    )
    stated_line_total: float = Field(
        ...,
        description="Sum of the 'amount' fields as stated in the document.",
    )
    line_total_difference: float = Field(
        ...,
        description="Absolute difference: |calculated_line_total − stated_line_total|.",
    )

    calculated_vat: float = Field(..., description="VAT recomputed as subtotal × (vat_percent / 100).")
    stated_vat: float = Field(..., description="VAT amount as stated in the document.")

    calculated_total: float = Field(..., description="Grand total recomputed as subtotal + calculated_vat.")
    stated_total: float = Field(..., description="Grand total as stated in the document.")

    #  Narrative
    details: List[str] = Field(
        default_factory=list,
        description="Ordered list of human-readable messages describing each check outcome.",
    )


#  RAG Schema
class RAGRuleChunk(BaseModel):
    """
    A policy rule chunk returned by the RAG retrieval engine.

    Each chunk corresponds to one rule in the company-rules knowledge base.
    ``similarity_score`` is populated after vector search and is absent when
    chunks are loaded directly (e.g. during index construction).
    """

    rule_id: str = Field(..., description="Machine-readable rule identifier, e.g. 'R-TAX-01'.")
    rule_category: str = Field(
        ...,
        description="Top-level policy category for grouping (e.g. 'Tax', 'Payment Terms', 'Pricing').",
    )
    title: str = Field(..., description="Short rule title / heading.")
    clause_text: str = Field(..., description="Full clause text from the company-rules document.")
    similarity_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Cosine similarity score [0, 1] returned by the vector store; None for exact lookups.",
    )


#  Final Output & HITL Schema
class AuditResult(BaseModel):
    """
    The immutable audit record produced at the end of the LangGraph pipeline
    for a single supplier quotation against a single PR line item.

    This is the canonical output written to reports and surfaced in the
    Streamlit HITL panel.
    """

    # Identification 
    source_file: str = Field(..., description="Filename of the audited supplier PDF.")
    supplier_name: str = Field(..., description="Supplier name extracted from the document.")
    item_code: str = Field(..., description="PR item code this audit covers.")

    # Verdict 
    verdict: Verdict = Field(..., description="Final compliance verdict for this quotation.")
    primary_reason: str = Field(
        ...,
        description="Single-sentence human-readable rationale for the verdict.",
    )
    primary_citation: str = Field(
        ...,
        description="Verbatim policy excerpt that most directly determines the verdict.",
    )

    # Deviation Metrics 
    price_deviation_percent: float = Field(
        ...,
        description=(
            "Signed percentage by which the quoted unit price exceeds (+) or "
            "undercuts (−) the PR ceiling price: "
            "((quoted − ceiling) / ceiling) × 100."
        ),
    )
    quantity_deviation_percent: float = Field(
        ...,
        description=(
            "Signed percentage by which the quoted quantity differs from the PR "
            "requested quantity: ((quoted − requested) / requested) × 100."
        ),
    )

    # Sub-audit Results 
    math_check: MathCheckResult = Field(
        ...,
        description="Full arithmetic verification result for this quotation.",
    )
    violations: List[RuleViolation] = Field(
        default_factory=list,
        description="All policy violations identified, ordered by severity (REJECT first).",
    )

    # Human-in-the-Loop
    human_action_required: Optional[str] = Field(
        default=None,
        description=(
            "When non-None, contains a plain-English instruction for the human reviewer "
            "(e.g. 'Verify late-penalty clause wording with legal team')."
        ),
    )

    # Audit Trail 
    workflow_trace: List[Dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Ordered list of trace events emitted by each LangGraph node during "
            "this audit run. Each event is a dict with at minimum 'node' and 'timestamp' keys."
        ),
    )


# LangGraph State Contract


class AuditState(TypedDict, total=False):
    """
    Typed state dict that flows through every node of the LangGraph
    :class:`StateGraph` for a single PDF audit run.

    All fields are optional (``total=False``) except the two required
    input paths, which are always provided at graph invocation time.
    Fields are populated incrementally as the graph executes.
    """

    #  Inputs (required at invocation) 
    pdf_path: str
    """Absolute or relative path to the supplier quotation PDF being audited."""

    pr_csv_path: str
    """Absolute or relative path to the purchase-request CSV file."""

    #  Stage 1: PDF Parsing 
    raw_tokens: List[str]
    """Stream of text tokens extracted from the PDF by the tokenizer."""

    doc: Optional[QuotationDocument]
    """Structured :class:`QuotationDocument` produced by the document parser."""

    #  Stage 2: Math Verification 
    math_check: Optional[MathCheckResult]
    """Result of the deterministic arithmetic validation pass."""

    # Stage 3: RAG Retrieval 
    retrieved_rules: List[RAGRuleChunk]
    """Policy rule chunks retrieved from the vector store for this document."""

    # Stage 4: PR / Budget Validation 
    price_deviation_pct: float
    """Signed price deviation percentage vs PR ceiling."""

    qty_deviation_pct: float
    """Signed quantity deviation percentage vs PR requested quantity."""

    pr_violations: List[RuleViolation]
    """Violations found during PR budget-cap and quantity-variance checks."""

    # Stage 5: Final Audit & HITL
    final_audit: Optional[AuditResult]
    """Completed :class:`AuditResult` after all nodes have executed."""

    # Cross-cutting 
    workflow_trace: List[Dict[str, Any]]
    """Accumulated trace events emitted by every node in execution order."""

    requires_human_escalation: bool
    """Set to True by any node that determines HITL review is needed."""

    # Error Handling 
    is_error: bool
    """True when an unrecoverable error has occurred in the pipeline."""

    error_message: Optional[str]
    """Human-readable description of the error; None when ``is_error`` is False."""
