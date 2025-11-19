# intent_analyzer.py
from openai import OpenAI
import json
import os
import re 
from typing import List, Dict, Any, Optional

class ResponseAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"
    def _analyze_response_quality(
        self, 
        query: str, 
        response: str, 
        user_profile: Optional[Dict]
    ) -> bool:
        """
        Checks if the RAG response adequately answered the question.
        Returns True if good, False if needs deep research.
        """
        
        # Quick checks first
        if not response or len(response.strip()) < 50:
            print("📊 Quality Check: ❌ Response too short")
            return False
        
        # ===== EXPANDED: More comprehensive checks =====
        
        # 1. Explicit "don't know" phrases
        dont_know_phrases = [
            "i couldn't find",
            "no relevant information",
            "i don't have information",
            "unable to find",
            "not available in",
            "couldn't locate",
            "amount not found",  # ← You have this in your responses!
            "were not found in the provided documents"  # ← And this!
        ]
        
        response_lower = response.lower()
        if any(phrase in response_lower for phrase in dont_know_phrases):
            print(f"📊 Quality Check: ❌ Contains 'don't know' phrase")
            return False
        
        # 2. Deflecting phrases (NEW!)
        deflecting_phrases = [
            "would require details",
            "you should evaluate",
            "you should consider",
            "it's advisable to review",
            "you may want to refer",
            "you may want to contact",
            "consult with an insurance advisor",
            "contact your insurance provider",
            "for more details, please",
            "ultimately, the decision should be based on",
            "considerations for",
            "factors to consider"
        ]
        
        if any(phrase in response_lower for phrase in deflecting_phrases):
            print(f"📊 Quality Check: ❌ Deflecting - not answering directly")
            return False
        
        # 3. Vague comparison language (NEW!)
        vague_comparison_phrases = [
            "typically aligns with",
            "generally similar to",
            "comparable to industry standards",
            "typical offerings",
            "industry standard often includes",
            "similar to what's available"
        ]
        
        # Only check if query is asking for comparison
        is_comparison_query = any(word in query.lower() for word in ['compare', 'comparison', 'versus', 'vs', 'better than', 'switch'])
        
        if is_comparison_query and any(phrase in response_lower for phrase in vague_comparison_phrases):
            print(f"📊 Quality Check: ❌ Vague comparison without data")
            return False
        
        # 4. Check for citations (important!)
        import re
        has_source_citation = bool(re.search(r'\[Source \d+:', response))
        has_profile_citation = '<USER PROFILE>' in response
        
        # For factual questions, we need citations
        is_factual_query = any(word in query.lower() for word in ['how much', 'what is', 'do i have', 'am i covered', 'does my'])
        
        if is_factual_query and not (has_source_citation or has_profile_citation):
            print("📊 Quality Check: ❌ Factual query but missing citations")
            return False
        
        # ===== END EXPANDED CHECKS =====
        
        # Now use LLM for deeper analysis
        analysis_prompt = f"""You are a strict quality checker for insurance chatbot responses.

    USER QUESTION: {query}

    BOT RESPONSE: {response}

    Check if the response ACTUALLY ANSWERS the question with SPECIFIC information:

    ❌ BAD Examples:
    - "You should evaluate if X offers better coverage..." (deflecting)
    - "Typically aligns with industry standards" (vague, no data)
    - "Would require details of their current offerings" (admitting ignorance)
    - "Considerations for switching: Compare coverage..." (generic advice, not specific answer)
    - "For more details, contact your provider" (deflecting)

    ✅ GOOD Examples:
    - "Your deductible is $3,500 [Source 1]"
    - "AIA HealthShield Gold Max has a $3,000 deductible vs your $3,500" (actual comparison)
    - "Industry average CI coverage is $250k, yours is $500k, which is above average" (specific data)

    Respond with ONLY ONE WORD: "GOOD" or "BAD"
    """
        
        try:
            result = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": analysis_prompt}],
                max_tokens=10,
                temperature=0
            )
            
            verdict = result.choices[0].message.content.strip().upper()
            is_good = "GOOD" in verdict
            
            print(f"📊 Response Quality Check (LLM): {'✅ GOOD' if is_good else '❌ BAD - Triggering deep research'}")
            
            return is_good
            
        except Exception as e:
            print(f"⚠️ Analysis failed: {e}. Assuming response is GOOD (safe default).")
            return True
    