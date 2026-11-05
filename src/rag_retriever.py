from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from src.models import RAGRuleChunk


# Stop words and metadata dictionaries for policy grounding

_STOP_WORDS: Set[str] = {
    "is", "are", "the", "a", "an", "in", "on", "at", "for", "to", "of",
    "and", "or", "with", "from", "by", "that", "this", "it", "as", "be",
    "has", "have", "had", "do", "does", "did", "but", "if", "any", "one",
    "these", "your", "our", "all", "not", "we", "they", "them", "their",
}

_RULE_METADATA: Dict[str, Dict[str, list[str] | str]] = {
    "REJECT_1": {
        "title": "Unit Price Exceeds Authorized Cap by > 3%",
        "keywords": [
            "unit price", "price", "maximum", "cap", "ceiling", "3%",
            "above", "excess", "purchase request", "bdt", "expensive",
        ],
        "phrases": [
            "unit price", "more than 3%", "above the maximum",
            "price excess", "exceeds maximum", "exceeds authorized",
        ],
        "aliases": ["REJECT_1_PRICE_EXCESS", "PRICE_CAP_EXCEEDED", "PRICE_REJECT"],
    },
    "REJECT_2": {
        "title": "Advance Payment Exceeds 20%",
        "keywords": [
            "advance", "deposit", "payment", "20%", "down payment",
            "advance payment", "purchase order", "po", "upfront",
        ],
        "phrases": [
            "advance payment", "more than 20%", "advance", "down payment",
            "advance payable", "advance with the purchase order",
        ],
        "aliases": ["REJECT_2_ADVANCE_EXCESS", "ADVANCE_PAYMENT", "EXCESSIVE_ADVANCE"],
    },
    "REJECT_3": {
        "title": "Missing Late-Delivery Penalty Clause",
        "keywords": [
            "penalty", "late delivery", "delay", "clause", "liquidated damages",
            "contract", "per week", "missing penalty", "no penalty",
        ],
        "phrases": [
            "late delivery", "penalty clause", "no late", "missing penalty",
            "no penalty", "penalty clause is not included", "no late-delivery",
        ],
        "aliases": ["REJECT_3_MISSING_PENALTY", "LATE_PENALTY", "NO_PENALTY_CLAUSE"],
    },
    "REJECT_4": {
        "title": "Missing Supplier TIN or BIN",
        "keywords": [
            "tin", "bin", "tax", "taxpayer", "registration", "identification",
            "missing tin", "missing bin", "details available on request",
        ],
        "phrases": [
            "tin", "bin", "tin or bin", "missing", "registration details",
            "details available on request", "tin is missing", "bin is missing",
        ],
        "aliases": ["REJECT_4_MISSING_TIN_BIN", "TAX_REGISTRATION", "TIN_BIN_MISSING"],
    },
    "REJECT_5": {
        "title": "Delivery Promised Later Than 45 Days",
        "keywords": [
            "delivery", "days", "lead time", "lead-time", "schedule",
            "45 days", "purchase order", "po", "later than 45", "60 days",
        ],
        "phrases": [
            "later than 45", "45 days", "later than 45 days",
            "within 60 days", "delivery within 60 days",
        ],
        "aliases": ["REJECT_5_DELIVERY_EXCESS", "DELIVERY_DELAY", "DELIVERY_OVER_45"],
    },
    "NEEDS_PERSON_1": {
        "title": "Unit Price Marginally Above Cap (<= 3%)",
        "keywords": [
            "unit price", "price", "marginal", "above maximum", "3%",
            "cap", "ceiling", "discretion", "marginally",
        ],
        "phrases": [
            "above the maximum", "no more than 3%", "marginally above",
            "marginal price", "marginally", "marginal",
        ],
        "aliases": ["NEEDS_PERSON_1_PRICE_MARGINAL", "PRICE_MARGINAL"],
    },
    "NEEDS_PERSON_2": {
        "title": "Quantity Discrepancy Exceeds 5%",
        "keywords": [
            "quantity", "qty", "differs", "variance", "5%", "requested",
            "units", "discrepancy", "tolerance", "shortfall",
        ],
        "phrases": [
            "quantity differs", "more than 5%", "quantity discrepancy",
            "qty differs", "differs from requested",
        ],
        "aliases": ["NEEDS_PERSON_2_QTY_DISCREPANCY", "QTY_VARIANCE"],
    },
    "NEEDS_PERSON_3": {
        "title": "Payment Terms Unclear or Outside 30 to 60 Days",
        "keywords": [
            "payment terms", "credit", "days", "30 to 60", "unclear",
            "after delivery", "net days", "terms", "90 days", "30 to 90",
        ],
        "phrases": [
            "payment terms", "30 to 60", "unclear", "outside 30",
            "30 to 90", "within 30 to 90", "outside 30 to 60",
        ],
        "aliases": ["NEEDS_PERSON_3_PAYMENT_TERMS", "PAYMENT_TERMS_UNCLEAR"],
    },
    "NEEDS_PERSON_4": {
        "title": "Delivery Promised in 31 to 45 Days",
        "keywords": [
            "delivery", "promised", "31 to 45", "days", "lead time",
            "lead-time", "schedule", "intermediate", "31", "35", "40",
        ],
        "phrases": [
            "31 to 45", "delivery is promised", "in 31 to 45 days",
            "promised in 31", "35 days",
        ],
        "aliases": ["NEEDS_PERSON_4_DELIVERY_MARGINAL", "DELIVERY_31_45"],
    },
    "NEEDS_PERSON_5": {
        "title": "VAT Not Shown Separately at 15%",
        "keywords": [
            "vat", "15%", "separately", "tax", "value added tax",
            "inclusive", "all taxes included", "vat included", "unseparated",
        ],
        "phrases": [
            "not shown separately", "vat", "15%", "vat included",
            "taxes included", "all taxes included", "vat not shown",
        ],
        "aliases": ["NEEDS_PERSON_5_VAT_STRUCTURE", "VAT_NOT_SEPARATE", "VAT_INCLUSIVE"],
    },
    "NEEDS_PERSON_6": {
        "title": "Arithmetic Discrepancy / Numbers Do Not Add Up",
        "keywords": [
            "numbers", "do not add up", "math", "line total", "subtotal",
            "wrong", "calculation", "arithmetic", "mismatch", "discrepancy",
        ],
        "phrases": [
            "do not add up", "line total", "subtotal", "arithmetic",
            "numbers do not", "mismatch", "calculation error",
        ],
        "aliases": ["NEEDS_PERSON_6_MATH_ERROR", "NUMBERS_DO_NOT_ADD_UP", "MATH_MISMATCH"],
    },
    "NEEDS_PERSON_7": {
        "title": "Quotation Validity Less Than 30 Days",
        "keywords": [
            "validity", "valid for", "less than 30 days", "expiration",
            "valid", "days", "short validity", "validity period",
        ],
        "phrases": [
            "valid for less than 30", "less than 30 days", "valid for",
            "quotation is valid", "valid for less",
        ],
        "aliases": ["NEEDS_PERSON_7_SHORT_VALIDITY", "VALIDITY_LESS_30"],
    },
    "NOTE_1": {
        "title": "Minimum Penalty Rate 0.5% Per Week",
        "keywords": [
            "penalty", "rate", "0.5%", "order value", "per week", "delay",
            "minimum penalty", "delay in delivery",
        ],
        "phrases": [
            "at least 0.5%", "per week of delay", "late-delivery penalty",
            "penalty rate", "0.5% of order value",
        ],
        "aliases": ["NOTE_PENALTY_RATE", "PENALTY_RATE_MINIMUM"],
    },
    "NOTE_2": {
        "title": "Mandatory Exact Citation Requirement",
        "keywords": ["quote", "exact text", "document", "citation", "evidence"],
        "phrases": ["always quote the exact text", "quote the exact text"],
        "aliases": ["NOTE_EXACT_CITATION"],
    },
    "NOTE_3": {
        "title": "Conservative Review Principle (Never Guess)",
        "keywords": ["not sure", "needs a person to check", "never guess", "review"],
        "phrases": ["if you are not sure", "never guess"],
        "aliases": ["NOTE_NEVER_GUESS"],
    },
}


