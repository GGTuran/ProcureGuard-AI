"""
src/pr_validator.py
===================
Purchase Request (PR) cross-validation and variance analysis engine
for ProcureGuard AI.

Validates supplier quotation documents against authorized purchase requests,
performing price cap verification (Reject Rule 1, Needs Person Rule 1) and
quantity discrepancy audits (Needs Person Rule 2).
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.models import PRItem, QuotationDocument, RuleViolation


class PRValidator:
    """
    Engine for cross-validating supplier quotations against authorized
    purchase requests (PR).

    Loads purchase requests from CSV, indexes items by code ('A' through 'E'),
    and computes percentage variances for unit price and order quantity.
    """

    def __init__(self, pr_csv_path: str) -> None:
        """
        Initialize the PRValidator and load reference purchase requests.

        Parameters
        ----------
        pr_csv_path:
            Path to the purchase-request.csv file.

        Raises
        ------
        FileNotFoundError:
            If pr_csv_path does not exist.
        """
        path = Path(pr_csv_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"PRValidator: purchase request file not found: {pr_csv_path!r}"
            )

        self.pr_items: Dict[str, PRItem] = {}
        self._load_pr_file(path)

    def _load_pr_file(self, path: Path) -> None:
        """Parse CSV rows into PRItem domain models, keyed by item code."""
        with open(path, mode="r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Clean headers and values of whitespace
                clean_row = {
                    (k.strip() if k else ""): (v.strip() if v else "")
                    for k, v in row.items()
                }
                item_code = clean_row.get("Item", "")
                if not item_code:
                    continue

                try:
                    qty = float(clean_row.get("Quantity requested", "0").replace(",", ""))
                    max_price = float(clean_row.get("Maximum unit price (BDT)", "0").replace(",", ""))
                except ValueError:
                    continue

                pr_item = PRItem(
                    pr_number=clean_row.get("PR number", ""),
                    item_code=item_code,
                    description=clean_row.get("Description", ""),
                    unit=clean_row.get("Unit", ""),
                    quantity_requested=qty,
                    max_unit_price=max_price,
                )
                self.pr_items[item_code] = pr_item

    def get_pr_item(self, item_code: str) -> Optional[PRItem]:
        """
        Retrieve PRItem by its code (e.g. 'A', 'B', etc.).

        Parameters
        ----------
        item_code:
            The item code to look up.

        Returns
        -------
        Optional[PRItem]
            The matching PRItem if found, else None.
        """
        if not item_code:
            return None
        return self.pr_items.get(item_code.strip())

    def audit_quotation_against_pr(
        self, doc: QuotationDocument
    ) -> Tuple[float, float, List[RuleViolation]]:
        """
        Audit a supplier QuotationDocument against authorized PR specifications.

        Parameters
        ----------
        doc:
            The parsed QuotationDocument to validate.

        Returns
        -------
        Tuple[float, float, List[RuleViolation]]
            (price_deviation_percent, quantity_deviation_percent, violations_list)
        """
        violations: List[RuleViolation] = []

        # ------------------------------------------------------------------
        # Guardrail 1: Document contains no line items
        # ------------------------------------------------------------------
        if not doc.items:
            violations.append(
                RuleViolation(
                    rule_category="REJECT",
                    rule_id="REJECT_NO_LINE_ITEMS",
                    rule_title="No Line Items in Quotation Document",
                    detail="Quotation document contains no line items to validate against the purchase request.",
                    exact_citation="N/A - missing items table",
                )
            )
            return 0.0, 0.0, violations

        # Primary line item (quotations in this context are per-item)
        item = doc.items[0]
        pr_item = self.get_pr_item(item.item_code)

        # ------------------------------------------------------------------
        # Guardrail 2: Unrecognized or mismatched item code
        # ------------------------------------------------------------------
        if not pr_item:
            violations.append(
                RuleViolation(
                    rule_category="REJECT",
                    rule_id="REJECT_UNRECOGNIZED_ITEM",
                    rule_title="Unrecognized Item Code",
                    detail=(
                        f"Quotation item code '{item.item_code}' was not found in authorized "
                        f"purchase request '{doc.reference_pr or 'PR'}'."
                    ),
                    exact_citation=f"Item: {item.item_code}",
                )
            )
            return 0.0, 0.0, violations

        # ------------------------------------------------------------------
        # Price Cap Audit Rules
        # ------------------------------------------------------------------
        quoted_price = float(item.unit_price) if item.unit_price is not None else 0.0
        max_price = float(pr_item.max_unit_price) if pr_item.max_unit_price else 1.0

        price_deviation_pct = ((quoted_price - max_price) / max_price) * 100.0

        # Reject Rule 1: Unit price > 3% above maximum authorized price
        if price_deviation_pct > 3.0:
            violations.append(
                RuleViolation(
                    rule_category="REJECT",
                    rule_id="REJECT_1_PRICE_EXCESS",
                    rule_title="Unit Price Exceeds Authorized Cap by > 3%",
                    detail=(
                        f"Quoted unit price BDT {quoted_price:.2f} exceeds authorized maximum "
                        f"price BDT {max_price:.2f} by {price_deviation_pct:.2f}% "
                        f"(exceeds 3.0% threshold)."
                    ),
                    exact_citation=f"{quoted_price:.2f}",
                )
            )
        # Needs Person Rule 1: Unit price above maximum, but <= 3%
        elif 0.0 < price_deviation_pct <= 3.0:
            violations.append(
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="NEEDS_PERSON_1_PRICE_MARGINAL",
                    rule_title="Unit Price Marginally Above Cap (<= 3%)",
                    detail=(
                        f"Quoted unit price BDT {quoted_price:.2f} is marginally above authorized maximum "
                        f"price BDT {max_price:.2f} by {price_deviation_pct:.2f}% "
                        f"(within 3.0% managerial discretion threshold)."
                    ),
                    exact_citation=f"{quoted_price:.2f}",
                )
            )

        # ------------------------------------------------------------------
        # Quantity Discrepancy Audit Rules
        # ------------------------------------------------------------------
        quoted_qty = float(item.quantity) if item.quantity is not None else 0.0
        requested_qty = float(pr_item.quantity_requested) if pr_item.quantity_requested else 1.0

        qty_deviation_pct = (abs(quoted_qty - requested_qty) / requested_qty) * 100.0

        # Needs Person Rule 2: Quantity differs by more than 5%
        if qty_deviation_pct > 5.0:
            violations.append(
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="NEEDS_PERSON_2_QTY_DISCREPANCY",
                    rule_title="Quantity Discrepancy Exceeds 5%",
                    detail=(
                        f"Quoted quantity ({quoted_qty:g} {item.unit}) differs from requested "
                        f"quantity ({requested_qty:g} {pr_item.unit}) by {qty_deviation_pct:.2f}% "
                        f"(variance exceeds 5.0% threshold)."
                    ),
                    exact_citation=f"{quoted_qty:g}",
                )
            )

        return (
            round(price_deviation_pct, 2),
            round(qty_deviation_pct, 2),
            violations,
        )
