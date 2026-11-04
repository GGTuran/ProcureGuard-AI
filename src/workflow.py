from __future__ import annotations
import time
from typing import Any, Dict, List, Optional
from langgraph.graph import StateGraph, START, END
from src.models import (
    AuditResult,
    AuditState,
    MathCheckResult,
    QuotationDocument,
    RuleViolation,
    Verdict,
)
from src.pdf_parser import PDFParser
from src.math_verifier import MathVerifier
from src.pr_validator import PRValidator
from src.rag_retriever import PolicyRAGRetriever
from src.rules_engine import RulesEngine



# Ingest -> Extract -> MathAudit -> PRCrossCheck -> RAGRetrieve -> RulesEngine -> Finalize.

class ProcurementAuditWorkflow:
    def __init__(self,
                pr_csv_path: str = "data/purchase_requests.csv",
                rules_path: str = "data/company_rules.md",
                ) -> None:
                self.pr_csv_path = pr_csv_path
                self.rules_path = rules_path

                # initialize deterministic domain tools
                self.pr_validator = PRValidator(pr_csv_path)
                self.rag_retriever = PolicyRAGRetriever(rules_path)

                # compile LangGraph StateGraph
                self.app = self._build_graph()

    def _log_trace(
        self, state: AuditState, node: str, status: str, details: str, duration_ms: float
    ) -> None:
        """Helper to append an audti event to the state's workflow trace."""
        trace_entry = {
            "step": len(state.get("workflow_trace", [])) + 1,
            "node": node,
            "status": status,
            "details": details,
            "duration_ms": round(duration_ms, 2),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        state["workflow_trace"].append(trace_entry)

    
    # Node 1: Ingest PDF Stream
    def node_ingest_pdf(self, state: AuditState) -> Dict[str, Any]:
        t0 = time.perd_counter()
        pdf_path = state["pdf_path"]
        try:
            tokens = PDFParser.extract_tokens_from_stream(pdf_path)
            elapsed = (time.perf_counter() - t0) * 1000
            self._log_trace(
                state,
                node="1. IngestPDFStream",
                status="SUCCESS",
                details=f"Decompressed PDF stream and extracted {len(tokens)} text tokens.",
                duration_ms=elapsed,
            )
            return { "raw_tokens": tokens, "workflow_trace": state["workflow_trace"]}
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self._log_trace(
                state,
                node="1. IngestPDFStream",
                status="FAILED",
                details=f"Stream ingestion failed: {e}",
                duration_ms=elapsed,
            )
            return {
                "is_error": True,
                "error_message": str(e),
                "workflow_trace": state["workflow_trace"],
            }
    
    # Node 2: Structured Entity Extraction
    def node_extract_entities(self, state: AuditState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        if state.get("is_error"):
            return {}

        pdf_path = state["pdf_path"]
        try:
            doc = PDFParser.parse_quotation(pdf_path)
            elapsed = (time.perf_counter() - t0) * 1000
            item_desc = doc.items[0].description if doc.items else "None"
            self._log_trace(
                state,
                node="2. StructuredEntityExtraction",
                status="SUCCESS",
                details=f"Extracted supplier '{doc.supplier_name}', Quote: '{doc.quotation_no}', Item: '{item_desc}'.",
                duration_ms=elapsed,
            )
            return {"doc": doc, "workflow_trace": state["workflow_trace"]}
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            self._log_trace(
                state,
                node="2. StructuredEntityExtraction",
                status="FAILED",
                details=f"Entity extraction failed: {e}",
                duration_ms=elapsed,
            )
            return {
                "is_error": True,
                "error_message": str(e),
                "workflow_trace": state["workflow_trace"],
            }

    
    # Node 3: Mathematical Integrity Audit
    def node_audit_math(self, state: AuditState) -> Dict[str,Any]:
        t0 = time.perf_counter()
        if state.get("is_error") or not state.get("doc"):
            return {}
        
        doc = state["doc"]
        math_check = MathVerifier.verify(doc)
        elapsed = (time.perf_counter() - t0) * 1000

        status = "SUCCESS" if math_check.is_mathematically_sound else "WARNING"
        detail_msg = (
            "All arithmetic verified (Line total, Subtotal, 15% VAT, Grand total)."
            if math_check.is_mathematically_sound
            else "; ".join(math_check.details)
        )
        self._log_trace(
            state,
            node="3. MathematicalIntegrityAudit",
            status=status,
            details=detail_msg,
            duration_ms=elapsed,
        )
        return {"math_check": math_check, "workflow_trace": state["workflow_trace"]}

    
    # Node 4: Purchase Request Cross-Validation
    def node_cross_check_pr(self, state: AuditState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        if state.get("is_error") or not state.get("doc"):
            return {}
        doc = state["doc"]
        p_dev, q_dev, pr_viols = self.pr_validator.audit_quotation_against_pr(doc)
        elapsed = (time.perf_counter() - t0) * 1000

        status = "SUCCESS" if not pr_viols else "FLAGGED"
        details = f"PR check: Price delta = {p_dev:+.2f}%, Qty discrepancy = {q_dev:.1f}%."
        self._log_trace(
            state,
            node="4. PRCrossValidation",
            status = status,
            details=details,
            duration_ms=elapsed,
        )
        return {
            "price_deviation_pct": p_dev,
            "qty_deviation_pct": q_dev,
            "pr_violations": pr_viols,
            "workflow_trace": state["workflow_trace"],
        }

    
    # Node 5: RAG Semantic Policy Retrieval
    def node_rag_retrieve(self, state: AuditState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        if state.get("is_error") or not state.get("doc"):
            return {}
        doc = state["doc"]
        retrieved = []

        # Semantically retrieve matching rule for payment terms
        if doc.payment_terms_next:
            matches = self.rag_retriever.retrieve_relevant_rule(doc.payment_terms_text, top_k=1)
            if matches:
                retrieved.extend(matches)
            
        # Semantically retrieve rule for late delivery
        if doc.has_late_penalty_clause and doc.late_penalty_text:
            matches = self.rag_retriever.retrieve_relevant_rule(doc.late_penalty_text, top_k=1)
            if matches:
                retrieved.extend(matches)
        
        elapsed = (time.perf_counter() - t0) * 1000
        self._log_trace(
            state,
            node="5. RAGSemanticRetrieval",
            status="SUCCESS",
            details=f"Retrieved {len(retrieved)} relevant policy rules from company-rules.md.",
            duration_ms=elapsed,
        )
        return {"retrieved_rules": retrieved, "workflow_trace": state["workflow_trace"]}

    
    # node 6: Compilance Rule Engine & HITL
    def node_evaluate_rules(self, state: AuditState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        if state.get("is_error"):
            return {"final_audit": self._build_error_audit(state)}
        doc = state["doc"]
        math_check = state["math_check"]
        pr_viols = state.get("pr_violations", [])
        p_dev = state.get("price_deviation_pct", 0.0)
        q_dev = state.get("qty_deviation_pct", 0.0)

        audit_result = RulesEngine.evaluate(
            doc=doc,
            math_check=math_check,
            pr_violations=pr_viols,
            price_deviation_pct=p_dev,
            qty_deviation_pct=q_dev,
            rag_retriever=self.rag_retriever,
        )

        requires_hitl = audit_result.verdict == Verdict.NEEDS_REVIEW
        audit_result.workflow_trace = state["workflow_trace"]

        elapsed = (time.perf_counter() - t0) * 1000
        self._log_trace(
            state,
            node="6. ComplianceRuleEngine",
            status="SUCCESS",
            details=f"Audit complete. Final Verdict = {audit_result.verdict.value}.",
            duration_ms=elapsed,
        )
        return {
            "final_audit": audit_result,
            "requires_human_escalation": requires_hitl,
            "workflow_trace": state["workflow_trace"],
        }

    
    # Graph
    def _build_graph(self):
        builder = StateGraph(AuditState)

        # Nodes
        builder.add_node("ingest", self.node_ingest_pdf)
        builder.add_node("extract", self.node_extract_entities)
        builder.add_node("math_audit", self.node_audit_math)
        builder.add_node("pr_check", self.node_cross_check_pr)
        builder.add_node("rag_retrieve", self.node_rag_retrieve)
        builder.add_node("evaluate_rules", self.node_evaluate_rules)

        # Edges
        builder.add_edge(START, "ingest")
        builder.add_edge("ingest", "extract")
        builder.add_edge("extract", "math_audit")
        builder.add_edge("math_audit", "pr_check")
        builder.add_edge("pr_check", "rag_retrieve")
        builder.add_edge("rag_retrieve", "evaluate_rules")
        builder.add_edge("evaluate_rules", END)

        return builder.compile()

    # Execution
    def run(self, pdf_path: str) -> AuditResult:
        """Run the compiled LangGraph pipeline on a single document."""
        initial_state: AuditState = {
            "pdf_path": pdf_path,
            "pr_csv_path": self.pr_csv_path,
            "raw_tokens": [],
            "doc": None,
            "math_check": None,
            "retrieved_rules": [],
            "price_deviation_pct": 0.0,
            "qty_deviation_pct": 0.0,
            "pr_violations": [],
            "final_audit": None,
            "workflow_trace": [],
            "requires_human_escalation": False,
            "is_error": False,
            "error_message": None,
        }

        output_state = self.app.invoke(initial_state)
        final_audit = output_state["final_audit"]
        final_audit.workflow_trace = output_state["workflow_trace"]
        return final_audit

    
    def _build_error_audit(self, state: AuditState) -> AuditResult:
        """Fallback for unparseable documents to prevent guessing."""
        return AuditResult(
            source_file=state["pdf_path"],
            supplier_name="Unknown",
            item_code="N/A",
            verdict=Verdict.NEEDS_REVIEW,
            primary_reason=f"Pipeline error: {state.get('error_message', 'Unrecoverable failure')}. Escalating to human.",
            primary_citation="Ingestion pipeline error.",
            math_check=MathCheckResult(is_mathematically_sound=False),
            violations=[
                RuleViolation(
                    rule_category="NEEDS_PERSON",
                    rule_id="SYS_ERROR",
                    rule_title="Ingestion Error",
                    detail=state.get("error_message", "Error"),
                    exact_citation="N/A",
                )
            ],
            human_action_required="Manual audit required.",
            workflow_trace=state["workflow_trace"],
        )


