# utils/inspect_batch.py

import argparse
import pickle
import sys
from pathlib import Path


def inspect_batch_chunks(batch_id: str, output_path: str | None = None):
    """
    Loads and inspects the chunks and metadata from a specified batch.
    If output_path is provided, also writes the output to that file.
    """
    lines = []

    def emit(text=""):
        print(text)
        lines.append(text)

    emit(f"--- Inspecting Batch: {batch_id} ---")

    # Path to the FAISS index.pkl file, based on search.py
    # We only need to read one, and the FAISS pkl is a simple dictionary
    index_file = Path(f"batches/{batch_id}/faiss_index/index.pkl")

    if not index_file.exists():
        emit(f"Error: index.pkl not found for batch '{batch_id}'")
        emit(f"Looked at path: {index_file.resolve()}")
        _write_output(output_path, lines)
        return

    try:
        # Load the data from the pickle file
        with open(index_file, "rb") as f:
            data = pickle.load(f)

        chunks = data.get("chunks")
        metadata_list = data.get("metadata")

        if not chunks or not metadata_list:
            emit("Error: 'chunks' or 'metadata' not found in the index file.")
            _write_output(output_path, lines)
            return

        emit(f"Found {len(chunks)} chunks. Displaying details:\n")

        # Loop through each chunk and its metadata
        for i, (chunk, metadata) in enumerate(zip(chunks, metadata_list)):
            emit("=" * 80)
            emit(f"CHUNK {i + 1} / {len(chunks)}")
            emit("=" * 80)

            # Print the metadata in a readable format
            emit(f"METADATA:")
            emit(f"  - Filename: {metadata.get('filename')}")
            emit(f"  - Page: {metadata.get('page_number')}")
            emit(f"  - Heading: {metadata.get('page_heading')}")

            # This is the "smart metadata" we've been working on
            emit(f"  - Plan Context: {metadata.get('plan_context')}")

            # Optional LLM enrichment fields (shown only if present)
            if metadata.get("llm_summary"):
                emit(f"  - LLM Summary: {metadata.get('llm_summary')}")
            if metadata.get("llm_key_entities"):
                emit(f"  - LLM Key Entities: {metadata.get('llm_key_entities')}")
            if metadata.get("llm_likely_questions"):
                emit(
                    f"  - LLM Likely Questions: {metadata.get('llm_likely_questions')}"
                )

            # Print the actual chunk content
            emit("\nCHUNK CONTENT:")
            emit(chunk)
            emit("\n\n")

    except Exception as e:
        emit(f"An error occurred while reading the batch file: {e}")

    _write_output(output_path, lines)


def _write_output(path, lines):
    if not path:
        return
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text("\n".join(lines), encoding="utf-8")
    print(f"\nSaved output to {path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("batch_id", help="Batch ID to inspect")
    parser.add_argument(
        "--output",
        "-o",
        help="Optional path to write the inspection output to a text file",
    )
    args = parser.parse_args()
    inspect_batch_chunks(args.batch_id, args.output)
