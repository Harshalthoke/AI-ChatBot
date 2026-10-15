# Research Journal Finder AI

**Evidence-Grounded Autonomous Academic Journal Recommendation System**

Research Journal Finder AI is an intelligent research publishing assistant built for academic authors and research scientists. The system identifies, verifies, evaluates, and ranks suitable peer-reviewed academic journals for manuscript submission using live scholarly registries (OpenAlex, Crossref, DOAJ) powered by a bounded LangGraph autonomous workflow engine and SQLite persistence.

---

## 1. System Architecture

```
                                  +----------------------------+
                                  | Streamlit Academic UI      |
                                  | (Dashboard, Form, Reports) |
                                  +--------------+-------------+
                                                 |
                                                 v
                                  +----------------------------+
                                  |  LangGraph Agent Workflow  |
                                  +--------------+-------------+
                                                 |
       +--------------------+--------------------+--------------------+
       |                    |                    |                    |
       v                    v                    v                    v
+--------------+    +---------------+    +---------------+    +---------------+
| OpenAlex API |    | Crossref API  |    |   DOAJ API    |    |  Multi-Criteria
| Works/Venues |    | Metadata/ISSN |    |  Verification |    | Ranking Engine|
+--------------+    +---------------+    +---------------+    +---------------+
       |                    |                    |                    |
       +--------------------+--------------------+--------------------+
                                                 |
                                                 v
                                  +----------------------------+
                                  | SQLite Storage & Reports   |
                                  | (Sessions, HTML/CSV/JSON)  |
                                  +----------------------------+
```

### Core Architecture Components

1. **State Machine (`agent/workflow.py`, `agent/state.py`):**
   - Built on LangGraph state graph.
   - Executes multi-step autonomous cycles:
     - `generate_queries`: Generates targeted query variations based on title, keywords, domain, and concepts.
     - `search_venues`: Discovers publications and journal sources across OpenAlex and Crossref.
     - `verify_evidence`: Authoritative registry validation (DOAJ, Crossref, ISSN, publisher checks).
     - `rank_and_score`: Computes normalized semantic similarity, domain fit, suitability, and evidence scores.
     - `refine_queries`: Analyzes candidate concept clusters and constructs follow-up queries.
     - `synthesize_summary`: Grounded research summary and manuscript submission advice.
   - Strict stopping rules: Max iterations, maximum API calls budget, no-progress termination, and sufficient qualifying candidates.

2. **Scholarly Service Clients (`services/`):**
   - `OpenAlexService`: Fetches related works and journal sources with polite headers and rate-limiting.
   - `CrossrefService`: Queries works and retrieves authoritative journal container metadata.
   - `DOAJService`: Verifies official Directory of Open Access Journals inclusion, APC fee schedules, and DOAJ seal statuses.
   - `VerificationService`: Anti-hallucination auditor that calculates explicit verification states (`VERIFIED`, `NOT_VERIFIED`, `CONFLICTING_EVIDENCE`, `REQUIRES_MANUAL_REVIEW`, `UNAVAILABLE`).

3. **Multi-Criteria Ranking Engine (`services/ranking_service.py`):**
   - Configurable composite score:
     - Research Relevance (Semantic similarity via TF-IDF + Cosine Similarity, Topic overlap, Domain alignment)
     - Publication Suitability (Open Access preference match, APC budget constraints, Indexing requests)
     - Evidence Completeness (Ratio of verifiable metadata fields present)

4. **Persistence & Reporting (`database/`, `services/report_service.py`):**
   - SQLite relational storage (`data/journal_finder.db`) tracking sessions, profiles, iterations, candidates, rankings, and logs.
   - Report generator exporting styled HTML reports, CSV comparison spreadsheets, and JSON session dumps.

5. **User Interface (`app.py`, `ui/`):**
   - Modern Streamlit academic dashboard featuring 7 views:
     1. **Dashboard:** System metrics, active configuration, and recent search history.
     2. **Find Journals:** Manuscript submission form, PDF text extraction, live agent execution status.
     3. **Agent Activity:** Real-time event log, query history, and iteration metrics.
     4. **Journal Comparison:** Interactive matrix with filters (OA, fee, score) and CSV/HTML downloads.
     5. **Verification Reports:** Registry audit inspecting verified facts, warnings, and discrepancies.
     6. **Search History:** Previous sessions stored in SQLite with reloading and deletion.
     7. **Settings:** Dynamic tuning of search thresholds, ranking weights, and API credentials.

