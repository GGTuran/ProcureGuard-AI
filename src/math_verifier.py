"""
src/math_verifier.py
====================
Deterministic mathematical integrity verification engine for ProcureGuard AI.

Performs strict arithmetic audits on supplier quotation documents to catch
calculation discrepancies, rounding inconsistencies, subtotal errors,
missing or non-compliant VAT structures, and grand total mismatches.

Conforms to:
- Company Rule (Needs Person 6): "The numbers do not add up (for example line total or subtotal is wrong)."
- Company Rule (Needs Person 5): "VAT is not shown separately at 15%."
"""

from __future__ import annotations

from typing import List, Optional

from src.models import MathCheckResult, QuotationDocument


class MathVerifier:
    """
    Deterministic code-level arithmetic verifier for supplier quotations.

    Evaluates:
    1. Line items: quantity × unit_price == amount
    2. Subtotal: sum(line amounts) == stated subtotal
    3. VAT: subtotal × 15% == stated VAT amount (and checks VAT separation)
    4. Grand total: subtotal + VAT amount == stated grand total
    """

    TOLERANCE: float = 0.05  # 5-paisa boundary for floating-point tolerance

    @classmethod
    def verify(cls, doc: QuotationDocument) -> MathCheckResult:
        """
        Execute deterministic mathematical audit on a QuotationDocument.

        Parameters
        ----------
        doc:
            The parsed QuotationDocument to verify.

        Returns
        -------
        MathCheckResult
            Complete audit result containing pass/fail flags, calculated vs.
            stated figures, discrepancies, and diagnostic log messages.
        """
        details: List[str] = []
        line_total_correct: bool = True
        subtotal_correct: bool = True
        vat_correct: bool = True
        total_correct: bool = True
        is_mathematically_sound: bool = True

        # ------------------------------------------------------------------
        # Guard: Empty or Missing Line Items
        # ------------------------------------------------------------------
        if not doc.items:
            details.append("Line-item audit failed: No line items found in quotation document.")
            stated_tot = round(doc.total or 0.0, 2)
            return MathCheckResult(
                is_mathematically_sound=False,
                line_total_correct=False,
                subtotal_correct=False,
                vat_correct=False,
                total_correct=False,
                calculated_line_total=0.0,
                stated_line_total=0.0,
                line_total_difference=0.0,
                calculated_vat=0.0,
                stated_vat=round(doc.vat_amount or 0.0, 2),
                calculated_total=0.0,
                stated_total=stated_tot,
                details=details,
            )

        # ------------------------------------------------------------------
        # 1. Line-Level Arithmetic Audit
        # ------------------------------------------------------------------
        calculated_line_total: float = 0.0
        stated_line_total: float = 0.0

        for item in doc.items:
            qty = float(item.quantity) if item.quantity is not None else 0.0
            price = float(item.unit_price) if item.unit_price is not None else 0.0
            stated_amt = float(item.amount) if item.amount is not None else 0.0

            calc_amt = round(qty * price, 2)
            stated_amt = round(stated_amt, 2)
            line_diff = round(abs(calc_amt - stated_amt), 2)

            calculated_line_total += calc_amt
            stated_line_total += stated_amt

            if line_diff > cls.TOLERANCE:
                line_total_correct = False
                is_mathematically_sound = False
                details.append(
                    f"Line item '{item.item_code}' arithmetic mismatch: "
                    f"quantity ({qty:g}) * unit_price ({price:.2f}) = {calc_amt:.2f}, "
                    f"but stated amount is {stated_amt:.2f} "
                    f"(discrepancy: {line_diff:.2f} > tolerance {cls.TOLERANCE})."
                )
            else:
                details.append(
                    f"Line item '{item.item_code}' arithmetic verified: "
                    f"quantity ({qty:g}) * unit_price ({price:.2f}) = {calc_amt:.2f} "
                    f"matches stated amount {stated_amt:.2f}."
                )

        calculated_line_total = round(calculated_line_total, 2)
        stated_line_total = round(stated_line_total, 2)
        line_total_difference = round(abs(calculated_line_total - stated_line_total), 2)

        # ------------------------------------------------------------------
        # 2. Subtotal Audit
        # ------------------------------------------------------------------
        doc_subtotal = float(doc.subtotal) if doc.subtotal is not None else 0.0

        if doc_subtotal > 0:
            subtotal_diff = round(abs(doc_subtotal - calculated_line_total), 2)
            if subtotal_diff > cls.TOLERANCE:
                subtotal_correct = False
                is_mathematically_sound = False
                details.append(
                    f"Subtotal mismatch: stated subtotal ({doc_subtotal:.2f}) differs from "
                    f"calculated line total ({calculated_line_total:.2f}) "
                    f"by {subtotal_diff:.2f} (tolerance: {cls.TOLERANCE})."
                )
            else:
                details.append(
                    f"Subtotal verified: stated subtotal ({doc_subtotal:.2f}) matches "
                    f"calculated line total ({calculated_line_total:.2f})."
                )
        else:
            if doc.is_vat_inclusive:
                subtotal_correct = True
                details.append(
                    "Subtotal not separately stated (quotation specifies VAT-inclusive pricing)."
                )
            else:
                subtotal_correct = False
                is_mathematically_sound = False
                details.append("Subtotal audit failed: Subtotal is missing or zero.")

        # ------------------------------------------------------------------
        # 3. VAT Structure Audit (Needs Person Rule 5)
        # ------------------------------------------------------------------
        base_for_vat = doc_subtotal if doc_subtotal > 0 else calculated_line_total
        calc_vat = round(base_for_vat * 0.15, 2) if not doc.is_vat_inclusive else 0.0
        doc_vat_amt = float(doc.vat_amount) if doc.vat_amount is not None else 0.0
        doc_vat_pct = float(doc.vat_percent) if doc.vat_percent is not None else 0.0

        if doc_vat_amt > 0:
            vat_diff = round(abs(doc_vat_amt - calc_vat), 2)
            pct_matches = abs(doc_vat_pct - 15.0) <= cls.TOLERANCE

            if vat_diff > cls.TOLERANCE or not pct_matches:
                vat_correct = False
                is_mathematically_sound = False
                details.append(
                    f"VAT structure mismatch: stated VAT is {doc_vat_amt:.2f} ({doc_vat_pct:.1f}%), "
                    f"expected 15% VAT on base {base_for_vat:.2f} is {calc_vat:.2f} "
                    f"(discrepancy: {vat_diff:.2f})."
                )
            else:
                vat_correct = True
                details.append(
                    f"VAT structure verified: stated VAT ({doc_vat_amt:.2f} at {doc_vat_pct:.1f}%) "
                    f"matches expected 15% VAT ({calc_vat:.2f})."
                )
        elif doc.is_vat_inclusive:
            vat_correct = False
            is_mathematically_sound = False
            details.append(
                "VAT structure flagged: VAT is not shown separately at 15% "
                "(quotation uses VAT-inclusive pricing)."
            )
        else:
            vat_correct = False
            is_mathematically_sound = False
            details.append(
                "VAT structure flagged: VAT is neither itemized separately at 15% "
                "nor declared inclusive."
            )

        # ------------------------------------------------------------------
        # 4. Grand Total Audit
        # ------------------------------------------------------------------
        if not doc.is_vat_inclusive and doc_vat_amt > 0:
            calc_total = round(doc_subtotal + doc_vat_amt, 2)
        else:
            calc_total = round(stated_line_total, 2)

        doc_total = float(doc.total) if doc.total is not None else 0.0

        if doc_total > 0:
            total_diff = round(abs(doc_total - calc_total), 2)
            if total_diff > cls.TOLERANCE:
                total_correct = False
                is_mathematically_sound = False
                details.append(
                    f"Grand total mismatch: stated total ({doc_total:.2f}) differs from "
                    f"calculated total ({calc_total:.2f}) by {total_diff:.2f} "
                    f"(tolerance: {cls.TOLERANCE})."
                )
            else:
                total_correct = True
                details.append(
                    f"Grand total verified: stated total ({doc_total:.2f}) matches "
                    f"calculated total ({calc_total:.2f})."
                )
        else:
            total_correct = False
            is_mathematically_sound = False
            details.append("Grand total audit failed: Grand total is missing or zero.")

        # Final reconciliation: sound only if all sub-checks passed
        is_mathematically_sound = (
            line_total_correct
            and subtotal_correct
            and vat_correct
            and total_correct
        )

        return MathCheckResult(
            is_mathematically_sound=is_mathematically_sound,
            line_total_correct=line_total_correct,
            subtotal_correct=subtotal_correct,
            vat_correct=vat_correct,
            total_correct=total_correct,
            calculated_line_total=calculated_line_total,
            stated_line_total=stated_line_total,
            line_total_difference=line_total_difference,
            calculated_vat=calc_vat,
            stated_vat=round(doc_vat_amt, 2),
            calculated_total=calc_total,
            stated_total=round(doc_total, 2),
            details=details,
        )
