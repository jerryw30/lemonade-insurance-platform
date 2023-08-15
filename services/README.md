
# Lemonade Insurance Platform
## AI-First, Mobile-Native Insurance Infrastructure

**Architecture**: Microservices (200+ services) | **Deployment**: AWS EKS | **Mobile**: Native iOS/Android  
**Claim Processing**: 40% instant approval, avg 3 seconds | **Customers**: 2.87M+

---

### Core Philosophy
- Zero paperwork, 100% mobile
- Conversational AI for onboarding (Maya) and claims (Jim)
- Behavioral economics + ML fraud detection
- Giveback program: unclaimed premiums to charity

### Tech Stack Evolution
- **2015-2019**: Ruby on Rails monolith (rapid MVP)
- **2019-2021**: Strangler Fig pattern migration to microservices
- **2021-Present**: Kubernetes-native, event-driven architecture

---

### System Architecture

[Mobile Apps] → [API Gateway (Kong)] → [Microservices Mesh]
                              ↓
                    [Event Bus (Kafka)] → [Data Lake]
                              ↓
                    [ML Platform (SageMaker)] → [Fraud Detection]

### Key Metrics
- 3.7M behavioral signals tracked/month
- 99.9% uptime for claims API
- &lt;100ms API response time (p95)
- 30% customer service automated via CX.AI
