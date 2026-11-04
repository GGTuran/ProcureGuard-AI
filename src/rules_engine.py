"""
src/rules_engine.py
===================
Hierarchical compliance policy engine and citation generator for ProcureGuard AI.

Implements two-tier policy auditing:
1. Hard REJECT rules (Priority 1)
2. NEEDS A PERSON TO CHECK rules (Priority 2)
3. Fallback APPROVE when all checks pass.

Integrates with PolicyRAGRetriever for grounded citation generation against
company compliance rules.
"""

from __future__ import annotations

from typing import List, Optional

from src.models import (
    AuditResult,
    MathCheckResult,
    QuotationDocument,
    RuleViolation,
    Verdict,
)
from src.rag_retriever import PolicyRAGRetriever


class RulesEngine:
    """
    Deterministic hierarchical compliance policy evaluation engine.

    Audits supplier quotations against company procurement rules, segregating
    hard dealbreakers from managerial review flags, and generating grounded
    citations for human auditors.
    """

    @classmethod
    def evaluate(
        cls,
        doc: QuotationDocument,
        math_check: MathCheckResult,
        pr_violations: List[RuleViolation],
        price_deviation_pct: float,
        qty_deviation_pct: float,
        rag_retriever: Optional[PolicyRAGRetriever] = None,
    ) -> AuditResult:
        """
        Evaluate a supplier quotation against all hierarchical policy rules.

        Parameters
        ----------
        doc:
            The parsed QuotationDocument under audit.
        math_check:
            The outcome of the arithmetic verification pass.
        pr_violations:
            Violations originating from purchase-request cross-validation.
        price_deviation_pct:
            Signed price deviation percentage relative to PR ceiling.
        qty_deviation_pct:
            Percentage quantity discrepancy relative to PR requested quantity.
        rag_retriever:
            Optional PolicyRAGRetriever instance used for grounded citations.

        Returns
        -------
        AuditResult
            Final audit decision, primary rationale, grounded citations, and
            hierarchical list of violations.
        """
        reject_violations: List[RuleViolation] = []
        needs_person_violations: List[RuleViolation] = []

        # Ingest pre-computed PR cross-validation violations
        for v in pr_violations:
            if v.rule_category == "REJECT":
                reject_violations.append(v)
            else:
                needs_person_violations.append(v)

        # ------------------------------------------------------------------
        # Step 1: Evaluate Hard REJECT Rules (Priority 1)
        # ------------------------------------------------------------------

        # Rule 1.2: Advance payment > 20%
        if doc.advance_percent is not None and doc.advance_percent > 20.0:
            citation_text = doc.payment_terms_text or f"{doc.advance_percent:.1f}% advance"
            reject_violations.append(
                RuleViolation(
                    rule_category="REJECT",
                    rule_id="REJECT_2_ADVANCE_EXCESS",
                    rule_title="Advance Payment Exceeds 20% Limit",
                    detail=(
                        f"Quoted advance payment of {doc.advance_percent:.1f}% exceeds "
                        f"the maximum allowable ceiling of 20.0%."
                    ),
                    exact_citation=citation_text,
                )
            )

        # Rule 1.3: Penalty clause missing or substandard (< 0.5% per week)
        if not doc.has_late_penalty_clause:
            reject_violations.append(
                RuleViolation(
                    rule_category="REJECT",
                    rule_id="REJECT_3_PENALTY_MISSING",
                    rule_title="No Late-Delivery Penalty Clause",
                    detail="The quotation terms and conditions omit a mandatory late-delivery penalty clause.",
                    exact_citation="N/A - late-delivery penalty clause is absent from contract terms",
                )
            )
        elif (
            doc.late_penalty_percent_per_week is not None
            and doc.late_penalty_percent_per_week < 0.5
        ):
            citation_text = doc.late_penalty_text or f"{doc.late_penalty_percent_per_week:.2f}% per week"
            reject_violations.append(
                RuleViolation(
                    rule_category="REJECT",
                    rule_id="REJECT_3_PENALTY_SUBSTANDARD",
                    rule_title="Late-Delivery Penalty Below 0.5% Minimum",
                    detail=(
                        f"Quoted late-delivery penalty of {doc.late_penalty_percent_per_week:.2f}% "
                        f"per week is below the mandatory policy minimum of 0.50% per week."
                    ),
                    exact_citation=citation_text,
                )
            )

        # Rule 1.4: Missing supplier TIN or BIN
        if not doc.has_tin_or_bin:
            # Check for standard fallback text in raw text
            exact_cit = "Supplier registration details available on request."
            if doc.raw_text and exact_cit in doc.raw_text:
                citation_text = exact_cit
            else:
                citation_text = "N/A - supplier TIN/BIN omitted from quotation"

            reject_violations.append(
                RuleViolation(
                    rule_category="REJECT",
                    rule_id="REJECT_4_TIN_BIN_MISSING",
                    rule_title="Missing Supplier TIN or BIN",
                    detail="The supplier's Tax Identification Number (TIN) or Business Identification Number (BIN) is missing.",
                    exact_citation=citation_text,
                )
            )

        # Rule 1.5: Delivery promised later than 45 days after purchase order
        if doc.delivery_days is not None and doc.delivery_days > 45:
            citation_text = doc.delivery_text or f"Delivery within {doc.delivery_days} days of PO."
            reject_violations.append(
                RuleViolation(
                    rule_category="REJECT",
                    rule_id="REJECT_5_DELIVERY_EXCESS",
                    rule_title="Promised Delivery Exceeds 45 Days",
                    detail=(
                        f"Promised delivery timeframe of {doc.delivery_days} days exceeds "
                        f"the authorized ceiling of 45 days after purchase order."
                    ),
                    exact_citation=citation_text,
                )
            )

        # ------------------------------------------------------------------
        # Step 2: Evaluate NEEDS A PERSON TO CHECK Rules (Priority 2)
        # ------------------------------------------------------------------

        # Rule 2.3: Payment terms unclear or outside 30 to 60 days
        if doc.is_payment_terms_unclear_or_out_of_range:
            citation_text = doc.payment_terms_text or "Payment terms unclear or out of range"
            needs_person_violations.append(
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="NEEDS_PERSON_3_PAYMENT_TERMS",
                    rule_title="Payment Terms Outside 30-60 Days Window",
                    detail=(
                        f"Quoted payment terms are unclear or outside the required 30 to 60 days "
                        f"settlement window: '{citation_text}'."
                    ),
                    exact_citation=citation_text,
                )
            )
        elif doc.payment_terms_days is not None and (
            doc.payment_terms_days < 30 or doc.payment_terms_days > 60
        ):
            citation_text = doc.payment_terms_text or f"within {doc.payment_terms_days} days"
            needs_person_violations.append(
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="NEEDS_PERSON_3_PAYMENT_TERMS",
                    rule_title="Payment Terms Outside 30-60 Days Window",
                    detail=(
                        f"Quoted payment period of {doc.payment_terms_days} days falls outside "
                        f"the standard 30 to 60 days window."
                    ),
                    exact_citation=citation_text,
                )
            )

        # Rule 2.4: Delivery promised in 31 to 45 days
        if doc.delivery_days is not None and 31 <= doc.delivery_days <= 45:
            citation_text = doc.delivery_text or f"Delivery within {doc.delivery_days} days of PO."
            needs_person_violations.append(
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="NEEDS_PERSON_4_DELIVERY_WINDOW",
                    rule_title="Extended Delivery Timeline (31 to 45 Days)",
                    detail=(
                        f"Promised delivery timeframe of {doc.delivery_days} days falls within "
                        f"the discretionary 31 to 45 days management review window."
                    ),
                    exact_citation=citation_text,
                )
            )

        # Rule 2.5: VAT is not shown separately at 15%
        if doc.is_vat_inclusive or doc.vat_amount is None or not math_check.vat_correct:
            if doc.is_vat_inclusive:
                citation_text = "Unit price (BDT, VAT included)"
                detail_msg = "VAT is not shown separately at 15% (quotation prices are inclusive of taxes)."
            elif doc.vat_percent and abs(doc.vat_percent - 15.0) > 0.05:
                citation_text = f"VAT {doc.vat_percent}%"
                detail_msg = f"VAT rate is stated at {doc.vat_percent}%, differing from the mandatory 15% rate."
            else:
                citation_text = "VAT not itemized separately at 15%"
                detail_msg = "VAT is not shown separately at 15% on the quotation."

            needs_person_violations.append(
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="NEEDS_PERSON_5_VAT_NOT_SEPARATE",
                    rule_title="VAT Not Separately Stated at 15%",
                    detail=detail_msg,
                    exact_citation=citation_text,
                )
            )

        # Rule 2.6: The numbers do not add up (arithmetic discrepancy)
        is_arithmetic_discrepancy = (
            not math_check.line_total_correct
            or not math_check.subtotal_correct
            or not math_check.total_correct
            or (not math_check.is_mathematically_sound and not doc.is_vat_inclusive)
        )
        if is_arithmetic_discrepancy:
            mismatch_details = [
                d for d in math_check.details
                if "mismatch" in d.lower() or "discrepancy" in d.lower() or "differs" in d.lower()
            ]
            detail_str = "; ".join(mismatch_details) if mismatch_details else "; ".join(math_check.details)
            exact_cit = (
                f"Line diff: {math_check.line_total_difference:.2f} BDT "
                f"(calc: {math_check.calculated_line_total:.2f}, stated: {math_check.stated_line_total:.2f})"
            )
            needs_person_violations.append(
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="NEEDS_PERSON_6_MATH_ERROR",
                    rule_title="Mathematical Calculation Discrepancy",
                    detail=f"Arithmetic verification failed: {detail_str}",
                    exact_citation=exact_cit,
                )
            )

        # Rule 2.7: Quotation validity under 30 days
        if doc.validity_days is not None and 0 < doc.validity_days < 30:
            citation_text = doc.validity_text or f"valid for {doc.validity_days} days"
            needs_person_violations.append(
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="NEEDS_PERSON_7_SHORT_VALIDITY",
                    rule_title="Quotation Validity Under 30 Days",
                    detail=(
                        f"Quotation validity period of {doc.validity_days} days is below "
                        f"the minimum 30-day requirement."
                    ),
                    exact_citation=citation_text,
                )
            )

        # ------------------------------------------------------------------
        # Step 3: Synthesize Final Decision & Citation Grounding
        # ------------------------------------------------------------------
        all_violations = reject_violations + needs_person_violations
        item_code = doc.items[0].item_code if doc.items else "N/A"

        if reject_violations:
            verdict = Verdict.REJECT
            primary_v = reject_violations[0]
            primary_reason = f"REJECTED: {primary_v.rule_title}. {primary_v.detail}"

            if rag_retriever:
                chunk = rag_retriever.get_rule_by_id(primary_v.rule_id)
                if not chunk:
                    chunks = rag_retriever.retrieve_relevant_rule(primary_v.detail, top_k=1)
                    chunk = chunks[0] if chunks else None
                if chunk:
                    primary_citation = rag_retriever.format_grounded_citation(chunk, primary_v.exact_citation)
                else:
                    primary_citation = primary_v.exact_citation
            else:
                primary_citation = primary_v.exact_citation

            human_action_required = None

        elif needs_person_violations:
            verdict = Verdict.NEEDS_REVIEW
            primary_v = needs_person_violations[0]
            reasons_combined = "; ".join([f"{v.rule_title} ({v.detail})" for v in needs_person_violations])
            primary_reason = f"HUMAN AUDIT REQUIRED: {reasons_combined}"
            human_action_required = "Review required by Procurement Officer."

            if rag_retriever:
                chunk = rag_retriever.get_rule_by_id(primary_v.rule_id)
                if not chunk:
                    chunks = rag_retriever.retrieve_relevant_rule(primary_v.detail, top_k=1)
                    chunk = chunks[0] if chunks else None
                if chunk:
                    primary_citation = rag_retriever.format_grounded_citation(chunk, primary_v.exact_citation)
                else:
                    primary_citation = primary_v.exact_citation
            else:
                primary_citation = primary_v.exact_citation

        else:
            verdict = Verdict.APPROVE
            primary_reason = (
                "APPROVED: Quotation complies with all company procurement policies, "
                "unit price and quantity match PR requirements within tolerance, "
                "VAT is properly separated at 15%, and arithmetic is 100% verified."
            )
            ref_pr = doc.reference_pr or "PR-2026-114"
            primary_citation = f"Quotation {doc.quotation_no or 'QT'} fully compliant with {ref_pr}."
            human_action_required = None

        return AuditResult(
            source_file=doc.source_file,
            supplier_name=doc.supplier_name,
            item_code=item_code,
            verdict=verdict,
            primary_reason=primary_reason,
            primary_citation=primary_citation,
            price_deviation_percent=price_deviation_pct,
            quantity_deviation_percent=qty_deviation_pct,
            math_check=math_check,
            violations=all_violations,
            human_action_required=human_action_required,
            workflow_trace=[],
        )
