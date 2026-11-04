import glob
from src.pdf_parser import PDFParser

files = sorted(glob.glob("data/supplier-pack-*.pdf"))
print(f"Found {len(files)} PDFs. Parsing...\n")

for f in files:
    doc = PDFParser.parse_quotation(f)
    item = doc.items[0] if doc.items else None
    pen = f"{doc.late_penalty_percent_per_week}%" if doc.has_late_penalty_clause else "MISSING"
    print(f"{doc.source_file}: {doc.supplier_name[:20]:<20} | Item: {item.item_code if item else '-'} | Adv: {doc.advance_percent}% | Del: {doc.delivery_days}d | Pen: {pen:<8} | TIN: {bool(doc.tin)}")

print("\n✅ Brick 2 (pdf_parser.py) parsed all packs successfully!")