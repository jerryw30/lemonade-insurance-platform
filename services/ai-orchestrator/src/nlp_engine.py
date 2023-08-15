"""
AI Orchestration Service
Powers Maya (onboarding) and Jim (claims) conversational agents
Uses transformer-based NLP with insurance-specific fine-tuning
"""

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from typing import List, Dict, Optional
import json
from dataclasses import dataclass

@dataclass
class ConversationContext:
    user_id: str
    session_id: str
    intent_history: List[str]
    extracted_entities: Dict
    current_flow: str  # 'onboarding', 'claims', 'support'

class InsuranceNLP:
    """
    Fine-tuned transformer model for insurance conversations.
    Trained on 10M+ customer interactions.
    """
    
    def __init__(self):
        # Load fine-tuned model (DistilBERT base, fine-tuned on insurance corpus)
        self.tokenizer = AutoTokenizer.from_pretrained('lemonade/insurance-nlp-v3')
        self.intent_model = AutoModelForSequenceClassification.from_pretrained(
            'lemonade/insurance-nlp-v3'
        )
        self.entity_extractor = InsuranceEntityExtractor()
        
        # Intent classes
        self.intents = [
            'get_quote', 'file_claim', 'check_claim_status', 'update_policy',
            'cancel_policy', 'ask_coverage_question', 'billing_question', 
            'emergency_assistance', 'fraudulent_behavior'
        ]
    
    def process_message(self, 
                       message: str, 
                       context: ConversationContext) -> Dict:
        """
        Main entry point for conversational AI.
        Returns intent, entities, response, and next actions.
        """
        
        # 1. Intent Classification
        intent = self.classify_intent(message)
        
        # 2. Entity Extraction (NER)
        entities = self.entity_extractor.extract(message, context.current_flow)
        
        # 3. Context Management
        updated_context = self.update_context(context, intent, entities)
        
        # 4. Response Generation
        response = self.generate_response(intent, entities, updated_context)
        
        # 5. Action Routing
        actions = self.determine_actions(intent, entities)
        
        return {
            'intent': intent,
            'confidence': intent['confidence'],
            'entities': entities,
            'response': response,
            'actions': actions,
            'context': updated_context
        }
    
    def classify_intent(self, message: str) -> Dict:
        """Multi-class intent classification with confidence scoring"""
        inputs = self.tokenizer(
            message, 
            return_tensors="pt", 
            truncation=True, 
            max_length=512
        )
        
        with torch.no_grad():
            outputs = self.intent_model(**inputs)
            probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
            confidence, predicted_class = torch.max(probabilities, dim=-1)
        
        return {
            'intent': self.intents[predicted_class.item()],
            'confidence': confidence.item(),
            'all_probabilities': {
                self.intents[i]: prob.item() 
                for i, prob in enumerate(probabilities[0])
            }
        }
    
    def generate_response(self, 
                         intent: Dict, 
                         entities: Dict, 
                         context: ConversationContext) -> str:
        """
        Dynamic response generation based on conversation state.
        Not template-based—uses retrieval-augmented generation.
        """
        
        # High-confidence, straightforward intents
        if intent['intent'] == 'get_quote' and intent['confidence'] > 0.9:
            if 'property_type' not in entities:
                return "I'd love to help you get a quote! First, are you looking for renters, homeowners, or car insurance?"
            elif 'location' not in entities:
                return f"Got it—{entities['property_type']} insurance. What's your ZIP code?"
            else:
                return self.generate_quote_response(entities)
        
        # Fraud detection trigger
        if intent['intent'] == 'fraudulent_behavior':
            return self.handle_fraudulent_input(context)
        
        # Contextual follow-up
        if context.intent_history[-1:] == ['file_claim'] and 'description' not in entities:
            return "I'm sorry to hear that. Can you describe what happened in a few sentences?"
        
        # Default to retrieval-augmented response
        return self.retrieve_similar_response(message, context)

class InsuranceEntityExtractor:
    """
    Specialized NER for insurance domain.
    Extracts: property types, coverage amounts, dates, locations, policy numbers
    """
    
    def extract(self, text: str, flow_type: str) -> Dict:
        entities = {}
        
        # Regex + ML hybrid approach
        if flow_type == 'onboarding':
            entities.update(self.extract_property_info(text))
            entities.update(self.extract_coverage_needs(text))
        
        elif flow_type == 'claims':
            entities.update(self.extract_incident_details(text))
            entities.update(self.extract_damage_assessment(text))
        
        return entities
    
    def extract_property_info(self, text: str) -> Dict:
        """Extract property type, bedrooms, square footage, etc."""
        # Implementation using spaCy/regex patterns
        pass
    
    def extract_incident_details(self, text: str) -> Dict:
        """Extract date, location, involved parties for claims"""
        pass
