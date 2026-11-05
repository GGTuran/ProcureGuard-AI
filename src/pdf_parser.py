from __future__ import annotations
import os
import re
import zlib
from pathlib import Path
from typing import List

from src.models import QuotationDocument, QuotationItem


#  Internal helpers
_ITEM_CODES: set[str] = set("ABCDE")

# Monetary string like "5,664,000.00" or "92.00" → float
def _parse_money(value: str) -> float:
    """Strip thousands separators and convert to float; return 0.0 on error."""
    try:
        return float(value.replace(",", "").strip())
    except (ValueError, AttributeError):
        return 0.0


def _unescape_pdf(token: str) -> str:
    """Unescape PDF string-literal escape sequences."""
    token = token.replace(r"\(", "(").replace(r"\)", ")").replace(r"\\", "\\")
    return token


class PDFParser:
    """
    Stateless parser for the ReportLab-generated supplier quotation PDFs used
    by ProcureGuard AI.  All public methods are class-methods so callers never
    need to instantiate the class.
    """

    # Low-level stream decompression

    @classmethod
    def _ascii85_decode(cls, data: bytes) -> bytes:
        """
        Decode an ASCII85-encoded byte string (Adobe variant).

        The encoder appends the ``~>`` end-of-data marker; whitespace inside
        the encoded body is silently ignored.  The special 'z' character
        expands to four zero bytes without consuming a full 5-byte group.
        Partial groups at the end are handled with right-padding of 'u' (84).
        """
        # Strip the end-of-data marker if present
        stripped = data
        if stripped.endswith(b"~>"):
            stripped = stripped[:-2]

        result: bytearray = bytearray()
        group: list[int] = []

        for byte in stripped:
            # Skip all whitespace (space, tab, CR, LF)
            if byte in (0x20, 0x09, 0x0D, 0x0A):
                continue

            ch = chr(byte)
            if ch == "z":
                # 'z' is a shorthand for five '!' characters (all-zero group)
                if group:
                    raise ValueError(
                        "ASCII85: 'z' encountered inside a partial group"
                    )
                result.extend(b"\x00\x00\x00\x00")
                continue

            if 33 <= byte <= 117:  # '!' to 'u'
                group.append(byte - 33)
                if len(group) == 5:
                    val = (
                        group[0] * 85 ** 4
                        + group[1] * 85 ** 3
                        + group[2] * 85 ** 2
                        + group[3] * 85
                        + group[4]
                    )
                    result.extend(val.to_bytes(4, "big"))
                    group = []
            # Characters outside the valid range are silently skipped;
            # a stricter decoder would raise here, but the ReportLab encoder
            # occasionally emits CR/LF inside the body which are already
            # handled above.

        # Handle the final partial group (1–4 chars)
        if group:
            n = len(group)
            # Right-pad with 'u' (value 84) to make a full 5-char group
            padded = group + [84] * (5 - n)
            val = (
                padded[0] * 85 ** 4
                + padded[1] * 85 ** 3
                + padded[2] * 85 ** 2
                + padded[3] * 85
                + padded[4]
            )
            # The final group yields n-1 bytes
            for i in range(n - 1):
                result.append((val >> (24 - 8 * i)) & 0xFF)

        return bytes(result)

    @classmethod
    def extract_tokens_from_stream(cls, pdf_path: str) -> List[str]:
        """
        Decompress the single content stream from a ReportLab PDF and return
        a list of cleaned PDF string-literal tokens.

        Processing pipeline
        -------------------
        1. Read raw bytes.
        2. Locate the ``stream`` / ``endstream`` block.
        3. ASCII85-decode the compressed body.
        4. zlib-decompress the resulting bytes.
        5. Extract all ``(…)`` string literals, unescaping ``\\(``, ``\\)``,
           and ``\\\\``.
        6. Strip surrounding whitespace and drop empty strings.

        Parameters
        ----------
        pdf_path:
            Absolute or relative path to the PDF file.

        Returns
        -------
        List[str]
            Ordered list of non-empty string tokens from the PDF content stream.

        Raises
        ------
        FileNotFoundError
            When *pdf_path* does not point to an existing file.
        ValueError
            When no ``stream``/``endstream`` block is found, or decompression
            fails irrecoverably.
        """
        path = Path(pdf_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"PDFParser: file not found: {pdf_path!r}"
            )

        raw: bytes = path.read_bytes()

        # Locate the stream body (ReportLab emits exactly one content stream)
        stream_start = raw.find(b"stream")
        endstream_start = raw.find(b"endstream")
        if stream_start == -1 or endstream_start == -1:
            raise ValueError(
                f"PDFParser: no stream/endstream found in {pdf_path!r}"
            )

        # Skip past 'stream' and the mandatory newline (LF or CRLF)
        body_start = stream_start + len(b"stream")
        if raw[body_start : body_start + 2] == b"\r\n":
            body_start += 2
        elif raw[body_start] in (0x0A, 0x0D):
            body_start += 1

        compressed_body: bytes = raw[body_start:endstream_start]

        # Decode ASCII85 → zlib-compressed bytes → raw PDF operator stream
        try:
            deflated = cls._ascii85_decode(compressed_body)
        except Exception as exc:
            raise ValueError(
                f"PDFParser: ASCII85 decode failed for {pdf_path!r}: {exc}"
            ) from exc

        try:
            stream_text: str = zlib.decompress(deflated).decode("latin-1")
        except zlib.error as exc:
            raise ValueError(
                f"PDFParser: zlib decompress failed for {pdf_path!r}: {exc}"
            ) from exc

        # Extract all PDF string literals: content between unescaped ( and )
        # The regex handles escaped parens (\( \)) and escaped backslashes (\\)
        raw_literals: List[str] = re.findall(
            r"\((?:[^\\()]|\\.)*\)", stream_text
        )

        tokens: List[str] = []
        for lit in raw_literals:
            # Strip the outer parentheses
            inner = lit[1:-1]
            # Unescape PDF escape sequences
            inner = _unescape_pdf(inner)
            # Normalise whitespace and drop empties
            inner = inner.strip()
            if inner:
                tokens.append(inner)

        return tokens

    # Document Header & Identification Parsing

    @classmethod
    def _parse_header(
        cls,
        tokens: List[str],
        full_text: str,
    ) -> dict:
        """
        Extract top-level document identifiers from the token stream.

        Returns a dict with keys:
            supplier_name, quotation_no, date, reference_pr,
            tin, bin, has_tin_or_bin
        """
        result: dict = {
            "supplier_name": "",
            "quotation_no": "",
            "date": "",
            "reference_pr": "",
            "tin": "",
            "bin": "",
            "has_tin_or_bin": False,
        }

        #  Supplier name: first substantial token before 'QUOTATION' 
        for i, tok in enumerate(tokens):
            if tok.upper() == "QUOTATION":
                if i > 0:
                    result["supplier_name"] = tokens[i - 1]
                break

        # Quotation number
        m = re.search(r"QT-\d{4}-\d+", full_text)
        if m:
            result["quotation_no"] = m.group(0)

        # Date (ISO-8601)
        m = re.search(r"\d{4}-\d{2}-\d{2}", full_text)
        if m:
            result["date"] = m.group(0)

        # Reference PR 
        m = re.search(r"PR-\d{4}-\d+", full_text)
        if m:
            result["reference_pr"] = m.group(0)

        # Tax IDs 
        # TIN and BIN often appear in a single token, e.g.
        # "Supplier TIN: 101458013391 BIN: 000170141-0101"
        tin_m = re.search(r"TIN:\s*(\d+)", full_text, re.IGNORECASE)
        if tin_m:
            result["tin"] = tin_m.group(1)

        bin_m = re.search(r"BIN:\s*([\d\-]+)", full_text, re.IGNORECASE)
        if bin_m:
            result["bin"] = bin_m.group(1)

        result["has_tin_or_bin"] = bool(result["tin"] or result["bin"])

        return result

    #  Line Items & Financial Matrix Extraction

    @classmethod
    def _parse_items_and_financials(
        cls,
        tokens: List[str],
    ) -> dict:
        """
        Locate the column-header row and extract line items + summary rows.

        Returns a dict with keys:
            items, subtotal, vat_percent, vat_amount, total, is_vat_inclusive
        """
        result: dict = {
            "items": [],
            "subtotal": 0.0,
            "vat_percent": 0.0,
            "vat_amount": 0.0,
            "total": 0.0,
            "is_vat_inclusive": False,
        }

        # Detect VAT-inclusive pricing variants
        # e.g. "Unit price (BDT, VAT included)" or "Total (all taxes included)"
        unit_price_col = ""
        total_col = ""
        for tok in tokens:
            tl = tok.lower()
            if "unit price" in tl:
                unit_price_col = tok
            if "total" in tl and "tax" in tl:
                total_col = tok

        if "vat included" in unit_price_col.lower() or "all taxes included" in total_col.lower():
            result["is_vat_inclusive"] = True

        # Find table header boundary: token immediately AFTER "Amount" or
        # "Amount (BDT)" or similar
        amount_col_idx = -1
        for i, tok in enumerate(tokens):
            if re.match(r"Amount", tok, re.IGNORECASE):
                amount_col_idx = i
                break

        if amount_col_idx == -1:
            return result  # No table found; return defaults

        # After the Amount header the tokens follow the pattern:
        # item_code, description, qty, unit, unit_price, amount
        # Rows continue until we hit a summary keyword (Subtotal / Total / VAT)
        # or a non-item-code token.
        i = amount_col_idx + 1
        n = len(tokens)

        while i < n:
            tok = tokens[i].strip()

            #  Summary rows 
            tl = tok.lower()

            if tl == "subtotal":
                if i + 1 < n:
                    result["subtotal"] = _parse_money(tokens[i + 1])
                i += 2
                continue

            # VAT row: "VAT 15%" followed by amount
            vat_m = re.match(r"VAT\s+(\d+(?:\.\d+)?)\s*%", tok, re.IGNORECASE)
            if vat_m:
                result["vat_percent"] = float(vat_m.group(1))
                if i + 1 < n:
                    result["vat_amount"] = _parse_money(tokens[i + 1])
                i += 2
                continue

            # Total row: "Total" or "Total (all taxes included)"
            if re.match(r"Total", tok, re.IGNORECASE):
                if i + 1 < n:
                    result["total"] = _parse_money(tokens[i + 1])
                i += 2
                continue

            #Line item detection
            # Item code is a single uppercase letter A–E
            if tok in _ITEM_CODES:
                # Expect: description (i+1), qty (i+2), unit (i+3),
                #         unit_price (i+4), amount (i+5)
                if i + 5 < n:
                    try:
                        qty = _parse_money(tokens[i + 2])
                        unit_price = _parse_money(tokens[i + 4])
                        amount = _parse_money(tokens[i + 5])

                        item = QuotationItem(
                            item_code=tok,
                            description=tokens[i + 1],
                            quantity=qty,
                            unit=tokens[i + 3],
                            unit_price=unit_price,
                            amount=amount,
                        )
                        result["items"].append(item)
                        i += 6
                        continue
                    except Exception:
                        pass  # fall through to generic advance

            # Skip unrecognised tokens
            i += 1

        return result

    # Contractual Clauses & Guardrail Extraction
    @classmethod
    def _parse_payment_clause(cls, full_text: str) -> dict:
        """
        Extract advance payment percentage, credit window, and flag whether
        payment terms are unclear or out of policy range (30–60 days).

        Returns a dict with keys:
            advance_percent, payment_terms_days, payment_terms_max_days,
            payment_terms_text, is_payment_terms_unclear_or_out_of_range
        """
        result: dict = {
            "advance_percent": 0.0,
            "payment_terms_days": 0,
            "payment_terms_max_days": 30,
            "payment_terms_text": "",
            "is_payment_terms_unclear_or_out_of_range": False,
        }

        # Locate the payment clause block
        pay_m = re.search(
            r"1\.\s*Payment\.\s*(.+?)(?=2\.\s*Delivery\.|$)",
            full_text,
            re.IGNORECASE | re.DOTALL,
        )
        if not pay_m:
            # Try looser match for any payment mention
            pay_m = re.search(
                r"Payment[.\s]+(.+?)(?=Delivery|$)",
                full_text,
                re.IGNORECASE | re.DOTALL,
            )

        if pay_m:
            clause = pay_m.group(1).strip()
            result["payment_terms_text"] = clause

            # --- Advance percentage ------------------------------------------
            # "no advance" → 0%
            if re.search(r"no\s+advance", clause, re.IGNORECASE):
                result["advance_percent"] = 0.0
            else:
                # "10% advance", "40% advance", "15% advance payable …"
                adv_m = re.search(
                    r"(\d+(?:\.\d+)?)\s*%\s+advance", clause, re.IGNORECASE
                )
                if adv_m:
                    result["advance_percent"] = float(adv_m.group(1))

            # --- Credit window -----------------------------------------------
            # Range: "within 30 to 90 days" → flag as unclear
            range_m = re.search(
                r"within\s+(\d+)\s+to\s+(\d+)\s+days?",
                clause,
                re.IGNORECASE,
            )
            if range_m:
                lo = int(range_m.group(1))
                hi = int(range_m.group(2))
                result["payment_terms_days"] = lo
                result["payment_terms_max_days"] = hi
                # Flag if range spans outside [30, 60]
                if lo < 30 or hi > 60:
                    result["is_payment_terms_unclear_or_out_of_range"] = True
            else:
                # Single value: "within 45 days", "within 30 days after delivery"
                single_m = re.search(
                    r"within\s+(\d+)\s+days?", clause, re.IGNORECASE
                )
                if single_m:
                    days = int(single_m.group(1))
                    result["payment_terms_days"] = days
                    result["payment_terms_max_days"] = days
                    # Outside [30, 60] means a reviewer is needed
                    if days < 30 or days > 60:
                        result["is_payment_terms_unclear_or_out_of_range"] = True
                else:
                    # Could not parse a numeric window → unclear
                    result["is_payment_terms_unclear_or_out_of_range"] = True

        return result

    @classmethod
    def _parse_delivery_clause(cls, full_text: str) -> dict:
        """
        Extract promised delivery lead-time in days.
        Converts week-based promises (e.g. "4 weeks") to days automatically.

        Returns a dict with keys:
            delivery_days, delivery_text
        """
        result: dict = {"delivery_days": 0, "delivery_text": ""}

        # Locate the delivery clause (clause 2)
        del_m = re.search(
            r"2\.\s*Delivery\.\s*(.+?)(?=3\.\s*(?:Delay|Validity)|$)",
            full_text,
            re.IGNORECASE | re.DOTALL,
        )
        if not del_m:
            del_m = re.search(
                r"Delivery\.\s*(.+?)(?=Delay|Validity|$)",
                full_text,
                re.IGNORECASE | re.DOTALL,
            )

        if del_m:
            clause = del_m.group(1).strip()
            result["delivery_text"] = clause

            # Weeks → days conversion
            weeks_m = re.search(
                r"within\s+(\d+)\s+weeks?", clause, re.IGNORECASE
            )
            if weeks_m:
                result["delivery_days"] = int(weeks_m.group(1)) * 7
            else:
                # Days expressed directly
                days_m = re.search(
                    r"within\s+(\d+)\s+days?", clause, re.IGNORECASE
                )
                if days_m:
                    result["delivery_days"] = int(days_m.group(1))

        return result

    @classmethod
    def _parse_penalty_clause(cls, full_text: str) -> dict:
        """
        Extract late-delivery penalty information.

        Detects whether the clause is present and extracts the weekly rate.
        If the "Delay" or "penalty" section is entirely absent the flag
        ``has_late_penalty_clause`` is set to False.

        Returns a dict with keys:
            has_late_penalty_clause, late_penalty_percent_per_week,
            late_penalty_text
        """
        result: dict = {
            "has_late_penalty_clause": False,
            "late_penalty_percent_per_week": 0.0,
            "late_penalty_text": "",
        }

        # Try to locate a "Delay" / "penalty" clause block
        delay_m = re.search(
            r"(?:3\.\s*Delay\.|penalty)",
            full_text,
            re.IGNORECASE,
        )
        if not delay_m:
            # No delay section exists at all
            return result

        # Extract the clause text around the match
        start = delay_m.start()
        end_m = re.search(
            r"(?:\d+\.\s*(?:Validity|Quality|Payment|Delivery)\.)",
            full_text[start:],
            re.IGNORECASE,
        )
        clause_end = start + end_m.start() if end_m else start + 300
        clause = full_text[start:clause_end].strip()
        result["late_penalty_text"] = clause

        # Extract the weekly rate percentage
        # Supports:
        #   "1% of order value for each full week of delay"
        #   "0.5% of order value per week"
        #   "0.75% of the order value per week of delay"
        #   "0.5% per week of delay"
        #   "0.6% of order value per week"
        #   "Delay in delivery will attract a penalty of 0.5% of order value per week"
        rate_m = re.search(
            r"(\d+(?:\.\d+)?)\s*%"
            r"(?:\s+of\s+(?:the\s+)?order\s+value)?"
            r"(?:\s+(?:for\s+each\s+full\s+week|per\s+week)"
            r"|\s+(?:of\s+order\s+value\s+)?per\s+week)",
            clause,
            re.IGNORECASE,
        )
        if rate_m:
            result["has_late_penalty_clause"] = True
            result["late_penalty_percent_per_week"] = float(rate_m.group(1))

        return result

    @classmethod
    def _parse_validity_clause(cls, full_text: str) -> dict:
        """
        Extract quotation validity period in days.

        Strategy: search for a "valid for N days" pattern anywhere in the
        text (no need to isolate the clause block first, since validity is
        always phrased as "valid for <N> days" in these documents).

        Returns a dict with keys:
            validity_days, validity_text
        """
        result: dict = {"validity_days": 0, "validity_text": ""}

        # Locate the validity clause block for audit-trail text
        val_block_m = re.search(
            r"(?:\d+\.\s*Validity\.)\s*(.+?)(?=\d+\.\s*(?:Quality|Disputes)|For\s|$)",
            full_text,
            re.IGNORECASE | re.DOTALL,
        )
        if val_block_m:
            result["validity_text"] = val_block_m.group(0).strip()

        # Extract the numeric value from the full text (more robust)
        days_m = re.search(
            r"valid\s+for\s+(\d+)\s+days?", full_text, re.IGNORECASE
        )
        if days_m:
            result["validity_days"] = int(days_m.group(1))
            if not result["validity_text"]:
                # Fallback: capture surrounding sentence
                start = max(0, days_m.start() - 20)
                result["validity_text"] = full_text[start : days_m.end() + 30].strip()

        return result

    #  Public Interface

    @classmethod
    def parse_quotation(cls, pdf_path: str) -> QuotationDocument:
        """
        Parse a supplier quotation PDF and return a fully populated
        :class:`~src.models.QuotationDocument`.

        This is the single public entry-point for downstream pipeline nodes
        (``pdf_parser`` LangGraph node, ``audit_pipeline``, unit tests).

        Parameters
        ----------
        pdf_path:
            Absolute or relative path to the supplier PDF.

        Returns
        -------
        QuotationDocument
            Fully populated domain model; ``raw_text`` contains the
            space-joined token stream for RAG and citation grounding.

        Raises
        ------
        FileNotFoundError
            When *pdf_path* does not exist.
        ValueError
            When the PDF stream cannot be decoded or decompressed.
        """
        tokens: List[str] = cls.extract_tokens_from_stream(pdf_path)

        # Preserve the full raw text as a single string for downstream RAG
        raw_text: str = "\n".join(tokens)

        #  Section parsers 
        header = cls._parse_header(tokens, raw_text)
        financials = cls._parse_items_and_financials(tokens)
        payment = cls._parse_payment_clause(raw_text)
        delivery = cls._parse_delivery_clause(raw_text)
        penalty = cls._parse_penalty_clause(raw_text)
        validity = cls._parse_validity_clause(raw_text)

        # Assemble QuotationDocument 
        return QuotationDocument(
            # Provenance
            source_file=os.path.basename(pdf_path),
            supplier_name=header["supplier_name"],
            quotation_no=header["quotation_no"],
            date=header["date"],
            reference_pr=header["reference_pr"],
            # Line items & financials
            items=financials["items"],
            subtotal=financials["subtotal"],
            vat_percent=financials["vat_percent"],
            vat_amount=financials["vat_amount"],
            total=financials["total"],
            is_vat_inclusive=financials["is_vat_inclusive"],
            # Tax registration
            tin=header["tin"],
            bin=header["bin"],
            has_tin_or_bin=header["has_tin_or_bin"],
            # Payment terms
            advance_percent=payment["advance_percent"],
            payment_terms_days=payment["payment_terms_days"],
            payment_terms_max_days=payment["payment_terms_max_days"],
            payment_terms_text=payment["payment_terms_text"],
            is_payment_terms_unclear_or_out_of_range=(
                payment["is_payment_terms_unclear_or_out_of_range"]
            ),
            # Delivery
            delivery_days=delivery["delivery_days"],
            delivery_text=delivery["delivery_text"],
            # Late-delivery penalty
            has_late_penalty_clause=penalty["has_late_penalty_clause"],
            late_penalty_percent_per_week=penalty["late_penalty_percent_per_week"],
            late_penalty_text=penalty["late_penalty_text"],
            # Validity
            validity_days=validity["validity_days"],
            validity_text=validity["validity_text"],
            # Full raw text for RAG / citation grounding
            raw_text=raw_text,
        )