---

## 2. Project File Tree

```
AI Agent/
├── .env.example               # Environment variables template
├── .gitignore                  # Git ignore rules
├── requirements.txt            # Tested Python dependency constraints
├── pytest.ini                  # Pytest configuration
├── README.md                   # Project documentation and guide
├── app.py                      # Main Streamlit web application
├── agent/
│   ├── __init__.py             # Agent module exports
│   ├── state.py                # ResearchAgentState schema (TypedDict)
│   └── workflow.py             # LangGraph state machine and decision loops
├── config/
│   ├── __init__.py
│   └── settings.py             # Pydantic application settings & defaults
├── database/
│   ├── __init__.py             # Database exports
│   ├── db.py                   # SQLite connection & lifecycle management
│   ├── repository.py           # ResearchRepository for session and candidate CRUD
│   └── schema.sql              # Relational database schema
├── models/
│   ├── __init__.py
│   ├── evidence.py             # VerificationStatus, EvidenceRecord, JournalVerificationSummary
│   ├── journal.py              # JournalRecord, JournalRankingResult, RepresentativePublication
│   └── research.py             # ResearchProfile, ResearchInputSubmission, AccessPreference
├── services/
│   ├── __init__.py
│   ├── crossref_service.py     # Crossref API client
│   ├── doaj_service.py         # DOAJ API client
│   ├── llm_service.py          # LLM provider adapter (Gemini, OpenAI, Ollama, Fallback)
│   ├── openalex_service.py     # OpenAlex API client
│   ├── ranking_service.py      # Multi-criteria scoring and ranking engine
│   ├── report_service.py       # HTML, CSV, and JSON report generator
│   └── verification_service.py # Evidence auditing and consistency checker
├── ui/
│   ├── __init__.py
│   ├── activity_view.py        # Real-time agent event timeline & metrics
│   ├── comparison.py           # Multi-attribute filter & comparison matrix
│   ├── dashboard.py            # Overview and system health view
│   └── journal_cards.py        # Journal candidate card component with badges
├── utils/
│   ├── __init__.py
│   ├── caching.py              # SQLite request caching
│   ├── deduplication.py        # ISSN normalization & canonical key merging
│   ├── pdf_extractor.py        # PyMuPDF manuscript text & section parser
│   ├── retry.py                # Exponential backoff retry handler
│   └── text_processing.py      # Stopwords, n-grams, and query variation generator
├── data/
│   └── journal_finder.db       # Local SQLite database
├── reports/                    # Generated HTML, CSV, and JSON reports
└── tests/
    ├── conftest.py             # Shared pytest fixtures
    ├── test_agent_loop.py      # Integration tests for LangGraph agent
    ├── test_analyzer.py        # Input validation & PDF extraction tests
    ├── test_deduplication.py   # Canonical keys & record merge tests
    ├── test_ranking.py         # Multi-criteria ranking & weights tests
    ├── test_search.py          # OpenAlex, Crossref, DOAJ mocks & error tests
    ├── test_stopping_conditions.py # Bounded loop termination tests
    └── test_verification.py    # DOAJ & publisher verification tests
```

---

## 3. Installation & Windows Setup

### Prerequisites
- Windows 10 or Windows 11
- Python 3.11 or Python 3.12/3.13 installed and added to PATH
- PowerShell

### Step-by-Step PowerShell Setup Commands

1. **Open PowerShell and navigate to the project directory:**
   ```powershell
   cd "d:\AI Agent"
   ```

2. **Create the virtual environment:**
   ```powershell
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   *(If execution policies prevent script activation, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`)*

4. **Install tested dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```

5. **Set up environment variables:**
   ```powershell
   Copy-Item .env.example .env
   ```

---

## 4. How to Launch the Application

Run the Streamlit application using Windows PowerShell:

```powershell
.\venv\Scripts\streamlit.exe run app.py
```

The application will start locally and open in your default web browser at:
`http://localhost:8501`

---

## 5. API Credentials & Configuration

Edit the `.env` file to customize settings:

