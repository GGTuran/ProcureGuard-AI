import sys
import unittest
from pathlib import Path
from src.models import QuotationDocument, QuotationItem, Verdict
from src.math_verifier import MathVerifier
from src.rules_engine import RulesEngine



# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))




class TestMathAndRuleEdgeCases(unittest.TestCase):
    """Verifies floating-point arithmetic boundaries and policy thresholds."""

    def test_line_total_math_discrepancy(self):
        """Arithmetic mismatch is flagged with exact delta."""
        doc = QuotationDocument(
            source_file="mock.pdf",
            supplier_name="Mock Supplier",
            quotation_no="QT-MOCK",
            date="2026-11-01",
            reference_pr="PR-2026-114",
            items=[
                QuotationItem(
                    item_code="A",
                    description="Cotton fabric",
                    quantity=1000.0,
                    unit="metre",
                    unit_price=10.0,
                    amount=12000.0,  # 12,000 instead of 10,000
                )
            ],
            subtotal=12000.0,
            vat_amount=1800.0,
            total=13800.0,
        )

        math_res = MathVerifier.verify(doc)
        self.assertFalse(math_res.is_mathematically_sound)
        self.assertFalse(math_res.line_total_correct)
        self.assertEqual(math_res.line_total_difference, 2000.0)


    def test_vat_mismatch_flagged(self):
        """VAT calculation differing from 15% of subtotal is flagged."""
        doc = QuotationDocument(
            source_file="mock.pdf",
            supplier_name="Mock Supplier",
            quotation_no="QT-MOCK",
            date="2026-11-01",
            reference_pr="PR-2026-114",
            items=[
                QuotationItem(
                    item_code="A",
                    description="Cotton fabric",
                    quantity=100.0,
                    unit="metre",
                    unit_price=10.0,
                    amount=1000.0,
                )
            ],
            subtotal=1000.0,
            vat_amount=100.0,  # 10% instead of 15% (150)
            total=1100.0,
        )

        math_res = MathVerifier.verify(doc)
        self.assertFalse(math_res.is_mathematically_sound)
        self.assertFalse(math_res.vat_correct)

    def test_advance_boundary_condition(self):
        doc_20 = QuotationDocument(
            source_file="mock.pdf",
            supplier_name="Mock Supplier",
            quotation_no="QT-MOCK",
            date="2026-11-01",
            reference_pr="PR-2026-114",
            advance_percent=20.0,
            has_tin_or_bin=True,
            has_late_penalty_clause=True,
            late_penalty_percent_per_week=1.0,
            delivery_days=20,
            payment_terms_days=30,
            validity_days=30,
            items=[
                QuotationItem(
                    item_code="A",
                    description="Cotton fabric",
                    quantity=100.0,
                    unit="metre",
                    unit_price=10.0,
                    amount=1000.0,
                )
            ],
            subtotal=1000.0,
            vat_percent=15.0,
            vat_amount=150.0,
            total=1150.0,
        )

        math_20 = MathVerifier.verify(doc_20)
        res_20 = RulesEngine.evaluate(doc_20, math_20, [], 0.0, 0.0)
        self.assertEqual(res_20.verdict, Verdict.APPROVE)

        # more than 20% advance will be rejected
        doc_21 = doc_20.model_copy(update={'advance_percent': 21.0})
        res_21 = RulesEngine.evaluate(doc_21, math_20, [], 0.0, 0.0)
        self.assertEqual(res_21.verdict, Verdict.REJECT)
        self.assertTrue(any(v.rule_id == "REJECT_2_ADVANCE_EXCESS" for v in res_21.violations))



if __name__ == "__main__":
    unittest.main()