# 👔 ProcureGuard AI — Enterprise Procurement Compliance & Document Audit Pipeline

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic V2](https://img.shields.io/badge/Validation-Pydantic%20V2-green.svg)](https://docs.pydantic.dev/)
[![Streamlit](https://img.shields.io/badge/UI-Streamlit-red.svg)](https://streamlit.io/)


An enterprise-grade, deterministic document intelligence and compliance auditing pipeline designed for garment manufacturing purchase orders (**Aamar Garments Ltd, RMG sector**). 

Built with **LangGraph StateGraph**, zero-tolerance arithmetic verification, and grounded Policy RAG, **ProcureGuard AI** automates quotation vetting, eliminates mathematical hallucinations, enforces strict commercial thresholds, and provides human-in-the-loop (HITL) managerial escalation.

---

## 🌐 Live Interactive Demo

**Live Application:** [ProcureGuard AI on Streamlit Community Cloud](https://procureguardai.streamlit.app/)   


---

## 📌 Executive Summary & Problem Statement

In the Bangladeshi Ready-Made Garments (RMG) industry, procurement margins are razor-thin. Factories process hundreds of supplier quotations across raw cotton, zippers, polyester sewing threads, poly bags, and export cartons. 

Standard generative AI approaches (feeding PDFs directly to LLMs) fail in enterprise procurement due to:
1. **Mathematical Hallucinations:** LLMs cannot reliably multiply large multi-digit floats or verify 15% VAT allocations.
2. **Boundary Condition Inconsistency:** Discretionary tolerances (e.g., unit price $\le 3\%$ above cap requiring review vs $> 3\%$ requiring hard rejection) are frequently conflated.
3. **Lack of Verifiable Grounding:** Approvals without exact contract and policy clause citations fail financial compliance audits.

**ProcureGuard AI solves this with a code-first, deterministic architecture:**
* **100% Verified Accuracy (10 / 10 Benchmark Packs)** matching all ground-truth commercial decisions.
* **5-Paisa Precision Code-Level Arithmetic Engine:** Zero LLM math errors.
* **Grounded Policy RAG:** Every decision links directly to verbatim company policy clauses.
* **Human-in-the-Loop Safeguard:** Transparent escalation with recorded managerial audit trails.

---



### The 6 Execution Graph Nodes
1. **`IngestPDFStream`**: Native stdlib parser decodes ReportLab PDF content streams (`ASCII85` + `zlib`) without heavyweight C-bindings (no Poppler or PyMuPDF dependencies).
2. **`ExtractQuotationSchema`**: Ingests token streams into structured `QuotationDocument` models with Pydantic validation.
3. **`AuditArithmetic`**: Verifies line item amounts ($Qty \times Unit\ Price = Amount$), Subtotal integrity, separate 15% VAT computation, and grand totals with 0.05 BDT floating-point tolerance.
4. **`ValidatePurchaseRequest`**: Computes signed price deviation relative to the authorized PR cap and quantity variances.
5. **`RetrievePolicyRule`**: Retrieves verbatim company rules from `company-rules.md` to ground citations.
6. **`EvaluateCompliance`**: Evaluates hierarchical business logic (Priority 1: Hard Reject $\rightarrow$ Priority 2: Needs Review $\rightarrow$ Fallback: Approve).

---

## 📊 Ground-Truth Reference Benchmark (100% Accuracy)

| Supplier Pack | Quoted Item | Quoted vs Cap | Math Audit | Actual Verdict | Expected Verdict | Primary Audit Rationale |
|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `pack-01.pdf` | **A** (Twill Fabric) | -1.67% | **PASS** | **`APPROVE`** | `APPROVE` | Compliant with all policies; math 100% sound. |
| `pack-02.pdf` | **B** (Metal Zipper) | -5.26% | **PASS** | **`APPROVE`** | `APPROVE` | Compliant quote; 0% advance payment within terms. |
| `pack-03.pdf` | **C** (Sewing Thread) | **+9.05%** | **PASS** | **`REJECT`** | `REJECT` | **Hard Reject:** Unit price exceeds authorized cap by > 3%. |
| `pack-04.pdf` | **D** (Poly Bag) | **+2.31%** | **PASS** | **`NEEDS REVIEW`** | `NEEDS REVIEW` | **HITL Required:** Unit price marginally above cap ($\le 3\%$). |
| `pack-05.pdf` | **E** (Carton Box) | -3.16% | **PASS** | **`REJECT`** | `REJECT` | **Hard Reject:** Advance payment requested (40%) exceeds 20% limit. |
| `pack-06.pdf` | **A** (Twill Fabric) | -3.12% | **PASS** | **`REJECT`** | `REJECT` | **Hard Reject:** Mandatory late-delivery penalty clause is omitted. |
| `pack-07.pdf` | **B** (Metal Zipper) | -7.89% | **PASS** | **`NEEDS REVIEW`** | `NEEDS REVIEW` | **HITL Required:** Quoted quantity is 17.5% below PR request (> 5% Δ). |
| `pack-08.pdf` | **C** (Sewing Thread) | -2.38% | **PASS** | **`REJECT`** | `REJECT` | **Hard Reject:** Supplier TIN/BIN registration is missing. |
| `pack-09.pdf` | **D** (Poly Bag) | -1.54% | **FAIL** | **`NEEDS REVIEW`** | `NEEDS REVIEW` | **HITL Required:** Numbers do not add up (Stated 322k vs Calc 320k). |
| `pack-10.pdf` | **E** (Carton Box) | -1.05% | **FAIL** | **`REJECT`** | `REJECT` | **Hard Reject:** Delivery timeline (60 days) exceeds 45-day ceiling. |

**Audit Accuracy:** **10 / 10 (100.0%)** | **Unit Tests Passing:** **13 / 13 in 0.052s**

---

## 🛠️ Technology Stack

* **Language:** Python 3.10 / 3.11 / 3.12
* **Package Management:** [`uv`](https://github.com/astral-sh/uv) (Astral) / `pip`
* **Workflow Orchestration:** [LangGraph 1.2+](https://github.com/langchain-ai/langgraph) (StateGraph, State contracts)
* **Data Validation & Modeling:** [Pydantic V2](https://docs.pydantic.dev/)
* **Document Processing:** Python Standard Library (`zlib`, `base64`, ASCII85 stream parser)
* **Interactive UI:** [Streamlit](https://streamlit.io/) with responsive CSS Grid
* **Data Processing & Analytics:** Pandas 2.2+, NumPy
* **Testing:** Pytest & Unittest

---

## 📂 Project Directory Structure

```text
ProcureGuard-AI/
├── data/                               # Reference datasets & document packs
│   ├── purchase-request.csv            # Authorized PR line items and price caps
│   ├── company-rules.md                # Natural language company procurement policy
│   ├── supplier-pack-01.pdf            # Benchmark reference quotation packs (01 to 10)
│   └── ...
├── src/                                # Core application source code
│   ├── __init__.py                     # Clean package exports
│   ├── models.py                       # Pydantic schemas (AuditResult, QuotationDocument)
│   ├── pdf_parser.py                   # ASCII85/zlib ReportLab stream tokenizer & parser
│   ├── math_verifier.py                # 5-paisa floating point arithmetic engine
│   ├── pr_validator.py                 # Budget ceiling & quantity delta validator
│   ├── rag_retriever.py                # Policy RAG retriever with verbatim grounding
│   ├── rules_engine.py                 # Two-tier hierarchical compliance evaluation engine
│   ├── workflow.py                     # 6-node LangGraph StateGraph pipeline
│   └── audit_pipeline.py               # Facade for single-document & batch audits
├── tests/                              # Comprehensive unit and integration test suite
│   ├── test_ground_truth.py            # Integration tests asserting all 10 sample packs
│   └── test_math_rules.py              # Boundary & arithmetic discrepancy unit tests
├── app.py                              # Interactive Streamlit compliance dashboard
├── run_audit.py                        # CLI batch audit runner with terminal reports
├── generate_test_cases.py              # Synthetic quotation generator (Approve/Reject/HITL)
├── ONE_PAGE_NOTE.md                    # Executive one-page brief
├── requirements.txt                    # Pinned production dependencies
└── README.md                           # Project technical documentation
```

---

## ⚡ Quickstart & Installation

### Option 1: Fast Setup with `uv` (Recommended)

[`uv`](https://github.com/astral-sh/uv) installs dependencies in seconds:

```bash
# 1. Clone the repository
git clone https://github.com/GGTuran/ProcureGuard-AI.git
cd ProcureGuard-AI

# 2. Create and activate a virtual environment with uv
uv venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

# 3. Install pinned dependencies
uv pip install -r requirements.txt
```

### Option 2: Standard Setup with `pip`

```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux / macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

---

## 🧪 Running Tests & Verification

### 1. Run the Complete Test Suite
Run the 13 automated unit and integration tests:

```bash
python -m unittest discover tests
```
*Expected Output:* `Ran 13 tests in 0.052s — OK`

### 2. Run the CLI Benchmark Auditor
Execute the batch auditor across all supplier quotation packs:

```bash
python run_audit.py
```
This prints the terminal compliance matrix, asserts the 10/10 verified accuracy, and exports `audit_report.md` and `audit_results.csv`.

### 3. Generate New Out-of-Distribution Test Packs
Generate 3 new synthetic quotation PDFs (Approve, Reject, and HITL):

```bash
python generate_test_cases.py
```

---

## 🖥️ Running the Interactive Streamlit Dashboard

Launch the local web application:

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`.

### Key Dashboard Capabilities:
* **Upload Supplier Quotation**: Drag and drop any quotation PDF to run real-time compliance auditing.
* **1-Click Recruiter Quick-Test**: Test pre-audited benchmark quotes instantly with one click.
* **Visual Execution Stepper**: Real-time visualization of the 6 LangGraph nodes with millisecond latencies.
* **Human-in-the-Loop Action Panel**: Interactive managerial override logging with persistent audit trail timestamps.
* **Deep-Dive Tabs**: Inspect line-by-line arithmetic, PR comparison diffs, verbatim policy citations, and the 10-pack fleet report.

---

## 📜 Compliance Decision Rules

### Priority 1: Hard Reject (Automatic Dealbreaker)
1. Unit price $> 3\%$ above purchase request authorized cap.
2. Advance payment requested exceeds $20.0\%$.
3. Missing mandatory late-delivery penalty clause (or rate $< 0.5\%$ per week).
4. Missing supplier Tax Identification Number (TIN) or Business Identification Number (BIN).
5. Promised delivery exceeds $45$ days after purchase order issuance.

### Priority 2: Needs a Person to Check (HITL Escalation)
1. Unit price is above cap, but by no more than $3\%$ (discretionary threshold).
2. Quoted quantity differs from requested quantity by $> 5\%$.
3. Payment terms unclear or outside the standard $30$ to $60$ day window.
4. Promised delivery falls in the $31$ to $45$ day window.
5. VAT is not shown separately at $15\%$.
6. Arithmetic discrepancy (numbers do not add up).
7. Quotation validity period is less than $30$ days.

### Fallback: Approve
Quotation satisfies 100% of commercial rules, math is verified, and delivery is within standard SLA.

---

