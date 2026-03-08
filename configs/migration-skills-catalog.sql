-- Migration: skills external catalog sync tables

CREATE TABLE IF NOT EXISTS skills_catalog (
    id BIGSERIAL PRIMARY KEY,
    skill_name VARCHAR(255) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    version VARCHAR(100) NOT NULL,
    schema_hash VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(skill_name, source_name)
);

CREATE TABLE IF NOT EXISTS skills_catalog_sync_runs (
    id BIGSERIAL PRIMARY KEY,
    run_mode VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL,
    source_count INTEGER DEFAULT 0,
    stats JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_skills_catalog_name
ON skills_catalog(skill_name, source_name);

CREATE INDEX IF NOT EXISTS idx_skills_catalog_status
ON skills_catalog(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_skills_catalog_runs_created
ON skills_catalog_sync_runs(created_at DESC);

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at'
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_trigger WHERE tgname = 'trg_skills_catalog_updated'
    ) THEN
        EXECUTE '
            CREATE TRIGGER trg_skills_catalog_updated
            BEFORE UPDATE ON skills_catalog
            FOR EACH ROW EXECUTE FUNCTION update_updated_at()
        ';
    END IF;
END $$;
