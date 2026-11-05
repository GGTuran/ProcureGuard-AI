"""
generate_test_cases.py
======================
Generates 3 synthetic, ReportLab-compatible supplier quotation PDFs:
  1. data/supplier-pack-11-approve.pdf  -> APPROVE
  2. data/supplier-pack-12-reject.pdf   -> REJECT (Price +6.15% > 3%)
  3. data/supplier-pack-13-hitl.pdf     -> NEEDS_REVIEW (Price +2.11% <= 3%)
"""

import base64
import zlib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def build_pdf_bytes(
    supplier: str,
    q_no: str,
    date: str,
    pr: str,
    item: str,
    desc: str,
    qty_str: str,
    unit: str,
    price_str: str,
    amt_str: str,
    subtotal_str: str,
    vat_str: str,
    total_str: str,
    tin_bin: str,
    pay_text: str,
    del_text: str,
    delay_text: str,
    val_text: str,
) -> bytes:
    stream_content = f"""1 0 0 1 0 0 cm  BT /F1 12 Tf 14.4 TL ET
q
1 0 0 1 57.02 768.53 cm
q
0 0 0 rg
BT 1 0 0 1 0 4 Tm /F2 18 Tf 22 TL ({supplier}) Tj T* ET
Q
Q
q
1 0 0 1 57.02 738.53 cm
q
0 0 0 rg
BT 1 0 0 1 0 4 Tm /F2 14 Tf 18 TL (QUOTATION) Tj T* ET
Q
Q
q
1 0 0 1 70.86 698.53 cm
q
BT /F1 9 Tf 12 TL ET
BT 1 0 0 1 6 24 Tm (Quotation no.) Tj T* ET
BT 1 0 0 1 91.03 24 Tm ({q_no}) Tj T* ET
BT 1 0 0 1 261.11 24 Tm (Date) Tj T* ET
BT 1 0 0 1 331.98 24 Tm ({date}) Tj T* ET
BT 1 0 0 1 6 6 Tm (To) Tj T* ET
BT 1 0 0 1 91.03 6 Tm (Aamar Garments Ltd) Tj T* ET
BT 1 0 0 1 261.11 6 Tm (Reference) Tj T* ET
BT 1 0 0 1 331.98 6 Tm ({pr}) Tj T* ET
Q
Q
q
1 0 0 1 51.02 594.36 cm
q
BT /F1 8.5 Tf 12 TL ET
BT 1 0 0 1 6 78.5 Tm (Item) Tj T* ET
BT 1 0 0 1 40.01 78.5 Tm (Description) Tj T* ET
BT 1 0 0 1 187.41 78.5 Tm (Qty) Tj T* ET
BT 1 0 0 1 244.11 78.5 Tm (Unit) Tj T* ET
BT 1 0 0 1 289.46 78.5 Tm (Unit price \\(BDT\\)) Tj T* ET
BT 1 0 0 1 408.51 78.5 Tm (Amount \\(BDT\\)) Tj T* ET
BT 1 0 0 1 6 60.5 Tm ({item}) Tj T* ET
BT 1 0 0 1 40.01 60.5 Tm ({desc}) Tj T* ET
BT 1 0 0 1 206.11 60.5 Tm ({qty_str}) Tj T* ET
BT 1 0 0 1 255.73 60.5 Tm ({unit}) Tj T* ET
BT 1 0 0 1 370.52 60.5 Tm ({price_str}) Tj T* ET
BT 1 0 0 1 437.60 60.5 Tm ({amt_str}) Tj T* ET
BT 1 0 0 1 365.33 42.5 Tm (Subtotal) Tj T* ET
BT 1 0 0 1 437.60 42.5 Tm ({subtotal_str}) Tj T* ET
BT 1 0 0 1 360.61 24.5 Tm (VAT 15%) Tj T* ET
BT 1 0 0 1 444.69 24.5 Tm ({vat_str}) Tj T* ET
BT 1 0 0 1 377.62 6.5 Tm (Total) Tj T* ET
BT 1 0 0 1 437.60 6.5 Tm ({total_str}) Tj T* ET
Q
Q
q
1 0 0 1 57.02 566.02 cm
q
BT 1 0 0 1 0 2.5 Tm /F1 8.5 Tf 11 TL ({tin_bin}) Tj T* ET
Q
Q
q
1 0 0 1 57.02 519.01 cm
q
BT 1 0 0 1 0 4 Tm /F2 14 Tf 18 TL (TERMS AND CONDITIONS) Tj T* ET
Q
Q
q
1 0 0 1 57.02 487.01 cm
q
BT 1 0 0 1 0 16.5 Tm 13 TL /F2 9.5 Tf (1. Payment.) Tj /F1 9.5 Tf ({pay_text}) Tj T* ET
Q
Q
q
1 0 0 1 57.02 462.34 cm
q
BT 1 0 0 1 0 3.5 Tm 13 TL /F2 9.5 Tf (2. Delivery.) Tj /F1 9.5 Tf ({del_text}) Tj T* ET
Q
Q
q
1 0 0 1 57.02 437.67 cm
q
BT 1 0 0 1 0 3.5 Tm 13 TL /F2 9.5 Tf (3. Delay.) Tj /F1 9.5 Tf ({delay_text}) Tj T* ET
Q
Q
q
1 0 0 1 57.02 413.00 cm
q
BT 1 0 0 1 0 3.5 Tm 13 TL /F2 9.5 Tf (4. Validity.) Tj /F1 9.5 Tf ({val_text}) Tj T* ET
Q
Q
"""
    compressed = zlib.compress(stream_content.encode("latin-1"))
    a85 = base64.a85encode(compressed, adobe=True)[2:-2]
    length = len(a85)
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [ 0 0 595.27 841.89 ] /Contents 6 0 R /Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>\nendobj\n"
        b"6 0 obj\n<< /Length " + str(length).encode() + b" /Filter [/ASCII85Decode /FlateDecode] >>\nstream\n"
        + a85
        + b"\nendstream\nendobj\nxref\n0 7\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000266 00000 n \n0000000343 00000 n \n0000000425 00000 n \ntrailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n800\n%%EOF\n"
    )


