from __future__ import annotations
import glob
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd
from src.models import AuditResult, Verdict
from src.workflow import ProcurementAuditWorkflow



class ProcurementAuditor:
    """Compilance verification."""

    def __init__(
        self,
        pr_csv_path: str = "data/purchase-request.csv",
        rules_path: str = "data/company-rules.md",
    ) -> None:
        self.pr_csv = pr_csv_path
        self.rules_path = rules_path
        self.workflow = ProcurementAuditWorkflow(
            pr_csv_path=pr_csv_path,
            rules_path=rules_path
        )

    
    def audit_document(self, pdf_path: str) -> AuditResult:
        """Audit a single supplier quotation document through the pipeline."""
        if not os.path.isfile(pdf_path):
            raise FileNotFoundError(f"Quotation PDF not found at path: {pdf_path}")

        return self.workflow.run(pdf_path)

    def audit_all_packs(self, data_dir: str = "data") -> List[AuditResult]:
        """Discover and audit all reference supplier packs in a directory."""

        if not os.path.isdir(data_dir):
            raise FileNotFoundError(f"Data directory not found: {data_dir}")

        pattern = os.path.join(data_dir, "supplier-pack-*.pdf")
        pdf_files = sorted(glob.glob(pattern))

        if not pdf_files:
            raise FileNotFoundError(
                f"No supplier packs matching pattern 'supplier-pack-*.pdf' found in {data_dir}"
            )

        results: List[AuditResult] = []
        for file_path in pdf_files:
            audit_res = self.audit_document(file_path)
            results.append(audit_res)

        return results

    @staticmethod
    def to_dataframe(results: List[AuditResult]) -> pd.DataFrame:
        """Transform a collection of AuditResult models into a presentation DataFrame."""

        rows: List[Dict[str, Any]] = []
        for r in results:
            rows.append(
                {
                    "File": os.path.basename(r.source_file),
                    "Supplier": r.supplier_name,
                    "Item": r.item_code,
                    "Verdict": r.verdict.value,
                    "Price Dev %": f"{r.price_deviation_percent:+.2f}%",
                    "Qty Dev %": f"{r.quantity_deviation_percent:.1f}%",
                    "Math Sound": "PASS" if r.math_check.is_mathematically_sound else "FAIL",
                    "Violations Count": len(r.violations),
                    "Primary Reason": r.primary_reason,
                    "Primary Citation": r.primary_citation,
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def generate_markdown_report(results: List[AuditResult]) -> str:
        total = len(results)
        approved = sum(1 for r in results if r.verdict == Verdict.APPROVE)
        rejected = sum(1 for r in results if r.verdict == Verdict.REJECT)
        needs_review = sum(1 for r in results if r.verdict == Verdict.NEEDS_REVIEW)
        md: List[str] = [
            "# Aamar Garments Ltd: Supplier Document Compliance Audit",
            "",
            f"**Total Documents Audited:** {total} | "
            f"**Approved:** {approved} | "
            f"**Rejected:** {rejected} | "
            f"**Needs Review (HITL):** {needs_review}",
            "",
            "| Pack | Supplier | Item | Verdict | Math Integrity | Price Delta | Primary Audit Rationale |",
            "|:---:|:---|:---:|:---:|:---:|:---:|:---|",
        ]
        for r in results:
            fname = os.path.basename(r.source_file)
            badge_map = {
                Verdict.APPROVE: "**APPROVE**",
                Verdict.REJECT: "**REJECT**",
                Verdict.NEEDS_REVIEW: "**NEEDS REVIEW**",
            }
            badge = badge_map.get(r.verdict, r.verdict.value)
            math_status = "PASS" if r.math_check.is_mathematically_sound else "MISMATCH"
            p_delta = f"{r.price_deviation_percent:+.2f}%"
            clean_reason = r.primary_reason.replace("\n", " ").strip()
            if len(clean_reason) > 95:
                clean_reason = clean_reason[:92] + "..."
            md.append(
                f"| `{fname}` | {r.supplier_name} | {r.item_code} | {badge} | {math_status} | {p_delta} | {clean_reason} |"
            )
        return "\n".join(md)