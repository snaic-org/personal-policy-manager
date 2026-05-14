# utils/test_ingestion.py
from .file_handlers import FileHandler


def main():
    # Path to a PDF you want to test (relative to project root)
    pdf_path = "documents/user_1/GREAT_SupremeHealth_Benefits.pdf"

    handler = FileHandler()

    print(f"Ingesting {pdf_path} with LLM enrichment enabled...")
    chunks, metadata = handler.process_document(pdf_path, enrich_with_llm=True)

    print(f"\nTotal chunks: {len(chunks)}")

    # Show all chunks that came from page 2
    print("\n=== CHUNKS FOR PAGE 2 ===")
    for i, (chunk_text, meta) in enumerate(zip(chunks, metadata)):
        if meta["page_number"] != 2:
            continue

        print("\n" + "=" * 80)
        print(f"Chunk index in list: {i}  (chunk_id: {meta['chunk_id']})")
        print("=" * 80)
        print("TEXT PREVIEW:")
        print(chunk_text[:800])
        if len(chunk_text) > 800:
            print("...")

        print("\nMETADATA:")
        for k, v in meta.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
