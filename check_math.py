from src.pdf_parser import PDFParser
from src.math_verifier import MathVerifier

# Test Pack 01 (Math should be 100% sound)
doc1 = PDFParser.parse_quotation("data/supplier-pack-01.pdf")
res1 = MathVerifier.verify(doc1)
print(f"Pack 01 Math Sound: {res1.is_mathematically_sound} (Expected: True)")

# Test Pack 09 (Math MUST fail because 50,000 * 6.40 = 320,000, but stated 322,000)
doc9 = PDFParser.parse_quotation("data/supplier-pack-09.pdf")
res9 = MathVerifier.verify(doc9)
print(f"Pack 09 Math Sound: {res9.is_mathematically_sound} (Expected: False)")
print("Pack 09 Mismatch detail:", [d for d in res9.details if "mismatch" in d.lower()][0])

assert res1.is_mathematically_sound == True
assert res9.is_mathematically_sound == False
print("\n✅ Brick 3 (math_verifier.py) verified successfully!")