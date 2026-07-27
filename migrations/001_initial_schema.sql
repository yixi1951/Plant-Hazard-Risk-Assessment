-- ============================================================
-- 智农 · 数据库 Schema v1
-- 适用于 PostgreSQL（SQLite 由 SQLAlchemy 自动建表）
-- ============================================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(64) NOT NULL UNIQUE,
    email           VARCHAR(128) NOT NULL UNIQUE,
    password_hash   VARCHAR(256) NOT NULL,
    role            VARCHAR(16) NOT NULL DEFAULT 'assessor'
                        CHECK (role IN ('admin', 'assessor', 'readonly')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- 评估记录表
CREATE TABLE IF NOT EXISTS assessments (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER REFERENCES users(id),
    case_id             VARCHAR(64) UNIQUE,
    input_filename      VARCHAR(256),
    input_source        VARCHAR(32) CHECK (input_source IN ('upload', 'url', 'batch', 'api')),
    disease_name        VARCHAR(128),
    disease_id          INTEGER,
    crop                VARCHAR(64),
    severity            VARCHAR(16) CHECK (severity IN ('健康', '一般', '严重')),
    severity_idx        INTEGER CHECK (severity_idx IN (0, 1, 2)),
    risk_score          REAL CHECK (risk_score >= 0 AND risk_score <= 100),
    risk_tier           VARCHAR(16) CHECK (risk_tier IN ('低', '中', '高')),
    disease_confidence  REAL CHECK (disease_confidence >= 0 AND disease_confidence <= 1),
    severity_confidence REAL CHECK (severity_confidence >= 0 AND severity_confidence <= 1),
    suggestion          TEXT,
    responsible_person  VARCHAR(64),
    deadline_days       INTEGER,
    report_path         VARCHAR(256),
    demo                BOOLEAN NOT NULL DEFAULT FALSE,
    model_version       VARCHAR(32),
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_assessments_user_id ON assessments(user_id);
CREATE INDEX idx_assessments_risk_tier ON assessments(risk_tier);
CREATE INDEX idx_assessments_created_at ON assessments(created_at);

-- 风险规则表
CREATE TABLE IF NOT EXISTS risk_rules (
    id                  SERIAL PRIMARY KEY,
    rule_key            VARCHAR(64) NOT NULL UNIQUE,
    description         VARCHAR(256),
    severity_idx_min    INTEGER,
    confidence_min      REAL,
    risk_score_min      REAL,
    risk_tier           VARCHAR(16) NOT NULL CHECK (risk_tier IN ('低', '中', '高')),
    suggestion_template TEXT,
    default_responsible VARCHAR(64),
    default_deadline_days INTEGER,
    priority            INTEGER NOT NULL DEFAULT 0,
    is_active           BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP NOT NULL DEFAULT NOW()
);

-- 风险规则版本表（审计追溯）
CREATE TABLE IF NOT EXISTS risk_rule_versions (
    id              SERIAL PRIMARY KEY,
    rule_id         INTEGER NOT NULL,
    rule_key        VARCHAR(64) NOT NULL,
    previous_config TEXT,
    new_config      TEXT NOT NULL,
    changed_by      INTEGER REFERENCES users(id),
    change_reason   VARCHAR(256),
    version         INTEGER NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_risk_rule_versions_rule_id ON risk_rule_versions(rule_id);

-- 灾害记录表
CREATE TABLE IF NOT EXISTS hazard_records (
    id              SERIAL PRIMARY KEY,
    assessment_id   INTEGER REFERENCES assessments(id),
    crop            VARCHAR(64),
    disease_name    VARCHAR(128),
    severity        VARCHAR(16),
    region          VARCHAR(128),
    field_id        VARCHAR(64),
    affected_area   REAL,
    estimated_loss  REAL,
    action_taken    TEXT,
    status          VARCHAR(16) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'resolved', 'monitoring')),
    reported_by     INTEGER REFERENCES users(id),
    occurred_at     TIMESTAMP,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_hazard_records_crop ON hazard_records(crop);
CREATE INDEX idx_hazard_records_status ON hazard_records(status);

-- 审计日志表
CREATE TABLE IF NOT EXISTS audit_logs (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER REFERENCES users(id),
    username        VARCHAR(64),
    action          VARCHAR(64) NOT NULL,
    resource_type   VARCHAR(64) NOT NULL,
    resource_id     VARCHAR(64),
    detail          TEXT,
    ip_address      VARCHAR(45),
    request_id      VARCHAR(64),
    created_at      TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_resource_type ON audit_logs(resource_type);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);

-- ============================================================
-- 初始风险规则种子数据
-- ============================================================
INSERT INTO risk_rules (rule_key, description, severity_idx_min, confidence_min, risk_score_min, risk_tier, suggestion_template, default_responsible, default_deadline_days, priority) VALUES
('high_severity', '严重病害 + 高置信度 → 高风险', 2, 0.80, 75.0, '高', null, '植保站技术员', 1, 10),
('medium_severity', '一般病害 + 中高置信度 → 中风险', 1, 0.70, 45.0, '中', null, '田间管理人员', 3, 20),
('low_severity', '轻度病害或低置信度 → 低风险', 0, 0.0, 0.0, '低', null, '巡检人员', 7, 30),
('healthy', '健康状态 → 低风险（常规管理）', 0, 0.85, 0.0, '低', null, '巡检人员', 7, 5)
ON CONFLICT (rule_key) DO NOTHING;

-- ============================================================
-- 初始管理员账号（密码需通过应用层设置）
-- ============================================================
INSERT INTO users (username, email, password_hash, role)
VALUES ('admin', 'admin@zhinong.local', '$2b$12$placeholder-change-via-app', 'admin')
ON CONFLICT (username) DO NOTHING;
