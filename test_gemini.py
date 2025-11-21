import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv

# Load .env where your GOOGLE_API_KEY should be
load_dotenv()

# Configure the API
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))


async def test_gemini_flash():
    print("--- Testing Gemini Flash ---")

    # Initialize Model
    # Note: "Gemini 2.5" isn't public yet. You likely mean "gemini-1.5-flash"
    # or the new experimental "gemini-2.0-flash-exp".
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash", system_instruction="You are a helpful assistant."
    )

    # 1. Test Standard Generation
    print("\n1. Testing Standard Response:")
    response = await model.generate_content_async(
        "Explain how a RAG pipeline works in one sentence."
    )
    print(f"Response: {response.text}")

    # 2. Test Streaming (Crucial for your UI)
    print("\n2. Testing Streaming Response:")
    # Note: Gemini async streaming syntax is slightly different
    async for chunk in await model.generate_content_async("Count to 5.", stream=True):
        print(f"Chunk: {chunk.text}", end=" | ")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(test_gemini_flash())
