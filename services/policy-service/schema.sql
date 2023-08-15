-- Core policy database schema
-- PostgreSQL with partitioning for time-series data

-- Policies table (50M+ rows, partitioned by created_date)
CREATE TABLE policies (
    policy_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    policy_number VARCHAR(20) UNIQUE NOT NULL,
    
    -- Coverage details
    policy_type policy_type_enum NOT NULL, -- 'renters', 'homeowners', 'car', 'pet', 'life'
    coverage_limits JSONB NOT NULL, -- {"personal_property": 30000, "liability": 100000}
    deductible DECIMAL(10,2) NOT NULL,
    premium_amount DECIMAL(10,2) NOT NULL,
    premium_frequency frequency_enum DEFAULT 'monthly',
    
    -- Status tracking
    status policy_status_enum DEFAULT 'pending',
    effective_date TIMESTAMP NOT NULL,
    expiration_date TIMESTAMP NOT NULL,
    cancelled_at TIMESTAMP,
    cancellation_reason TEXT,
    
    -- Risk assessment
    risk_score DECIMAL(3,2), -- 0.00 to 1.00
    underwriting_factors JSONB, -- {"credit_score": 750, "property_age": 5}
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    version INTEGER DEFAULT 1,
    
    -- Constraints
    CONSTRAINT valid_effective_date CHECK (effective_date < expiration_date),
    CONSTRAINT valid_premium CHECK (premium_amount > 0),
    CONSTRAINT valid_deductible CHECK (deductible >= 0)
) PARTITION BY RANGE (effective_date);

-- Create monthly partitions for query performance
CREATE TABLE policies_2024_01 PARTITION OF policies
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
-- ... additional partitions

-- Indexes for common queries
CREATE INDEX idx_policies_user_id ON policies(user_id);
CREATE INDEX idx_policies_status ON policies(status) WHERE status = 'active';
CREATE INDEX idx_policies_expiration ON policies(expiration_date) 
    WHERE status = 'active';
CREATE INDEX idx_policies_gin_underwriting ON policies USING GIN(underwriting_factors);

-- Claims table (100M+ rows, heavy write load)
CREATE TABLE claims (
    claim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_id UUID NOT NULL REFERENCES policies(policy_id),
    user_id UUID NOT NULL,
    
    -- Claim details
    claim_number VARCHAR(20) UNIQUE NOT NULL,
    claim_type claim_type_enum NOT NULL,
    incident_date TIMESTAMP NOT NULL,
    reported_date TIMESTAMP DEFAULT NOW(),
    description TEXT NOT NULL,
    estimated_amount DECIMAL(10,2) NOT NULL,
    final_amount DECIMAL(10,2),
    
    -- Processing
    status claim_status_enum DEFAULT 'submitted',
    approved_at TIMESTAMP,
    approved_by UUID REFERENCES employees(employee_id),
    payout_method payout_method_enum,
    payout_reference VARCHAR(100),
    
    -- AI/ML fields
    fraud_score DECIMAL(3,2),
    ml_confidence DECIMAL(3,2),
    ai_analysis JSONB, -- {"intent": "water_damage", "entities": {...}}
    
    -- Media evidence
    video_evidence_url VARCHAR(500),
    photos JSONB, -- Array of S3 URLs
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP,
    
    -- Constraints
    CONSTRAINT valid_incident_date CHECK (incident_date <= reported_date),
    CONSTRAINT valid_amounts CHECK (estimated_amount > 0 AND final_amount >= 0)
);

-- Partition by reported_date for time-series analysis
PARTITION BY RANGE (reported_date);

-- High-performance indexes
CREATE INDEX idx_claims_policy_id ON claims(policy_id);
CREATE INDEX idx_claims_status_date ON claims(status, reported_date) 
    WHERE status IN ('submitted', 'under_review');
CREATE INDEX idx_claims_fraud_score ON claims(fraud_score) 
    WHERE fraud_score > 0.5;
CREATE INDEX idx_claims_gin_ai ON claims USING GIN(ai_analysis);

-- Fraud signals table (3.7M records/month)
CREATE TABLE fraud_signals (
    signal_id BIGSERIAL PRIMARY KEY,
    claim_id UUID REFERENCES claims(claim_id),
    user_id UUID NOT NULL,
    
    signal_type signal_type_enum NOT NULL,
    -- 'behavioral_biometric', 'device_fingerprint', 'velocity', 'network'
    
    signal_data JSONB NOT NULL,
    risk_contribution DECIMAL(3,2), -- How much this signal contributes to score
    
    created_at TIMESTAMP DEFAULT NOW()
) PARTITION BY HASH (user_id);

-- Sharded across 16 partitions for even write distribution
