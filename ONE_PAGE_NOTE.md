# 👔 ProcureGuard AI: One-Page Engineering Assessment Brief

**Candidate:** Md Tayyab Ameri Turan  
**Assessment:** BIAI (Bangladesh Institute of AI / BIAI Labs) — Round 2 Technical Task  
**Task Selected:** Task 1: Check Supplier Documents (Aamar Garments Ltd, RMG Sector)  
**Repository:** [https://github.com/GGTuran/ProcureGuard-AI](https://github.com/GGTuran/ProcureGuard-AI)  
**Live Demo:** [ProcureGuard AI Streamlit App](https://procureguardai.streamlit.app/)  
<!-- **Loom Video:** [5-Minute Solution Presentation](https://www.loom.com/) *(Paste your Loom link here)*   -->

---

### 1. What Was Built
**ProcureGuard AI** is a production-grade, deterministic document compliance and arithmetic verification system tailored for garment manufacturing purchase orders. 

Rather than relying on non-deterministic, hallucination-prone Large Language Models to calculate numbers, the system uses a **6-node LangGraph StateGraph** coupled with code-level domain tools:
1. **Dependency-Free PDF Stream Parser:** Directly decompresses ReportLab content streams (`ASCII85` + `zlib`) in pure Python stdlib, eliminating fragile external C-libraries (Poppler/PyMuPDF).
2. **Zero-Tolerance Arithmetic Engine:** Audits multi-digit float multiplications ($Qty \times Unit\ Price = Amount$), Subtotal, 15% VAT itemization, and Grand Total with 5-paisa (0.05 BDT) precision.
3. **Purchase Request Validator:** Computes exact price ceiling and quantity delta percentages against `purchase-request.csv`.
4. **Policy RAG Retriever:** Indexes natural language compliance rules (`company-rules.md`) and returns grounded, verbatim citations.
5. **Hierarchical Rules Engine:** Enforces two-tier business logic (Priority 1: Hard Reject $\rightarrow$ Priority 2: Human-in-the-Loop Review $\rightarrow$ Fallback: Approve).
6. **Interactive Streamlit Dashboard:** Features an upload dropzone, real-time node latency steppers, and a Human-in-the-Loop managerial override panel.

---

### 2. How It Was Tested
The solution was validated using a multi-layered testing strategy:
* **Ground-Truth Fleet Verification (`run_audit.py`):** Batch audited all 10 reference sample quotation packs (`supplier-pack-01.pdf` through `10.pdf`), asserting exact verdict matches, price deviations, and citation accuracy.
* **Automated Integration Tests (`tests/test_ground_truth.py`):** 10 automated test cases asserting that each sample pack triggers its intended business outcome.
* **Unit & Edge-Case Suite (`tests/test_math_rules.py`):** Tested floating-point rounding, VAT calculation mismatches (10% vs 15%), arithmetic line discrepancies, and boundary conditions (e.g., advance payment at 20.0% vs 20.1%, delivery lead-time at 30d vs 31d vs 45d vs 46d).
* **Synthetic Out-of-Distribution Validation (`generate_test_cases.py`):** Generated 3 new unseen quotation PDFs (Pack 11: Approve, Pack 12: Reject, Pack 13: HITL) to prove generalization beyond the sample dataset.

---

### 3. Results
* **10 / 10 (100.0%) Verified Accuracy:** Matches all expected business decisions across the benchmark dataset:
  * **2 Approved:** Packs 01, 02 (fully compliant).
  * **5 Rejected:** Packs 03 (+9.05% price), 05 (40% advance), 06 (missing penalty), 08 (missing TIN/BIN), 10 (60-day delivery).
  * **3 Human-in-the-Loop:** Packs 04 (+2.31% price review), 07 (17.5% quantity short), 09 (arithmetic discrepancy 322k vs 320k).
* **Execution Performance:** 13 unit tests execute in **0.052 seconds**. Individual quotation audits complete in **~2 milliseconds**.
* **Zero Math Hallucination:** Code-level arithmetic guarantees that no invoice with calculation errors can pass automated release.

---

### 4. Limitations (What Does Not Work Well)
1. **ReportLab Stream Heuristic Dependency:** The parser is optimized for digital vector PDFs with single content streams. Scanned raster images, photocopies, or skewed mobile camera photos would require an upstream OCR engine (e.g., Tesseract or Gemini Vision) before stream tokenization.
2. **Single-Item Quotation Scope:** The current PR schema assumes one primary line item per quotation pack. Multi-item consolidated quotations would require expanding the cross-validation logic into a matrix mapper.
3. **In-Memory Session Persistence:** Human-in-the-loop managerial overrides are maintained in Streamlit session state and reset on server reload without an external persistent database.

---

### 5. Next Steps & Production Roadmap
* **Observability with LangSmith & OpenTelemetry:** Instrument the StateGraph with LangSmith to track node-by-node execution latency, trace event logs, and capture production failure anomalies.
* **Enterprise FastAPI Backend & RBAC:** Decouple the UI from business logic using a high-throughput async FastAPI service backed by PostgreSQL. Implement Role-Based Access Control (RBAC): Junior Officers can only flag and request exceptions; only authorized Department Heads can grant managerial overrides.
* **Hybrid LLM Reasoning for Unstructured Contracts:** Integrate an LLM reasoning node (e.g., Gemini 1.5 Pro with Extended Thinking) for edge cases with non-standard legal phrasing, foreign languages, or automated counter-offer email drafting.
* **3-Way Matching Expansion:** Extend the workflow from 2-way matching (PR vs Quote) to complete 3-way matching (PR vs Quote vs Goods Received Note / Warehouse Inventory vs Final Tax Invoice).