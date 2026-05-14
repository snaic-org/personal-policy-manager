import os, sys

# Ensure repo root is on the path before local imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from batch_manager import BatchManager
from query_processor import QueryProcessor


def main():
    batch_id = "user_1"
    query = input("Enter your query: ").strip()
    if not query:
        print("No query provided.")
        return

    bm = BatchManager()
    qp = QueryProcessor(bm)
    answer = qp.process_query(query, batch_id=batch_id, user_profile=None)
    print("\n--- ANSWER ---")
    print(answer)


if __name__ == "__main__":
    main()
