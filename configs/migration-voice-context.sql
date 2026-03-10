-- Migration: Voice context ingestion

CREATE TABLE IF NOT EXISTS voice_ingestion_jobs (
    id BIGSERIAL PRIMARY KEY,
    source VARCHAR(100) NOT NULL,
    batch_date DATE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    finished_at TIMESTAMP WITH TIME ZONE,
    stats_json JSONB DEFAULT '{}',
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS voice_audio_files (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES voice_ingestion_jobs(id) ON DELETE CASCADE,
    sha256 VARCHAR(64) NOT NULL UNIQUE,
    filename VARCHAR(255) NOT NULL,
    device_timestamp TIMESTAMP WITH TIME ZONE,
    duration_seconds FLOAT,
    transcript_path TEXT,
    archive_path TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS voice_context_items (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NOT NULL REFERENCES voice_ingestion_jobs(id) ON DELETE CASCADE,
    file_id BIGINT REFERENCES voice_audio_files(id) ON DELETE SET NULL,
    item_type VARCHAR(50) NOT NULL,
    memory_target VARCHAR(50) NOT NULL,
    domain VARCHAR(100) NOT NULL,
    risk_level VARCHAR(20) NOT NULL DEFAULT 'low',
    confidence FLOAT DEFAULT 0.0,
    payload_json JSONB NOT NULL,
    commit_status VARCHAR(30) NOT NULL DEFAULT 'extracted',
    proposal_id INTEGER,
    memory_key VARCHAR(255),
    review_note TEXT,
    committed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voice_jobs_status
ON voice_ingestion_jobs(status, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_voice_files_job_status
ON voice_audio_files(job_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_voice_context_commit_status
ON voice_context_items(commit_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_voice_context_proposal
ON voice_context_items(proposal_id);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_voice_audio_files_updated') THEN
        CREATE TRIGGER trg_voice_audio_files_updated
            BEFORE UPDATE ON voice_audio_files
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_voice_context_items_updated') THEN
        CREATE TRIGGER trg_voice_context_items_updated
            BEFORE UPDATE ON voice_context_items
            FOR EACH ROW EXECUTE FUNCTION update_updated_at();
    END IF;
END $$;
