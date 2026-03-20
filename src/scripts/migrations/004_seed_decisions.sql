-- 004_seed_decisions.sql
-- Seed realistic decision records for existing submissions, policies, and claims.
-- These cover the five agent decision types used across the platform.

-- Triage decisions
INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-submission', 'gpt-5.1', '0.1.0', 'triage',
    '{"entity_id":"seed-sub-001","entity_type":"submission","applicant":"Acme Cyber Corp","industry":"technology"}',
    '{"entity_id":"seed-sub-001","entity_type":"submission"}',
    '{"appetite_match":"yes","risk_score":32,"priority":"medium","confidence":0.92}',
    'Low risk profile; IT sector with strong security posture and no prior incidents.',
    0.92,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -120, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-submission', 'gpt-5.1', '0.1.0', 'triage',
    '{"entity_id":"seed-sub-002","entity_type":"submission","applicant":"GlobalFinance Ltd","industry":"financial_services"}',
    '{"entity_id":"seed-sub-002","entity_type":"submission"}',
    '{"appetite_match":"yes","risk_score":58,"priority":"high","confidence":0.78}',
    'Financial services firm with elevated risk due to high revenue band and complex IT environment.',
    0.78,
    '{"human_override":true,"override_reason":"Senior UW approved after additional documentation review.","level":"required"}',
    DATEADD(day, -95, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-submission', 'gpt-5.1', '0.1.0', 'triage',
    '{"entity_id":"seed-sub-003","entity_type":"submission","applicant":"SecureHealth Systems","industry":"healthcare"}',
    '{"entity_id":"seed-sub-003","entity_type":"submission"}',
    '{"appetite_match":"yes","risk_score":45,"priority":"medium","confidence":0.88}',
    'Healthcare vertical within appetite; moderate risk with adequate security controls.',
    0.88,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -400, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-submission', 'gpt-5.1', '0.1.0', 'triage',
    '{"entity_id":"seed-sub-004","entity_type":"submission","applicant":"RetailMart Inc","industry":"retail"}',
    '{"entity_id":"seed-sub-004","entity_type":"submission"}',
    '{"appetite_match":"no","risk_score":78,"priority":"low","confidence":0.94}',
    'Retail sector outside current cyber appetite; high incident history.',
    0.94,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -60, GETUTCDATE()));

-- Underwriting / pricing decisions
INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-underwriting', 'gpt-5.1', '0.1.0', 'underwriting',
    '{"entity_id":"seed-sub-001","entity_type":"submission","revenue":8000000,"employees":120}',
    '{"entity_id":"seed-sub-001","entity_type":"submission"}',
    '{"risk_score":35,"recommended_premium":12500,"confidence":0.85,"conditions":["annual pen test"]}',
    'Standard rating for mid-market tech company; annual penetration test required.',
    0.85,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -119, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-underwriting', 'gpt-5.1', '0.1.0', 'underwriting',
    '{"entity_id":"seed-sub-002","entity_type":"submission","revenue":50000000,"employees":850}',
    '{"entity_id":"seed-sub-002","entity_type":"submission"}',
    '{"risk_score":58,"recommended_premium":45000,"confidence":0.72,"conditions":["SOC2 required","board-level reporting"]}',
    'Higher revenue band triggers senior underwriter review; SOC2 compliance mandatory.',
    0.72,
    '{"human_override":true,"override_reason":"Premium adjusted to $42,000 after senior review.","level":"required"}',
    DATEADD(day, -94, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-underwriting', 'gpt-5.1', '0.1.0', 'underwriting',
    '{"entity_id":"seed-sub-003","entity_type":"submission","revenue":15000000,"employees":300}',
    '{"entity_id":"seed-sub-003","entity_type":"submission"}',
    '{"risk_score":42,"recommended_premium":18750,"confidence":0.91,"conditions":[]}',
    'Healthcare mid-market with HIPAA compliance in place. Standard terms apply.',
    0.91,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -398, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-underwriting', 'gpt-5.1', '1.0.0', 'pricing',
    '{"entity_id":"seed-sub-005","entity_type":"submission","revenue":3500000,"employees":45}',
    '{"entity_id":"seed-sub-005","entity_type":"submission"}',
    '{"premium":5250,"currency":"USD","rate_per_1000":1.50,"confidence":0.95}',
    'Small-market tech company; standard base rate applies with no adjustments.',
    0.95,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -730, GETUTCDATE()));

-- Policy review decisions
INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-policy', 'gpt-5.1', '0.1.0', 'policy_review',
    '{"entity_id":"seed-sub-001","entity_type":"submission","policy_number":"POL-2024-A1B2C3"}',
    '{"entity_id":"seed-sub-001","entity_type":"submission"}',
    '{"recommendation":"issue","coverage_adequate":true,"terms_complete":true,"confidence":0.93}',
    'All coverage terms verified. Premium within guidelines. Recommend issuance.',
    0.93,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -118, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-policy', 'gpt-5.1', '0.1.0', 'policy_review',
    '{"entity_id":"seed-sub-002","entity_type":"submission","policy_number":"POL-2024-D4E5F6"}',
    '{"entity_id":"seed-sub-002","entity_type":"submission"}',
    '{"recommendation":"refer","coverage_adequate":true,"terms_complete":false,"confidence":0.68}',
    'Coverage adequate but terms incomplete; missing cyber extortion sublimit specification.',
    0.68,
    '{"human_override":true,"override_reason":"Terms completed manually; sublimit added at $500K.","level":"required"}',
    DATEADD(day, -93, GETUTCDATE()));

