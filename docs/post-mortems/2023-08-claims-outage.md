# Post-Mortem: Claims Service Outage
**Date**: August 14, 2023  
**Duration**: 23 minutes  
**Severity**: SEV-1 (Revenue impact: $180K potential claims delayed)

## Summary
Claims processing pipeline experienced cascading failure due to Redis cluster 
node exhaustion during flash flood event in Texas (10K+ simultaneous claims).

## Timeline (UTC)
- 14:32: Redis memory usage alert triggered (85%)
- 14:35: Claims API latency spikes to 8s (normal: &lt;100ms)
- 14:38: Kubernetes HPA scales claims-service to 50 pods (max)
- 14:40: Redis cluster enters read-only mode (memory maxed)
- 14:45: Claims submission queue backs up (2K pending)
- 14:50: PagerDuty alert to on-call engineer
- 14:55: Manual failover to backup Redis cluster
- 15:15: Service fully restored, queue draining

## Root Cause
1. **Insufficient memory headroom**: Redis configured with 16GB, no eviction policy
2. **Thundering herd**: All 50 claims-service pods reconnected simultaneously after HPA scale-up
3. **Missing circuit breaker**: No fallback to degraded mode when Redis unavailable

## Resolution
- Immediate: Failover to hot standby Redis cluster in us-west-2
- Short-term: Implemented Redis Cluster with 32GB nodes + allkeys-lru eviction
- Long-term: Added circuit breaker pattern (Hystrix) to fail open on cache miss

## Lessons Learned
- **Cache is not optional**: Claims service should function (slowly) without Redis
- **Regional disasters require multi-region**: Texas flood = localized traffic spike
- **HPA can amplify problems**: Scaling up increased Redis connection count exponentially

## Action Items
- [ ] Implement cache-aside pattern with DB fallback (Owner: @sarah-chen, Due: 08/21)
- [ ] Add Redis memory alerts at 70% threshold (Owner: @devops-team, Due: 08/16)
- [ ] Load test with 20K concurrent claims (Owner: @qa-team, Due: 08/30)
