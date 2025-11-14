import os
import json
from typing import Dict, Any, Optional
import google.generativeai as genai
from pydantic import BaseModel
from pydantic import ValidationError

# Initialize Gemini client
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print(f"DEBUG: GEMINI_API Key loaded: {GEMINI_API_KEY[:5]}...{GEMINI_API_KEY[-4:]}")
else:
    print("DEBUG: GEMINI_API Key not found. Gemini queries will fail.")

# --- Function to check if a Gemini model is reachable ---
def is_gemini_model_available(model: str = "gemini-2.0-flash-001") -> bool:
    """Check if Gemini model is available by making a test call."""
    if GEMINI_API_KEY is None:
        print("Gemini client not initialized. Cannot check model.")
        return False
    try:
        # # List available models first (helpful for debugging)
        # available_models = genai.list_models()
        # print("Available Gemini models:")
        # for m in available_models:
        #     if 'generateContent' in m.supported_generation_methods:
        #         print(f"  - {m.name}")
        
        # Create a GenerativeModel instance
        test_model = genai.GenerativeModel(model)
        
        # Do a minimal test with a simple prompt
        response = test_model.generate_content(
            "Hello!",
            generation_config=genai.GenerationConfig(
                max_output_tokens=1
            )
        )
        print(f"Model '{model}' is available.")
        return True
    except Exception as e:
        print(f"Model check failed for '{model}': {e}")
        return False


def parse_response(response_text: Any, schema: type[BaseModel]) -> Optional[BaseModel]:
    """
    Parse Gemini JSON response into the provided Pydantic schema.
    Handles both JSON string and dict.
    """
    try:
        # Convert to dict if it's a string
        if isinstance(response_text, str):
            data = json.loads(response_text)
        elif isinstance(response_text, dict):
            data = response_text
        else:
            print(f"Unknown response type: {type(response_text)}")
            return None
        
        # Create instance of the schema
        return schema(**data)  # <-- instantiate Pydantic model
    except (json.JSONDecodeError, ValidationError, TypeError) as e:
        print(f"Unexpected parse_response error: {e}")
        print(f"Response text was: {response_text}")
        return None



def generate_object(
        system_prompt: str,
        user_prompt: str,
        schema: type[BaseModel],
        model: str = "gemini-2.0-flash-001",
        temperature: float = 0.1,
        max_tokens: int = 4000
) -> Optional[BaseModel]:
    """
    Generate structured object from Gemini using a Pydantic schema.
    """
    if GEMINI_API_KEY is None:
        print("Gemini client not initialized. Cannot generate object.")
        return None

    prompt_text = f"{system_prompt}\n\nUser: {user_prompt}\n\nRespond as JSON matching the schema."
    if hasattr(schema, "model_json_schema"):
        json_schema = schema.model_json_schema()
    elif isinstance(schema, dict):
        json_schema = schema
    else:
        raise TypeError("Schema must be a Pydantic BaseModel class or JSON schema dict")
    
    try:
        # Create GenerativeModel instance
        gemini_model = genai.GenerativeModel(model)

        # Get the JSON schema from the Pydantic model
        # json_schema = schema.model_json_schema()
        
        # Generate content with JSON schema
        response = gemini_model.generate_content(
            prompt_text,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                response_schema=json_schema,  # Pass Pydantic model directly
                temperature=temperature,
                max_output_tokens=max_tokens
            )
        )

        print("DEBUG: Raw Gemini response:", response)
        print("DEBUG: Gemini text:", getattr(response, "text", None))

        # response.text contains JSON
        gemini_text = None
        try:
            gemini_text = response.result.candidates[0].content.parts[0].text
        except Exception:
            print("Could not extract text from Gemini response:", response)
            return None

        return parse_response(gemini_text, schema)
    except Exception as e:
        print(f"Error in generate_object (Gemini): {e}")
        return None


def trim_prompt(text: str, max_length: int = 14000) -> str:
    """
    Trim text to max length while preserving sentences.
    """
    if len(text) <= max_length:
        return text
    last_period = text.rfind('.', 0, max_length)
    if last_period != -1 and last_period > max_length * 0.7:
        return text[:last_period + 1].strip()
    last_newline = text.rfind('\n', 0, max_length)
    if last_newline != -1 and last_newline > max_length * 0.7:
        return text[:last_newline].strip()
    last_space = text.rfind(' ', 0, max_length)
    if last_space != -1:
        return text[:last_space].strip()
    return text[:max_length].strip()