-- Claims assessment decisions
INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-claims', 'gpt-5.1', '0.1.0', 'claims',
    '{"entity_id":"seed-clm-001","entity_type":"claim","claim_type":"data_breach","severity":"high"}',
    '{"entity_id":"seed-clm-001","entity_type":"claim"}',
    '{"coverage_confirmed":true,"severity_tier":"complex","initial_reserve":150000,"fraud_score":0.05,"confidence":0.85}',
    'High-severity data breach with regulatory exposure. Reserve set for notification costs, forensics, and legal.',
    0.85,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -45, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-claims', 'gpt-5.1', '0.1.0', 'claims',
    '{"entity_id":"seed-clm-002","entity_type":"claim","claim_type":"ransomware","severity":"critical"}',
    '{"entity_id":"seed-clm-002","entity_type":"claim"}',
    '{"coverage_confirmed":true,"severity_tier":"catastrophe","initial_reserve":500000,"fraud_score":0.08,"confidence":0.79}',
    'Ransomware attack with business interruption. Catastrophe tier due to extended downtime and recovery costs.',
    0.79,
    '{"human_override":true,"override_reason":"Reserve increased to $750K after forensics report.","level":"required"}',
    DATEADD(day, -200, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-claims', 'gpt-5.1', '0.1.0', 'claims',
    '{"entity_id":"seed-clm-003","entity_type":"claim","claim_type":"social_engineering","severity":"moderate"}',
    '{"entity_id":"seed-clm-003","entity_type":"claim"}',
    '{"coverage_confirmed":true,"severity_tier":"moderate","initial_reserve":45000,"fraud_score":0.12,"confidence":0.91}',
    'Social engineering wire transfer. Moderate severity; limited to single transaction amount.',
    0.91,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -800, GETUTCDATE()));

-- Fraud detection decisions
INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-claims', 'gpt-5.1', '0.2.0', 'fraud_detection',
    '{"entity_id":"seed-clm-002","entity_type":"claim","claim_type":"ransomware","amount":500000}',
    '{"entity_id":"seed-clm-002","entity_type":"claim"}',
    '{"fraud_score":0.08,"flag":false,"indicators":[],"confidence":0.93}',
    'Low fraud indicators — ransomware attack consistent with known threat actor patterns and incident timeline.',
    0.93,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -198, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-claims', 'gpt-5.1', '0.2.0', 'fraud_detection',
    '{"entity_id":"seed-clm-004","entity_type":"claim","claim_type":"data_breach","amount":85000}',
    '{"entity_id":"seed-clm-004","entity_type":"claim"}',
    '{"fraud_score":0.67,"flag":true,"indicators":["late_reporting","inconsistent_timeline"],"confidence":0.74}',
    'Elevated fraud score due to late reporting (45 days post-incident) and inconsistent timeline details.',
    0.74,
    '{"human_override":false,"override_reason":null,"level":"required"}',
    DATEADD(day, -30, GETUTCDATE()));

-- Compliance audit decisions
INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-compliance', 'gpt-5.1', '0.1.0', 'compliance_audit',
    '{"entity_id":"seed-sub-001","entity_type":"submission","workflow":"new_business"}',
    '{"entity_id":"seed-sub-001","entity_type":"submission"}',
    '{"compliant":true,"issues":[],"articles_checked":["Art.12","Art.13","Art.14"],"confidence":0.96}',
    'Full EU AI Act compliance verified. All transparency and oversight requirements met.',
    0.96,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -117, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-compliance', 'gpt-5.1', '0.1.0', 'compliance_audit',
    '{"entity_id":"seed-clm-001","entity_type":"claim","workflow":"claims_assessment"}',
    '{"entity_id":"seed-clm-001","entity_type":"claim"}',
    '{"compliant":true,"issues":["minor: explainability documentation incomplete"],"articles_checked":["Art.12","Art.13","Art.14"],"confidence":0.87}',
    'Mostly compliant; minor gap in explainability documentation for reserve calculation.',
    0.87,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -44, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-compliance', 'gpt-5.1', '0.1.0', 'compliance_audit',
    '{"entity_id":"seed-sub-003","entity_type":"submission","workflow":"new_business"}',
    '{"entity_id":"seed-sub-003","entity_type":"submission"}',
    '{"compliant":true,"issues":[],"articles_checked":["Art.12","Art.13","Art.14"],"confidence":0.94}',
    'Healthcare submission fully compliant. HIPAA-aligned data handling verified.',
    0.94,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -395, GETUTCDATE()));

-- Orchestration decisions
INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-orchestrator', 'gpt-5.1', '0.1.0', 'orchestration',
    '{"entity_id":"seed-sub-001","entity_type":"submission","workflow":"new_business"}',
    '{"entity_id":"seed-sub-001","entity_type":"submission"}',
    '{"processing_path":"standard","priority":"medium","confidence":0.90}',
    'Standard processing path for mid-market tech submission with no escalation triggers.',
    0.90,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -121, GETUTCDATE()));

INSERT INTO decision_records (id, agent_id, model_used, model_version, decision_type,
    input_summary, data_sources_used, output_data, reasoning, confidence, human_oversight, created_at)
VALUES (NEWID(), 'openinsure-orchestrator', 'gpt-5.1', '0.1.0', 'orchestration',
    '{"entity_id":"seed-clm-002","entity_type":"claim","workflow":"claims_assessment"}',
    '{"entity_id":"seed-clm-002","entity_type":"claim"}',
    '{"investigation_priority":"urgent","fraud_flag":false,"confidence":0.82}',
    'Urgent priority due to ransomware severity and active business interruption.',
    0.82,
    '{"human_override":false,"override_reason":null,"level":"recommended"}',
    DATEADD(day, -201, GETUTCDATE()));
