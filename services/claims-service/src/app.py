"""
Claims Processing Service
Handles 50K+ claims/month with 40% instant approval rate
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime
import asyncio
import redis
import boto3
from kafka import KafkaProducer
import json
import uuid

app = FastAPI(title="Lemonade Claims Service", version="3.2.0")

# Infrastructure clients
redis_client = redis.Redis(host='redis-cluster.internal', port=6379, decode_responses=True)
kafka_producer = KafkaProducer(
    bootstrap_servers=['kafka-1.internal:9092', 'kafka-2.internal:9092'],
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)
s3_client = boto3.client('s3')
fraud_detection = FraudDetectionClient()  # Internal ML service

class ClaimRequest(BaseModel):
    claim_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    policy_id: str
    user_id: str
    claim_type: Literal["theft", "water_damage", "fire", "liability", "medical"]
    incident_date: datetime
    description: str
    estimated_amount: float = Field(..., gt=0, lt=1000000)
    video_evidence_url: Optional[str] = None
    photos: list[str] = []
    location: dict = Field(..., example={"lat": 40.7128, "lng": -74.0060})
    
    class Config:
        schema_extra = {
            "example": {
                "policy_id": "pol_123456789",
                "user_id": "usr_987654321",
                "claim_type": "water_damage",
                "incident_date": "2024-01-15T14:30:00Z",
                "description": "Pipe burst in kitchen causing floor damage",
                "estimated_amount": 3500.00,
                "video_evidence_url": "s3://lemonade-claims-videos/claim_123.mp4"
            }
        }

class ClaimResponse(BaseModel):
    claim_id: str
    status: Literal["instant_approved", "under_review", "rejected", "flagged"]
    payout_amount: Optional[float] = None
    processing_time_ms: int
    confidence_score: float
    next_steps: str

@app.post("/v1/claims", response_model=ClaimResponse)
async def submit_claim(
    claim: ClaimRequest,
    background_tasks: BackgroundTasks
):
    """
    Main claims submission endpoint.
    40% of claims are approved instantly via ML models.
    Average processing time: 3 seconds.
    """
    start_time = datetime.utcnow()
    
    # 1. Validate policy is active
    policy = await validate_policy(claim.policy_id, claim.user_id)
    if not policy or policy['status'] != 'active':
        raise HTTPException(status_code=400, detail="Invalid or inactive policy")
    
    # 2. Check for duplicate claims (fraud prevention)
    duplicate_check = await check_duplicate_claim(claim)
    if duplicate_check['is_duplicate']:
        return ClaimResponse(
            claim_id=claim.claim_id,
            status="flagged",
            processing_time_ms=get_elapsed_ms(start_time),
            confidence_score=0.0,
            next_steps="Claim flagged for manual review due to similarity to recent claim"
        )
    
    # 3. Real-time fraud scoring (18 ML models)
    fraud_score = await fraud_detection.evaluate(claim)
    
    # 4. Instant approval logic (low risk + low amount + high confidence)
    if (fraud_score['risk_level'] == 'low' and 
        claim.estimated_amount < 5000 and 
        fraud_score['confidence'] > 0.85 and
        claim.claim_type in ['theft', 'water_damage']):
        
        # Instant approval path
        payout_amount = calculate_payout(claim, policy)
        
        # Trigger async payout
        background_tasks.add_task(process_instant_payout, claim, payout_amount)
        
        # Publish event for analytics
        kafka_producer.send('claims.instant_approved', {
            'claim_id': claim.claim_id,
            'amount': payout_amount,
            'fraud_score': fraud_score['score'],
            'timestamp': datetime.utcnow().isoformat()
        })
        
        return ClaimResponse(
            claim_id=claim.claim_id,
            status="instant_approved",
            payout_amount=payout_amount,
            processing_time_ms=get_elapsed_ms(start_time),
            confidence_score=fraud_score['confidence'],
            next_steps="Funds transferred to your account (2-3 business days)"
        )
    
    # 5. Route to human adjuster for complex claims
    background_tasks.add_task(route_to_adjuster, claim, fraud_score)
    
    return ClaimResponse(
        claim_id=claim.claim_id,
        status="under_review",
        processing_time_ms=get_elapsed_ms(start_time),
        confidence_score=fraud_score['confidence'],
        next_steps="A claims specialist will review your case within 24 hours"
    )

async def validate_policy(policy_id: str, user_id: str) -> Optional[dict]:
    """Check policy service for active coverage"""
    # Cache frequently accessed policies
    cache_key = f"policy:{policy_id}"
    cached = redis_client.get(cache_key)
    
    if cached:
        return json.loads(cached)
    
    # Fetch from policy service (async HTTP call)
    # Implementation omitted for brevity
    policy = await fetch_policy_from_service(policy_id)
    
    if policy:
        redis_client.setex(cache_key, 300, json.dumps(policy))  # 5 min TTL
    
    return policy

async def check_duplicate_claim(claim: ClaimRequest) -> dict:
    """
    Check for duplicate submissions within 30 days.
    Uses fuzzy matching on description + location + amount.
    """
    recent_claims_key = f"user_claims:{claim.user_id}:30d"
    recent = redis_client.smembers(recent_claims_key)
    
    for recent_claim_json in recent:
        recent_claim = json.loads(recent_claim_json)
        similarity = calculate_similarity(claim, recent_claim)
        if similarity > 0.85:
            return {"is_duplicate": True, "similarity": similarity}
    
    # Add to recent claims set
    redis_client.sadd(recent_claims_key, claim.json())
    redis_client.expire(recent_claims_key, 2592000)  # 30 days
    
    return {"is_duplicate": False}

def calculate_payout(claim: ClaimRequest, policy: dict) -> float:
    """Calculate payout based on coverage limits and deductibles"""
    coverage_limit = policy['coverage_limits'].get(claim.claim_type, 0)
    deductible = policy['deductible']
    
    payout = min(claim.estimated_amount, coverage_limit) - deductible
    return max(payout, 0)  # Never negative

def get_elapsed_ms(start_time: datetime) -> int:
    return int((datetime.utcnow() - start_time).total_seconds() * 1000)

async def process_instant_payout(claim: ClaimRequest, amount: float):
    """Async task to process bank transfer"""
    # Integration with Stripe/Plaid for instant transfers
    pass

async def route_to_adjuster(claim: ClaimRequest, fraud_score: dict):
    """Route complex claims to human adjusters with full context"""
    # Create ticket in Salesforce/ServiceNow
    pass
