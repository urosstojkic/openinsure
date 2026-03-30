-- =============================================================================
-- Migration 025: Workflow Templates
-- Data-driven workflow definitions: per-product configurable workflow steps
-- instead of hardcoded Python constants.
-- Idempotent: safe to re-run (IF OBJECT_ID ... IS NULL guards).
-- =============================================================================

-- Migration tracking
IF NOT EXISTS (SELECT 1 FROM sys.tables WHERE name = '_migration_history')
CREATE TABLE _migration_history (
    migration_name NVARCHAR(200) NOT NULL UNIQUE,
    applied_at DATETIME2 DEFAULT GETUTCDATE()
);
GO

IF EXISTS (SELECT 1 FROM _migration_history WHERE migration_name = '025_workflow_templates')
BEGIN
    PRINT 'Migration 025_workflow_templates already applied — skipping.';
    RETURN;
END
GO

-- 1. WORKFLOW_TEMPLATES
IF OBJECT_ID('workflow_templates', 'U') IS NULL
CREATE TABLE workflow_templates (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    product_id          UNIQUEIDENTIFIER NULL,
    workflow_type       NVARCHAR(50)     NOT NULL,
    version             INT              DEFAULT 1,
    status              NVARCHAR(20)     DEFAULT 'active',
    description         NVARCHAR(500)    NULL,
    created_at          DATETIME2        DEFAULT GETUTCDATE(),
    updated_at          DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT UQ_workflow_template UNIQUE (product_id, workflow_type, version)
);
GO

-- Index for fast lookup by workflow_type + status
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_workflow_templates_type_status')
CREATE INDEX IX_workflow_templates_type_status
    ON workflow_templates(workflow_type, status)
    INCLUDE (product_id, version);
GO

-- 2. WORKFLOW_STEPS
IF OBJECT_ID('workflow_steps', 'U') IS NULL
CREATE TABLE workflow_steps (
    id                  UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    template_id         UNIQUEIDENTIFIER NOT NULL,
    step_name           NVARCHAR(50)     NOT NULL,
    step_order          INT              NOT NULL,
    agent_name          NVARCHAR(100)    NULL,
    is_parallel         BIT              DEFAULT 0,
    depends_on          NVARCHAR(200)    NULL,
    timeout_seconds     INT              DEFAULT 60,
    is_optional         BIT              DEFAULT 0,
    skip_condition      NVARCHAR(500)    NULL,
    prompt_key          NVARCHAR(100)    NULL,
    created_at          DATETIME2        DEFAULT GETUTCDATE(),
    CONSTRAINT FK_workflow_steps_template FOREIGN KEY (template_id)
        REFERENCES workflow_templates(id) ON DELETE CASCADE,
    CONSTRAINT UQ_workflow_step_order UNIQUE (template_id, step_order)
);
GO

-- Index for fast step retrieval by template
IF NOT EXISTS (SELECT 1 FROM sys.indexes WHERE name = 'IX_workflow_steps_template')
CREATE INDEX IX_workflow_steps_template
    ON workflow_steps(template_id)
    INCLUDE (step_order, step_name, agent_name);
GO

-- =============================================================================
-- 3. SEED DEFAULT WORKFLOWS (product_id = NULL means default/fallback)
-- =============================================================================

-- 3a. Default 'new_business' workflow (5 steps)
IF NOT EXISTS (SELECT 1 FROM workflow_templates WHERE product_id IS NULL AND workflow_type = 'new_business')
BEGIN
    DECLARE @nb_id UNIQUEIDENTIFIER = NEWID();
    INSERT INTO workflow_templates (id, product_id, workflow_type, version, status, description)
    VALUES (@nb_id, NULL, 'new_business', 1, 'active', 'Default new business submission workflow');

    INSERT INTO workflow_steps (template_id, step_name, step_order, agent_name, is_parallel, depends_on, timeout_seconds, is_optional, skip_condition, prompt_key)
    VALUES
        (@nb_id, 'orchestration',  1, 'openinsure-orchestrator', 0, NULL,             60, 0, NULL, 'new_business_orchestration'),
        (@nb_id, 'enrichment',     2, 'openinsure-enrichment',   0, 'orchestration',  60, 1, NULL, 'new_business_enrichment'),
        (@nb_id, 'intake',         3, 'openinsure-submission',   0, 'orchestration',  60, 0, NULL, 'new_business_intake'),
        (@nb_id, 'underwriting',   4, 'openinsure-underwriting', 0, 'intake',         60, 0, 'intake.appetite_match == ''yes''', 'new_business_underwriting'),
        (@nb_id, 'compliance',     5, 'openinsure-compliance',   0, 'intake,underwriting', 60, 0, NULL, 'new_business_compliance');
END
GO

-- 3b. Default 'claims' workflow (3 steps)
IF NOT EXISTS (SELECT 1 FROM workflow_templates WHERE product_id IS NULL AND workflow_type = 'claims')
BEGIN
    DECLARE @cl_id UNIQUEIDENTIFIER = NEWID();
    INSERT INTO workflow_templates (id, product_id, workflow_type, version, status, description)
    VALUES (@cl_id, NULL, 'claims', 1, 'active', 'Default claims assessment workflow');

    INSERT INTO workflow_steps (template_id, step_name, step_order, agent_name, is_parallel, depends_on, timeout_seconds, is_optional, skip_condition, prompt_key)
    VALUES
        (@cl_id, 'orchestration',  1, 'openinsure-orchestrator', 0, NULL,             60, 0, NULL, 'claims_orchestration'),
        (@cl_id, 'assessment',     2, 'openinsure-claims',       0, 'orchestration',  60, 0, NULL, 'claims_assessment'),
        (@cl_id, 'compliance',     3, 'openinsure-compliance',   0, 'orchestration,assessment', 60, 0, NULL, 'claims_compliance');
END
GO

-- 3c. Default 'renewal' workflow (4 steps)
IF NOT EXISTS (SELECT 1 FROM workflow_templates WHERE product_id IS NULL AND workflow_type = 'renewal')
BEGIN
    DECLARE @rn_id UNIQUEIDENTIFIER = NEWID();
    INSERT INTO workflow_templates (id, product_id, workflow_type, version, status, description)
    VALUES (@rn_id, NULL, 'renewal', 1, 'active', 'Default renewal assessment workflow');

    INSERT INTO workflow_steps (template_id, step_name, step_order, agent_name, is_parallel, depends_on, timeout_seconds, is_optional, skip_condition, prompt_key)
    VALUES
        (@rn_id, 'orchestration',  1, 'openinsure-orchestrator',  0, NULL,             60, 0, NULL, 'renewal_orchestration'),
        (@rn_id, 'assessment',     2, 'openinsure-underwriting',  0, 'orchestration',  60, 0, NULL, 'renewal_assessment'),
        (@rn_id, 'policy_review',  3, 'openinsure-policy',        0, 'assessment',     60, 0, NULL, 'renewal_policy_review'),
        (@rn_id, 'compliance',     4, 'openinsure-compliance',    0, 'assessment,policy_review', 60, 0, NULL, 'renewal_compliance');
END
GO

-- Record migration
INSERT INTO _migration_history (migration_name) VALUES ('025_workflow_templates');
GO

PRINT 'Migration 025_workflow_templates applied successfully.';
GO
