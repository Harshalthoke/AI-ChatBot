-- Schema for Research Journal Finder AI Local SQLite Database

CREATE TABLE IF NOT EXISTS research_sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'PENDING',
    stop_reason TEXT,
    iteration_count INTEGER DEFAULT 0,
    api_call_count INTEGER DEFAULT 0,
    research_summary TEXT
);

CREATE TABLE IF NOT EXISTS research_profiles (
    profile_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL,
    abstract TEXT,
    keywords TEXT, -- Comma-separated or JSON list
    domain TEXT,
    methodology TEXT,
    access_preference TEXT,
    max_apc_usd REAL,
    indexing_preferences TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES research_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS search_iterations (
    iteration_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    iteration_number INTEGER NOT NULL,
    query_used TEXT,
    candidates_found INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES research_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidate_journals (
    record_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    title TEXT NOT NULL,
    issn_linking TEXT,
    issn_print TEXT,
    issn_electronic TEXT,
    publisher TEXT,
    homepage_url TEXT,
    subject_areas TEXT, -- JSON array
    is_open_access INTEGER,
    apc_usd REAL,
    metrics_json TEXT,
    sources_contributed TEXT, -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES research_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS verification_checks (
    check_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    journal_key TEXT NOT NULL,
    status TEXT NOT NULL,
    is_doaj_listed INTEGER,
    inconsistencies TEXT, -- JSON array
    warnings TEXT, -- JSON array
    items_verified INTEGER DEFAULT 0,
    items_total INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES research_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ranking_results (
    ranking_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    journal_key TEXT NOT NULL,
    rank_position INTEGER NOT NULL,
    total_score REAL NOT NULL,
    research_relevance_score REAL NOT NULL,
    publication_suitability_score REAL NOT NULL,
    evidence_completeness_score REAL NOT NULL,
    explanation TEXT,
    confidence_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES research_sessions(session_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    log_message TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES research_sessions(session_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sessions_created ON research_sessions(created_at);
CREATE INDEX IF NOT EXISTS idx_candidates_session ON candidate_journals(session_id);
CREATE INDEX IF NOT EXISTS idx_rankings_session ON ranking_results(session_id);
