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
        
        # Quick checks first (before calling API)
        if not response or len(response.strip()) < 50:
            print("📊 Quality Check: ❌ Response too short")
            return False
        
        # Check for common "I don't know" phrases
        dont_know_phrases = [
            "i couldn't find",
            "no relevant information",
            "i don't have information",
            "unable to find",
            "not available in",
            "couldn't locate"
        ]
        
        response_lower = response.lower()
        if any(phrase in response_lower for phrase in dont_know_phrases):
            print("📊 Quality Check: ❌ Contains 'don't know' phrase")
            return False
        
        # Now use LLM for deeper analysis
        analysis_prompt = f"""You are a quality checker for insurance chatbot responses.

    USER QUESTION: {query}

    BOT RESPONSE: {response}

    USER'S POLICIES: {json.dumps(user_profile.get("insurance_policies", {}) if user_profile else {}, indent=2)}

    Analyze if the response:
    1. **Directly answers** the user's specific question
    2. **Provides concrete details** (dollar amounts, percentages, policy names)
    3. **Uses information** from the user's actual policies
    4. **Doesn't deflect** with vague statements like "may be covered" or "it depends"
    5. **Is complete** - user wouldn't need to ask a follow-up to get the core answer

    Respond with ONLY ONE WORD:
    - "GOOD" if the response adequately answers the question
    - "BAD" if it's insufficient and needs deep research

    Examples of GOOD responses:
    - "Your deductible is $3,500 [Source 1: ...]"
    - "You are NOT covered due to exclusion: [specific exclusion]"
    - "You'll receive $500,000 lump sum [Source 2: ...]"

    Examples of BAD responses:
    - "You may have coverage depending on your policy"
    - "I couldn't find specific information about..."
    - "Your policy should cover this" (no specifics)
    - "Please check with your insurer" (deflecting)

    ONE WORD ONLY:"""
        
        try:
            result = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Cheaper/faster model
                messages=[{"role": "user", "content": analysis_prompt}],
                max_tokens=10,
                temperature=0
            )
            
            verdict = result.choices[0].message.content.strip().upper()
            is_good = "GOOD" in verdict
            
            print(f"📊 Response Quality Check: {'✅ GOOD - Answer is sufficient' if is_good else '❌ BAD - Triggering deep research'}")
            
            return is_good
            
        except Exception as e:
            print(f"⚠️ Analysis failed: {e}. Assuming response is GOOD (safe default).")
            return True  # Default to accepting response if analysis fails