def main():
    print("Generating 3 new supplier quotation test packs...")

    # APPROVE CASE
    pdf_approve = build_pdf_bytes(
        supplier="Meghna Fabric Mills Ltd",
        q_no="QT-2026-911",
        date="2026-10-25",
        pr="PR-2026-114",
        item="A",
        desc="Cotton twill fabric, 280 gsm",
        qty_str="12,000",
        unit="metre",
        price_str="465.00",
        amt_str="5,580,000.00",
        subtotal_str="5,580,000.00",
        vat_str="837,000.00",
        total_str="6,417,000.00",
        tin_bin="Supplier TIN: 108492019481 BIN: 000192847-0101",
        pay_text=" 15% advance payable with purchase order. Balance within 45 days after delivery.",
        del_text=" Delivery within 25 days of purchase order.",
        delay_text=" Late delivery penalty: 0.75% of order value per week of delay.",
        val_text=" This quotation is valid for 45 days.",
    )
    (DATA_DIR / "supplier-pack-11-approve.pdf").write_bytes(pdf_approve)
    print("-> Generated: data/supplier-pack-11-approve.pdf (Expected: APPROVE)")

    #  REJECT CASE (Price +6.15% > 3%)
    pdf_reject = build_pdf_bytes(
        supplier="Karnafuli Packaging Ltd",
        q_no="QT-2026-912",
        date="2026-10-25",
        pr="PR-2026-114",
        item="D",
        desc="Poly bag, 30 x 40 cm",
        qty_str="50,000",
        unit="piece",
        price_str="6.90",
        amt_str="345,000.00",
        subtotal_str="345,000.00",
        vat_str="51,750.00",
        total_str="396,750.00",
        tin_bin="Supplier TIN: 109283746182 BIN: 000283746-0101",
        pay_text=" 10% advance payable with purchase order. Balance within 30 days after delivery.",
        del_text=" Delivery within 20 days of purchase order.",
        delay_text=" Late delivery penalty: 0.5% of order value per week of delay.",
        val_text=" This quotation is valid for 35 days.",
    )
    (DATA_DIR / "supplier-pack-12-reject.pdf").write_bytes(pdf_reject)
    print("-> Generated: data/supplier-pack-12-reject.pdf (Expected: REJECT)")

    # NEEDS_REVIEW CASE (Price +2.11% <= 3%)
    pdf_hitl = build_pdf_bytes(
        supplier="Shitalakshya Accessories Ltd",
        q_no="QT-2026-913",
        date="2026-10-25",
        pr="PR-2026-114",
        item="B",
        desc="Metal zipper, 18 cm",
        qty_str="20,000",
        unit="piece",
        price_str="38.80",
        amt_str="776,000.00",
        subtotal_str="776,000.00",
        vat_str="116,400.00",
        total_str="892,400.00",
        tin_bin="Supplier TIN: 102938475612 BIN: 000394857-0101",
        pay_text=" 10% advance payable with purchase order. Balance within 45 days after delivery.",
        del_text=" Delivery within 25 days of purchase order.",
        delay_text=" Late delivery penalty: 0.5% of order value per week of delay.",
        val_text=" This quotation is valid for 30 days.",
    )
    (DATA_DIR / "supplier-pack-13-hitl.pdf").write_bytes(pdf_hitl)
    print("-> Generated: data/supplier-pack-13-hitl.pdf (Expected: NEEDS A PERSON TO CHECK)")

    print("\nVerifying newly generated packs against ProcureGuard AI pipeline...")
    from src.audit_pipeline import ProcurementAuditor

    auditor = ProcurementAuditor(str(DATA_DIR / "purchase-request.csv"), str(DATA_DIR / "company-rules.md"))
    for f in ["supplier-pack-11-approve.pdf", "supplier-pack-12-reject.pdf", "supplier-pack-13-hitl.pdf"]:
        res = auditor.audit_document(str(DATA_DIR / f))
        print(f"[{res.verdict.value.upper():<23}] {f:<30} | {res.primary_reason[:65]}")


if __name__ == "__main__":
    main()