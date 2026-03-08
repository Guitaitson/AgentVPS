-- Migration: Memory audit persistence + Soul identity governance

-- Memory audit log
CREATE TABLE IF NOT EXISTS memory_audit_log (
    id BIGSERIAL PRIMARY KEY,
    event_ts TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    action VARCHAR(50) NOT NULL,
    memory_type VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    memory_key VARCHAR(255) NOT NULL,
    scope VARCHAR(50) NOT NULL,
    project_id VARCHAR(100),
    redacted BOOLEAN DEFAULT FALSE,
    outcome VARCHAR(50) DEFAULT 'success',
    details JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_memory_audit_ts ON memory_audit_log(event_ts DESC);
CREATE INDEX IF NOT EXISTS idx_memory_audit_user ON memory_audit_log(user_id, event_ts DESC);

-- Soul artifacts (versioned identity)
CREATE TABLE IF NOT EXISTS agent_soul_artifacts (
    id BIGSERIAL PRIMARY KEY,
    artifact_type VARCHAR(50) NOT NULL,
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(artifact_type, version)
);

CREATE INDEX IF NOT EXISTS idx_soul_artifact_type_version
ON agent_soul_artifacts(artifact_type, version DESC);

-- Soul change proposals (approval workflow)
CREATE TABLE IF NOT EXISTS agent_soul_change_proposals (
    id BIGSERIAL PRIMARY KEY,
    artifact_type VARCHAR(50) NOT NULL,
    proposed_content TEXT NOT NULL,
    rationale TEXT NOT NULL,
    impact_level VARCHAR(20) DEFAULT 'medium',
    requires_approval BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'pending',
    requested_by VARCHAR(100) DEFAULT 'system',
    reviewer VARCHAR(100),
    review_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    applied_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_soul_proposals_status
ON agent_soul_change_proposals(status, created_at DESC);