def _tokenize(text: str) -> List[str]:
    """Extract lowercased alphanumeric and percentage tokens, filtering stop words."""
    tokens = re.findall(r"[a-zA-Z0-9%]+", text.lower())
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 1]


class PolicyRAGRetriever:
    """
    RAG engine for company compliance policies.

    Indexes policy rules from company-rules.md, performs semantic keyword
    retrieval against extracted document clauses, and formats grounded citations.
    """

    def __init__(self, rules_markdown_path: str = "data/company-rules.md") -> None:
        """
        Initialize and index rules from markdown.

        Parameters
        ----------
        rules_markdown_path:
            Path to the company-rules.md file.

        Raises
        ------
        FileNotFoundError:
            If rules_markdown_path does not exist.
        """
        path = Path(rules_markdown_path)
        if not path.is_file():
            raise FileNotFoundError(
                f"PolicyRAGRetriever: rules markdown file not found: {rules_markdown_path!r}"
            )

        self._rules: Dict[str, RAGRuleChunk] = {}
        self._rule_keywords: Dict[str, List[str]] = {}
        self._alias_map: Dict[str, str] = {}

        self._parse_markdown(path)

    @property
    def rules(self) -> Dict[str, RAGRuleChunk]:
        """Return a copy of the indexed rule dictionary."""
        return self._rules.copy()

    def _parse_markdown(self, path: Path) -> None:
        """Parse company-rules.md into structured RAGRuleChunk models."""
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        current_section = ""
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            if stripped.startswith("## "):
                header = stripped[3:].strip().lower()
                if "reject" in header:
                    current_section = "REJECT"
                elif "needs a person" in header:
                    current_section = "NEEDS_PERSON"
                elif "other notes" in header:
                    current_section = "OTHER_NOTES"
                else:
                    current_section = ""
                continue

            # Numbered rule matching (e.g. "1. Unit price is...")
            m_num = re.match(r"^(\d+)\.\s*(.+)$", stripped)
            if m_num and current_section in ("REJECT", "NEEDS_PERSON"):
                num = m_num.group(1)
                clause = m_num.group(2).strip()
                rule_id = f"{current_section}_{num}"
                meta = _RULE_METADATA.get(rule_id, {})

                title = str(meta.get("title", f"{current_section.replace('_', ' ').title()} Rule {num}"))
                keywords = list(meta.get("keywords", []))

                chunk = RAGRuleChunk(
                    rule_id=rule_id,
                    rule_category=current_section,
                    title=title,
                    clause_text=clause,
                    similarity_score=None,
                )
                self._rules[rule_id] = chunk
                self._rule_keywords[rule_id] = keywords

                for alias in meta.get("aliases", []):
                    self._alias_map[alias.upper()] = rule_id
                continue

            # Bullet note matching (e.g. "- The late-delivery penalty...")
            m_bullet = re.match(r"^[-*]\s*(.+)$", stripped)
            if m_bullet and current_section == "OTHER_NOTES":
                clause = m_bullet.group(1).strip()
                note_idx = len([k for k in self._rules if k.startswith("NOTE_")]) + 1
                rule_id = f"NOTE_{note_idx}"
                meta = _RULE_METADATA.get(rule_id, {})

                title = str(meta.get("title", f"Policy Note {note_idx}"))
                keywords = list(meta.get("keywords", []))

                chunk = RAGRuleChunk(
                    rule_id=rule_id,
                    rule_category="NOTE",
                    title=title,
                    clause_text=clause,
                    similarity_score=None,
                )
                self._rules[rule_id] = chunk
                self._rule_keywords[rule_id] = keywords

                for alias in meta.get("aliases", []):
                    self._alias_map[alias.upper()] = rule_id
                continue

    def get_rule_by_id(self, rule_id: str) -> Optional[RAGRuleChunk]:
        """
        Retrieve a policy rule directly by its canonical ID or registered alias.

        Parameters
        ----------
        rule_id:
            Identifier (e.g., 'REJECT_1', 'REJECT_1_PRICE_EXCESS', 'reject_2').

        Returns
        -------
        Optional[RAGRuleChunk]
            The matching rule chunk if found, else None.
        """
        if not rule_id:
            return None

        clean_id = rule_id.strip().upper()
        # Direct match
        if clean_id in self._rules:
            return self._rules[clean_id].model_copy()

        # Alias lookup
        canonical_id = self._alias_map.get(clean_id)
        if canonical_id and canonical_id in self._rules:
            return self._rules[canonical_id].model_copy()

        # Prefix normalization (e.g. "REJECT_1_PRICE_EXCESS" -> check "REJECT_1")
        for prefix in ("REJECT_", "NEEDS_PERSON_", "NOTE_"):
            if clean_id.startswith(prefix):
                parts = clean_id.split("_")
                if len(parts) >= 2:
                    short_id = f"{parts[0]}_{parts[1]}"
                    if short_id in self._rules:
                        return self._rules[short_id].model_copy()

        return None

    def retrieve_relevant_rule(self, query: str, top_k: int = 1) -> List[RAGRuleChunk]:
        """
        Perform relevance-weighted retrieval to find the most applicable
        compliance rule(s) for a query.

        Parameters
        ----------
        query:
            Contract clause text, violation topic, or audit query.
        top_k:
            Number of top matching rules to return. Default is 1.

        Returns
        -------
        List[RAGRuleChunk]
            Ranked list of matching RAGRuleChunk objects with similarity_score set.
        """
        if not query or not query.strip():
            return []

        q_tokens = set(_tokenize(query))
        q_lower = query.lower()
        scored_rules: List[tuple[float, RAGRuleChunk]] = []

        for rule_id, rule in self._rules.items():
            meta = _RULE_METADATA.get(rule_id, {})
            p_score = 0.0

            # 1. Exact phrase matching
            phrases = meta.get("phrases", [])
            for p in phrases:
                if p in q_lower:
                    p_score += 0.35

            # 2. Domain-specific contextual & numeric heuristics
            if "delivery" in q_lower:
                days_m = re.search(r"(\d+)\s*days?", q_lower)
                if days_m:
                    days = int(days_m.group(1))
                    if 31 <= days <= 45 and rule_id == "NEEDS_PERSON_4":
                        p_score += 0.5
                    elif days > 45 and rule_id == "REJECT_5":
                        p_score += 0.5

            if "advance" in q_lower:
                adv_m = re.search(r"(\d+(?:\.\d+)?)\s*%", q_lower)
                if adv_m and float(adv_m.group(1)) > 20.0 and rule_id == "REJECT_2":
                    p_score += 0.5

            if "valid" in q_lower:
                val_m = re.search(r"(\d+)\s*days?", q_lower)
                if val_m and int(val_m.group(1)) < 30 and rule_id == "NEEDS_PERSON_7":
                    p_score += 0.5

            # 3. Token overlap with keywords, title, and clause text
            rule_tokens = set()
            for kw in self._rule_keywords.get(rule_id, []):
                rule_tokens.update(_tokenize(kw))
            rule_tokens.update(_tokenize(rule.title))
            rule_tokens.update(_tokenize(rule.clause_text))

            overlap = len(q_tokens.intersection(rule_tokens))
            t_score = (overlap / max(1, len(q_tokens))) * 0.5 if q_tokens else 0.0

            total_score = min(1.0, max(0.0, p_score + t_score))

            if total_score > 0.0:
                chunk = rule.model_copy()
                chunk.similarity_score = round(total_score, 4)
                scored_rules.append((total_score, chunk))

        # Sort descending by score
        scored_rules.sort(key=lambda x: x[0], reverse=True)

        return [item[1] for item in scored_rules[:top_k]]

    def format_grounded_citation(self, rule: RAGRuleChunk, document_quote: str) -> str:
        """
        Format an immutable audit citation pairing the company policy requirement
        with verbatim evidence extracted from the supplier document.

        Parameters
        ----------
        rule:
            The matched policy rule chunk.
        document_quote:
            Verbatim quote or text snippet from the supplier document.

        Returns
        -------
        str
            Formatted citation string.
        """
        quote_str = document_quote.strip() if document_quote else "None provided"
        return (
            f"[Rule: {rule.title}] Policy requirement: '{rule.clause_text}' | "
            f"Quoted document evidence: '{quote_str}'"
        )
