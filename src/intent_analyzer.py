# intent_analyzer.py
from openai import OpenAI
import json
import os
import re 

class IntentAnalyzer:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = "gpt-4o-mini"

    def analyze(self, query: str) -> dict:
        prompt = f"""
        Analyze this insurance-related query to determine its intent.

        Consider carefully:
        1. Does it ask for comparison with other policies or insurers?
        2. Does it ask about features that might not be in user's policy?
        3. Does it need external information beyond policy documents?

        Respond with JSON containing these boolean fields:
        - needs_comparison
        - asks_about_uncovered_features
        - requires_external_info

        Query: "{query}"
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=50
            )
            # Extract the assistant’s text
            raw_content = response.choices[0].message.content
            print("DEBUG: IntentAnalyzer raw response:", response)

            # Remove code fences (```json ... ```)
            cleaned = re.sub(r"^```(?:json)?|```$", "", raw_content.strip(), flags=re.MULTILINE).strip()
            print("CLEANED:", cleaned)

            # Parse the JSON safely
            intent = json.loads(cleaned)
            return intent
        
        except Exception as e:
            print(f"Error analyzing intent: {e}")
            return {
                "needs_comparison": False,
                "asks_about_uncovered_features": False,
                "requires_external_info": False
            }