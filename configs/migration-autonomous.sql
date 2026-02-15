-- Migration T4-01: Autonomous Blueprint Schema
-- Adiciona tabelas para proposals, missions e policies do agente autônomo

-- ============================================================
-- TABELAS AUTONOMOUS (T4-01)
-- ============================================================

-- Proposals: ações sugeridas pelo agente autônomo
CREATE TABLE IF NOT EXISTS agent_proposals (
    id SERIAL PRIMARY KEY,
    trigger_name VARCHAR(100) NOT NULL,
    condition_data JSONB NOT NULL,
    suggested_action JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    -- Status: pending, approved, rejected, executing, completed, failed
    priority INTEGER DEFAULT 5,
    -- Priority: 1 (highest) to 10 (lowest)
    requires_approval BOOLEAN DEFAULT FALSE,
    approval_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    executed_at TIMESTAMP WITH TIME ZONE
);

-- Missions: execução de proposals aprovadas
CREATE TABLE IF NOT EXISTS agent_missions (
    id SERIAL PRIMARY KEY,
    proposal_id INTEGER REFERENCES agent_proposals(id),
    mission_type VARCHAR(50) NOT NULL,
    -- mission_type: ram_cleanup, container_restart, backup, health_check
    execution_plan JSONB NOT NULL,
    status VARCHAR(20) DEFAULT 'pending',
    -- Status: pending, running, completed, failed
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Policies: regras de governança do agente autônomo
CREATE TABLE IF NOT EXISTS agent_policies (
    id SERIAL PRIMARY KEY,
    policy_name VARCHAR(100) NOT NULL UNIQUE,
    policy_type VARCHAR(50) NOT NULL,
    -- policy_type: resource_limit, security, rate_limit, approval_required
    config JSONB NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- ============================================================
-- ÍNDICES
-- ============================================================

CREATE INDEX idx_proposals_status ON agent_proposals(status, created_at DESC);
CREATE INDEX idx_proposals_trigger ON agent_proposals(trigger_name);
CREATE INDEX idx_missions_proposal ON agent_missions(proposal_id);
CREATE INDEX idx_missions_status ON agent_missions(status);
CREATE INDEX idx_policies_type ON agent_policies(policy_type);
CREATE INDEX idx_policies_enabled ON agent_policies(enabled);

-- ============================================================
-- POLICIES INICIAIS
-- ============================================================

INSERT INTO agent_policies (policy_name, policy_type, config, enabled, description)
VALUES
    ('max_proposals_per_hour', 'rate_limit', '{"max_count": 10, "window_seconds": 3600}', TRUE, 'Limita proposals por hora'),
    ('ram_threshold', 'resource_limit', '{"min_free_mb": 200}', TRUE, 'RAM mínima disponível'),
    ('dangerous_action_approval', 'approval_required', '{"actions": ["systemctl", "rm -rf", "kill"]}', TRUE, 'Ações perigosas requerem aprovação'),
    ('container_action_approval', 'approval_required', '{"actions": ["docker stop", "docker rm"]}', TRUE, 'Container actions requerem aprovação')
ON CONFLICT (policy_name) DO NOTHING;

-- ============================================================
-- TRIGGERS
-- ============================================================

CREATE TRIGGER trg_proposals_updated
    BEFORE UPDATE ON agent_proposals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_policies_updated
    BEFORE UPDATE ON agent_policies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
