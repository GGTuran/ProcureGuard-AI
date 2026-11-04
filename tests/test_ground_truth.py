import os
import sys
import unittest
from pathlib import Path
from src.audit_pipeline import ProcurementAuditor
from src.models import Verdict


# Add project root to sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))



class TestGroundTruthSamplePacks(unittest.TestCase):
    """Verifies that all 10 sample files match the expected business decisions."""
    @classmethod
    def setUpClass(cls):
        cls.root_dir = Path(__file__).resolve().parent.parent
        cls.data_dir = cls.root_dir / "data"
        cls.pr_csv = str(cls.data_dir / "purchase-request.csv")
        cls.rules_md = str(cls.data_dir / "company-rules.md")
        cls.auditor = ProcurementAuditor(pr_csv_path=cls.pr_csv, rules_path=cls.rules_md)


    def test_pack_01_approve(self):
        """Pack 01: Fully compliant Cotton twill quote -> APPROVE."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-01.pdf"))
        self.assertEqual(res.verdict, Verdict.APPROVE)
        self.assertEqual(res.item_code, "A")
        self.assertEqual(res.supplier_name, "Padma Textile Mills Ltd")
        self.assertTrue(res.math_check.is_mathematically_sound)
        self.assertEqual(len(res.violations), 0)


    def test_pack_02_approve(self):
        """Pack 02: Fully compliant Metal zipper quote with 0% advance -> APPROVE."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-02.pdf"))
        self.assertEqual(res.verdict, Verdict.APPROVE)
        self.assertEqual(res.item_code, "B")
        self.assertEqual(res.supplier_name, "Jamuna Trims and Accessories")
        self.assertTrue(res.math_check.is_mathematically_sound)
        self.assertEqual(len(res.violations), 0)


    def test_pack_03_reject_price_excess(self):
        """Pack 03: Unit price BDT 229 vs Max BDT 210 (+9.05% > 3%) -> REJECT."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-03.pdf"))
        self.assertEqual(res.verdict, Verdict.REJECT)
        self.assertEqual(res.item_code, "C")
        self.assertGreater(res.price_deviation_percent, 3.0)
        self.assertTrue(any(v.rule_id == "REJECT_1_PRICE_EXCESS" for v in res.violations))


    def test_pack_04_needs_person_price_tolerance(self):
        """Pack 04: Unit price BDT 6.65 vs Max BDT 6.50 (+2.31% <= 3%) -> NEEDS PERSON."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-04.pdf"))
        self.assertEqual(res.verdict, Verdict.NEEDS_REVIEW)
        self.assertEqual(res.item_code, "D")
        self.assertTrue(0.0 < res.price_deviation_percent <= 3.0)
        self.assertTrue(any(v.rule_id == "NEEDS_PERSON_1_PRICE_MARGINAL" for v in res.violations))


    def test_pack_05_reject_advance_excess(self):
        """Pack 05: Advance payment requested is 40% (> 20% limit) -> REJECT."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-05.pdf"))
        self.assertEqual(res.verdict, Verdict.REJECT)
        self.assertEqual(res.item_code, "E")
        self.assertTrue(any(v.rule_id == "REJECT_2_ADVANCE_EXCESS" for v in res.violations))


    def test_pack_06_reject_missing_penalty(self):
        """Pack 06: Missing late delivery penalty clause entirely -> REJECT."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-06.pdf"))
        self.assertEqual(res.verdict, Verdict.REJECT)
        self.assertEqual(res.item_code, "A")
        self.assertTrue(any(v.rule_id == "REJECT_3_PENALTY_MISSING" for v in res.violations))


    def test_pack_07_needs_person_quantity_discrepancy(self):
        """Pack 07: Quoted quantity 16,500 vs requested 20,000 (17.5% diff > 5%) -> NEEDS PERSON."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-07.pdf"))
        self.assertEqual(res.verdict, Verdict.NEEDS_REVIEW)
        self.assertEqual(res.item_code, "B")
        self.assertGreater(res.quantity_deviation_percent, 5.0)
        self.assertTrue(any(v.rule_id == "NEEDS_PERSON_2_QTY_DISCREPANCY" for v in res.violations))


    def test_pack_08_reject_tin_bin_missing(self):
        """Pack 08: Supplier TIN & BIN missing -> REJECT."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-08.pdf"))
        self.assertEqual(res.verdict, Verdict.REJECT)
        self.assertEqual(res.item_code, "C")
        self.assertTrue(any(v.rule_id == "REJECT_4_TIN_BIN_MISSING" for v in res.violations))


    def test_pack_09_needs_person_math_and_payment_terms(self):
        """Pack 09: Line total mismatch (322k vs 320k) and payment 30-90 days -> NEEDS PERSON."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-09.pdf"))
        self.assertEqual(res.verdict, Verdict.NEEDS_REVIEW)
        self.assertEqual(res.item_code, "D")
        self.assertFalse(res.math_check.is_mathematically_sound)
        self.assertTrue(any(v.rule_id == "NEEDS_PERSON_6_MATH_ERROR" for v in res.violations))


    def test_pack_10_reject_delivery_excess(self):
        """Pack 10: Promised delivery in 60 days (> 45 days limit) -> REJECT."""
        res = self.auditor.audit_document(str(self.data_dir / "supplier-pack-10.pdf"))
        self.assertEqual(res.verdict, Verdict.REJECT)
        self.assertEqual(res.item_code, "E")
        self.assertTrue(any(v.rule_id == "REJECT_5_DELIVERY_EXCESS" for v in res.violations))

        
if __name__ == "__main__":
    unittest.main()
