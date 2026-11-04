from __future__ import annotations
import os
import sys
from pathlib import Path


# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.audit_pipeline import ProcurementAuditor
from src.models import Verdict

EXPECTED_GROUND_TRUTH = {
    "supplier-pack-01.pdf": Verdict.APPROVE,
    "supplier-pack-02.pdf": Verdict.APPROVE,
    "supplier-pack-03.pdf": Verdict.REJECT,
    "supplier-pack-04.pdf": Verdict.NEEDS_REVIEW,
    "supplier-pack-05.pdf": Verdict.REJECT,
    "supplier-pack-06.pdf": Verdict.REJECT,
    "supplier-pack-07.pdf": Verdict.NEEDS_REVIEW,
    "supplier-pack-08.pdf": Verdict.REJECT,
    "supplier-pack-09.pdf": Verdict.NEEDS_REVIEW,
    "supplier-pack-10.pdf": Verdict.REJECT,
}


def main() -> None:
    data_dir = ROOT_DIR / "data"
    pr_csv = data_dir / "purchase-request.csv"
    rules_md = data_dir / "company-rules.md"

    
    print(" ProcureGuard AI: Zero-Hallucination LangGraph Compliance Pipeline")
    

    if not pr_csv.exists() or not rules_md.exists():
        print(f"Error: Missing reference files in {data_dir}")
        sys.exit(1)

    auditor = ProcurementAuditor(pr_csv_path=str(pr_csv), rules_path=str(rules_md))
    results = auditor.audit_all_packs(data_dir=str(data_dir))

    correct_count = 0
    total_count = len(results)

    
    print(
        f"{'Pack':<22} | {'Supplier':<26} | {'Item':<4} | {'Actual Verdict':<23} | {'Expected Verdict':<23} | {'Status'}"
    )
    

    for r in results:
        fname = os.path.basename(r.source_file)
        expected = EXPECTED_GROUND_TRUTH.get(fname)
        is_match = r.verdict == expected
        if is_match:
            correct_count += 1
            status_str = "[PASS]"
        else:
            status_str = "[FAIL]"

        print(
            f"{fname:<22} | {r.supplier_name[:26]:<26} | {r.item_code:<4} | "
            f"{r.verdict.value:<23} | {expected.value if expected else 'N/A':<23} | {status_str}"
        )

    accuracy = (correct_count / total_count) * 100.0 if total_count else 0.0
    
    print(f"\nFinal Audit Score: {correct_count} / {total_count} ({accuracy:.1f}% Verified Accuracy)")

    # Save Markdown report
    md_report = auditor.generate_markdown_report(results)
    report_file = ROOT_DIR / "audit_report.md"
    report_file.write_text(md_report, encoding="utf-8")
    print(f"Executive report saved to : {report_file}")

    # Save CSV
    df = auditor.to_dataframe(results)
    csv_file = ROOT_DIR / "audit_results.csv"
    df.to_csv(csv_file, index=False)
    print(f"Tabular results saved to   : {csv_file}\n")


if __name__ == "__main__":
    main()