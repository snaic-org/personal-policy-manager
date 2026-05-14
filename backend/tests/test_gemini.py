import os
import asyncio
from google import genai
from dotenv import load_dotenv

# Load .env where your GOOGLE_API_KEY should be
load_dotenv()


async def test_gemini_flash():
    print("--- Testing Gemini Flash ---")

    # Initialize Model
    # Note: "Gemini 2.5" isn't public yet. You likely mean "gemini-1.5-flash"
    # or the new experimental "gemini-2.0-flash-exp".
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


    # 1. Test Standard Generation
    print("\n1. Testing Standard Response:")
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        system_instruction="You are a helpful assistant.",
        contents="Explain how a RAG pipeline works in one sentence."
    )
    print(f"Response: {response.text}")

    # 2. Test Streaming (Crucial for your UI)
    print("\n2. Testing Streaming Response:")
    # Note: Gemini async streaming syntax is slightly different
    async for chunk in await client.aio.models.generate_content_stream(
        model="gemini-2.5-flash",
        system_instruction="You are a helpful assistant.",
        contents="Count to 5."
    ):
        print(f"Chunk: {chunk.text}", end=" | ")
    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(test_gemini_flash())
