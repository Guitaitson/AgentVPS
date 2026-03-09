-- /opt/vps-agent/core/init-db.sql
-- Schema inicial para memória do agente

-- Memória estruturada por usuário
CREATE TABLE IF NOT EXISTS agent_memory (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    memory_type VARCHAR(50) NOT NULL,  -- 'fact', 'preference', 'context'
    key VARCHAR(255) NOT NULL,
    value JSONB NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, memory_type, key)
);

-- Memória global do sistema
CREATE TABLE IF NOT EXISTS system_state (
    id SERIAL PRIMARY KEY,
    component VARCHAR(100) NOT NULL UNIQUE,
    state JSONB NOT NULL,
    last_health_check TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Histórico de conversas (para contexto)
CREATE TABLE IF NOT EXISTS conversation_log (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Tarefas agendadas
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id SERIAL PRIMARY KEY,
    task_name VARCHAR(255) NOT NULL,
    task_type VARCHAR(50) NOT NULL,  -- 'cron', 'once', 'recurring'
    schedule VARCHAR(100),  -- cron expression ou timestamp
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'running', 'done', 'failed'
    last_run TIMESTAMP WITH TIME ZONE,
    next_run TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Skills aprendidas pelo agente
CREATE TABLE IF NOT EXISTS agent_skills (
    id SERIAL PRIMARY KEY,
    skill_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    trigger_pattern VARCHAR(500),  -- regex ou keywords
    execution_steps JSONB NOT NULL,
    success_count INT DEFAULT 0,
    failure_count INT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Catálogo de skills externos (normalizados)
CREATE TABLE IF NOT EXISTS skills_catalog (
    id BIGSERIAL PRIMARY KEY,
    skill_name VARCHAR(255) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    version VARCHAR(100) NOT NULL,
    schema_hash VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'active', -- active, inactive
    pinned BOOLEAN DEFAULT FALSE,
    pinned_version VARCHAR(100),
    pin_reason TEXT,
    pinned_at TIMESTAMP WITH TIME ZONE,
    pinned_by VARCHAR(100),
    last_seen_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(skill_name, source_name)
);

CREATE TABLE IF NOT EXISTS skills_catalog_sync_runs (
    id BIGSERIAL PRIMARY KEY,
    run_mode VARCHAR(20) NOT NULL, -- check, apply
    status VARCHAR(20) NOT NULL, -- success, failed
    source_count INTEGER DEFAULT 0,
    stats JSONB DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS skills_catalog_history (
    id BIGSERIAL PRIMARY KEY,
    skill_name VARCHAR(255) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    version VARCHAR(100) NOT NULL,
    schema_hash VARCHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    change_type VARCHAR(40) NOT NULL,
    changed_by VARCHAR(100) DEFAULT 'sync_engine',
    details JSONB DEFAULT '{}',
    changed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Auditoria de memória tipada (Phase 1)
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

-- Alma do agente (identidade versionada)
CREATE TABLE IF NOT EXISTS agent_soul_artifacts (
    id BIGSERIAL PRIMARY KEY,
    artifact_type VARCHAR(50) NOT NULL, -- core_identity, personal_voice, behavior_contract
    version INTEGER NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_by VARCHAR(100) DEFAULT 'system',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(artifact_type, version)
);

-- Propostas auditáveis de mudança de alma
CREATE TABLE IF NOT EXISTS agent_soul_change_proposals (
    id BIGSERIAL PRIMARY KEY,
    artifact_type VARCHAR(50) NOT NULL,
    proposed_content TEXT NOT NULL,
    rationale TEXT NOT NULL,
    impact_level VARCHAR(20) DEFAULT 'medium', -- low, medium, high
    requires_approval BOOLEAN DEFAULT TRUE,
    status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected, applied
    requested_by VARCHAR(100) DEFAULT 'system',
    reviewer VARCHAR(100),
    review_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    applied_at TIMESTAMP WITH TIME ZONE
);

-- Índices para performance
CREATE INDEX idx_memory_user ON agent_memory(user_id, memory_type);
CREATE INDEX idx_memory_key ON agent_memory(key);
CREATE INDEX idx_conversation_user ON conversation_log(user_id, created_at DESC);
CREATE INDEX idx_tasks_status ON scheduled_tasks(status, next_run);
CREATE INDEX idx_skills_trigger ON agent_skills(trigger_pattern);
CREATE INDEX idx_skills_catalog_name ON skills_catalog(skill_name, source_name);
CREATE INDEX idx_skills_catalog_status ON skills_catalog(status, updated_at DESC);
CREATE INDEX idx_skills_catalog_runs_created ON skills_catalog_sync_runs(created_at DESC);
CREATE INDEX idx_skills_catalog_history_name ON skills_catalog_history(skill_name, source_name, changed_at DESC);
CREATE INDEX idx_memory_audit_ts ON memory_audit_log(event_ts DESC);
CREATE INDEX idx_memory_audit_user ON memory_audit_log(user_id, event_ts DESC);
CREATE INDEX idx_soul_artifact_type_version ON agent_soul_artifacts(artifact_type, version DESC);
CREATE INDEX idx_soul_proposals_status ON agent_soul_change_proposals(status, created_at DESC);

-- Função para auto-update do updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_memory_updated
    BEFORE UPDATE ON agent_memory
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_state_updated
    BEFORE UPDATE ON system_state
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_skills_updated
    BEFORE UPDATE ON agent_skills
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_skills_catalog_updated
    BEFORE UPDATE ON skills_catalog
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Capacidades do agente (Self-Improvement)
CREATE TABLE IF NOT EXISTS agent_capabilities (
    id SERIAL PRIMARY KEY,
    capability_name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT NOT NULL,
    category VARCHAR(50) NOT NULL,
    implemented BOOLEAN DEFAULT FALSE,
    implementation_path VARCHAR(500),
    dependencies JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    implemented_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Histórico de implementações de capacidades
CREATE TABLE IF NOT EXISTS capability_implementations (
    id SERIAL PRIMARY KEY,
    capability_name VARCHAR(255) NOT NULL,
    implementation_plan TEXT NOT NULL,
    generated_code TEXT,
    status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'in_progress', 'completed', 'failed'
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Índices para capacidades
CREATE INDEX idx_capabilities_name ON agent_capabilities(capability_name);
CREATE INDEX idx_capabilities_category ON agent_capabilities(category);
CREATE INDEX idx_capabilities_implemented ON agent_capabilities(implemented);
CREATE INDEX idx_implementations_status ON capability_implementations(status);
CREATE INDEX idx_implementations_capability ON capability_implementations(capability_name);

-- Trigger para update de capabilities
CREATE TRIGGER trg_capabilities_updated
    BEFORE UPDATE ON agent_capabilities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
