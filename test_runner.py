import json
import os
import sys
import textwrap
from pathlib import Path

# --- START FIX ---
# Add these two lines to load your .env file
from dotenv import load_dotenv

load_dotenv()
# --- END FIX ---

# --- Add project root to path to import our modules ---
project_root = Path(__file__).parent.resolve()
sys.path.append(str(project_root))
# ---

try:
    from query_processor import QueryProcessor
    from batch_manager import BatchManager
except ImportError:
    print("\n--- ERROR ---")
    print("Could not import QueryProcessor or BatchManager.")
    print("Make sure this script is in your project's root directory.")
    print("-------------")
    sys.exit(1)

# --- All 12 Test Questions ---
TEST_QUERIES = [
    # --- Test Case 1 (Multi-Policy) ---
    {
        "name": "Test Case 1: Multi-Policy (Cancer Scenario)",
        "query": "I was just diagnosed with 'Major Cancer' and I'll be getting treatment at a private hospital. How can my Manulife policy help me with my Great Eastern plan's costs?",
    },
    # --- Test Case 2 (Rider Confusion) ---
    {
        "name": "Test Case 2: Rider Confusion (Deductible)",
        "query": "Does my health plan cover my deductible?",
    },
    # --- Test Case 3 (Personalization) ---
    {
        "name": "Test Case 3: Personalization (Public Hospital)",
        "query": "What is my deductible for a public hospital?",
    },
    # --- Test Case 4 (Relevance / Filtering) ---
    {
        "name": "Test Case 4: Relevance (Motorcycle Accident)",
        "query": "I got into a motorcycle accident in Singapore and need to be warded. What am I covered for?",
    },
    # --- Test Case 5 (Benefit Lookup: Health) ---
    {
        "name": "Test Case 5: Benefit Lookup (Stem Cell)",
        "query": "I need a Stem Cell Transplant. What is my coverage for that?",
    },
    # --- Test Case 6 (Benefit Lookup: CI) ---
    {
        "name": "Test Case 6: Benefit Lookup (Angioplasty)",
        "query": "My doctor says I need 'Angioplasty'. Is that covered by my Manulife plan, and if so, how much does it pay?",
    },
    # --- Test Case 7 (Benefit Lookup: Base Life) ---
    {
        "name": "Test Case 7: Benefit Lookup (Death Benefit)",
        "query": "What is the total sum insured for my Manulife policy if I pass away?",
    },
    # --- Test Case 8 (Benefit Lookup: Travel - Specific) ---
    {
        "name": "Test Case 8: Benefit Lookup (Pet Hotel)",
        "query": "I'm on a trip and my cat is in a pet hotel. My flight home was delayed by 24 hours. Does my travel insurance cover the extra day at the pet hotel?",
    },
    # --- Test Case 9 (Benefit Lookup: Travel - Terminology) ---
    {
        "name": "Test Case 9: Benefit Lookup (Rental Car)",
        "query": "I'm renting a car in Spain. Does my Singlife policy cover the rental car's insurance excess?",
    },
    # --- Test Case 10 (Benefit Lookup: Travel - Simple) ---
    {
        "name": "Test Case 10: Benefit Lookup (Bag Delay)",
        "query": "My bag was delayed for 6 hours. How much can I claim?",
    },
    # --- Test Case 11 (Benefit Lookup: Multi-Policy) ---
    {
        "name": "Test Case 11: Benefit Lookup (Dental)",
        "query": "I need 'Accidental Dental Treatment'. Which of my policies covers this?",
    },
    # --- Test Case 12 (Hallucination / Sign-off) ---
    {
        "name": "Test Case 12: Hallucination (Sign-off)",
        "query": "What's my travel insurance tier?",
    },
]


def load_user_profile(profile_path="user_profile.json"):
    """Loads the user_profile.json file."""
    try:
        with open(profile_path, "r") as f:
            profile = json.load(f)
        print(f"Successfully loaded user profile from {profile_path}")
        return profile
    except FileNotFoundError:
        print(f"Error: user_profile.json not found at {profile_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error: user_profile.json is not valid JSON.")
        return None


def main():
    """
    Main function to run the test suite.
    """
    BATCH_ID = "user_1"

    # 1. Load Profile
    user_profile = load_user_profile()
    if not user_profile:
        print("Exiting test runner.")
        return

    # 2. Initialize Query Processor
    try:
        # Initialize BatchManager without the 'registry_path' argument
        batch_manager = BatchManager()

        # Now that load_dotenv() has run, this will find the API key
        query_processor = QueryProcessor(batch_manager)

        # Manually load the batch once
        if not query_processor._ensure_batch_loaded(BATCH_ID):
            print(f"Failed to load batch {BATCH_ID}. Exiting.")
            return
    except Exception as e:
        print(f"Error initializing QueryProcessor: {e}")
        return

    print("\n" + "=" * 80)
    print("STARTING RAG BOT TEST SUITE")
    print("=" * 80 + "\n")

    # 3. Loop through and run all test queries
    for i, test in enumerate(TEST_QUERIES, 1):
        print(f"\n--- TEST {i}/{len(TEST_QUERIES)}: {test['name']} ---")

        query = test["query"]
        print(f"\nQUERY:\n{query}\n")

        try:
            # Use process_query (non-streaming) for test script
            response = query_processor.process_query(
                query, batch_id=BATCH_ID, user_profile=user_profile
            )

            print("BOT RESPONSE:")
            # Use textwrap to format the bot's response nicely
            print(textwrap.indent(response, "  > "))

        except Exception as e:
            print(f"!!! TEST FAILED WITH AN ERROR: {e} !!!")
            import traceback

            traceback.print_exc()

        print("--------------------------------" + "-" * len(test["name"]))

    print("\n" + "=" * 80)
    print("TEST SUITE COMPLETE")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