```env
# Polite API Pool Contact Information (Recommended for high rate limits)
OPENALEX_EMAIL=your.email@university.edu
CROSSREF_EMAIL=your.email@university.edu

# LLM Provider Configuration: "fallback", "gemini", "openai", or "ollama"
LLM_PROVIDER=fallback

# Google Gemini (Optional)
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash

# OpenAI (Optional)
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini

# Ollama Local LLM (Optional)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

> **Note on LLM Requirements:** A paid LLM API key is **not required**. The application includes an offline deterministic heuristic fallback that analyzes research inputs, ranks venues, and produces structured grounded advice without external AI dependencies.

---

## 6. Automated Testing & Verification

The test suite validates input parsing, API clients, fault tolerance, deduplication, ranking, evidence verification, and autonomous agent loops.

### Run Tests Command

```powershell
.\venv\Scripts\python.exe -m pytest -v
```

### Actual Test Results

```text
============================= test session starts =============================
platform win32 -- Python 3.13.14, pytest-9.1.1, pluggy-1.6.0
rootdir: D:\AI Agent
configfile: pytest.ini
testpaths: tests
collected 30 items

tests/test_agent_loop.py::test_full_agent_workflow_integration PASSED    [  3%]
tests/test_agent_loop.py::test_agent_workflow_partial_results_on_api_failure PASSED [  6%]
tests/test_analyzer.py::test_valid_research_profile_creation PASSED      [ 10%]
tests/test_analyzer.py::test_invalid_research_profile_empty_fields PASSED [ 13%]
tests/test_analyzer.py::test_pdf_extraction_valid PASSED                 [ 16%]
tests/test_analyzer.py::test_pdf_extraction_corrupted_bytes PASSED       [ 20%]
tests/test_analyzer.py::test_pdf_metadata_extraction PASSED              [ 23%]
tests/test_analyzer.py::test_query_variations_generation PASSED          [ 26%]
tests/test_deduplication.py::test_normalize_issn PASSED                  [ 30%]
tests/test_deduplication.py::test_canonical_title_slug PASSED            [ 33%]
tests/test_deduplication.py::test_merge_journal_records_same_issn PASSED [ 36%]
tests/test_deduplication.py::test_distinct_journals_different_issn_not_merged PASSED [ 40%]
tests/test_deduplication.py::test_get_canonical_journal_key PASSED       [ 43%]
tests/test_ranking.py::test_ranking_computes_normalized_scores PASSED    [ 46%]
tests/test_ranking.py::test_ranking_budget_constraint_penalty PASSED     [ 50%]
tests/test_ranking.py::test_ranking_weights_customization PASSED         [ 53%]
tests/test_search.py::test_openalex_search_works_success PASSED          [ 56%]
tests/test_search.py::test_openalex_timeout_handling PASSED              [ 60%]
tests/test_search.py::test_crossref_search_success PASSED                [ 63%]
tests/test_search.py::test_doaj_journal_lookup PASSED                    [ 66%]
tests/test_search.py::test_api_rate_limiting_429_handling PASSED         [ 70%]
tests/test_search.py::test_malformed_json_response_handling PASSED       [ 73%]
tests/test_stopping_conditions.py::test_stopping_condition_max_iterations PASSED [ 76%]
tests/test_stopping_conditions.py::test_stopping_condition_max_api_calls PASSED [ 80%]
tests/test_stopping_conditions.py::test_stopping_condition_no_progress PASSED [ 83%]
tests/test_stopping_conditions.py::test_stopping_condition_sufficient_candidates PASSED [ 86%]
tests/test_stopping_conditions.py::test_stopping_condition_continues_when_incomplete PASSED [ 90%]
tests/test_verification.py::test_verification_service_with_doaj_match PASSED [ 93%]
tests/test_verification.py::test_verification_conflicting_publisher PASSED [ 96%]
tests/test_verification.py::test_verification_unverified_no_issn PASSED  [100%]

====================== 30 passed in 18.85s =======================
```

---

## 7. Known Limitations & Roadmap

### Known Limitations
- **Proprietary Index Verification:** Direct Scopus and Web of Science Master Journal List lookups require institution-subscribed API credentials. The system flags unverified indexing claims with explicit warnings rather than guessing or fabricating.
- **Cold Import Overhead:** On initial execution under Windows Defender, Python scientific packages (`numpy`, `scikit-learn`) require a few seconds to verify signatures; subsequent runs execute instantly from cache.

### Development Roadmap
- [ ] Integration of official Elsevier Scopus API key adapter for direct citation percentile lookups.
- [ ] Export of publication recommendation dossiers directly to vector PDF format.
- [ ] Automatic LaTeX bibliography / BibTeX citation format export for candidate journals.
