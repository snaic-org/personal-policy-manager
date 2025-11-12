from azure.ai.formrecognizer import DocumentAnalysisClient
from azure.core.credentials import AzureKeyCredential
import sys
from pathlib import Path
import re
import os
from dotenv import load_dotenv
import fitz

load_dotenv()


def _clean_text(text: str) -> str:
    """Simple text cleaner."""
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r" +", " ", text)
    return text.strip()


def table_to_markdown(table):
    """Convert Azure table object to markdown with better cell handling."""
    if table.row_count == 0 or table.column_count == 0:
        return ""

    # Create a 2D array to hold cell contents
    grid = [["" for _ in range(table.column_count)] for _ in range(table.row_count)]

    # Fill the grid with cell contents, handling merged cells
    for cell in table.cells:
        content = cell.content.strip() if cell.content else ""

        # Handle cells that span multiple columns
        if cell.column_span and cell.column_span > 1:
            for col_offset in range(cell.column_span):
                if cell.column_index + col_offset < table.column_count:
                    grid[cell.row_index][cell.column_index + col_offset] = (
                        content if col_offset == 0 else ""
                    )
        else:
            grid[cell.row_index][cell.column_index] = content

    # Convert to markdown
    lines = []
    lines.append("| " + " | ".join(grid[0]) + " |")
    lines.append("| " + " | ".join(["---"] * table.column_count) + " |")

    for row in grid[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def split_pdf(pdf_path, chunk_size=15):
    """Split PDF into chunks to avoid page limits."""
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    chunks = []

    for start_page in range(0, total_pages, chunk_size):
        end_page = min(start_page + chunk_size, total_pages)

        # Create new PDF with chunk
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page - 1)

        # Convert to bytes
        pdf_bytes = new_doc.tobytes()
        chunks.append(
            {
                "bytes": pdf_bytes,
                "start_page": start_page + 1,
                "end_page": end_page,
                "page_count": end_page - start_page,
            }
        )

        new_doc.close()

    doc.close()
    return chunks


def read_pdf_with_azure(file_path, endpoint, key, use_chunking=True):
    """Extract PDF content using Azure Document Intelligence."""
    print(f"Reading PDF file: {file_path}")
    pdf_path = Path(file_path)

    if not pdf_path.exists():
        print(f"Error: File not found at '{file_path}'")
        return

    if pdf_path.suffix.lower() != ".pdf":
        print(f"Error: File '{file_path}' is not a PDF.")
        return

    # Check original page count
    doc = fitz.open(pdf_path)
    original_page_count = len(doc)
    doc.close()

    print(f"[INFO] PDF has {original_page_count} pages")

    client = DocumentAnalysisClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    try:
        if use_chunking and original_page_count > 15:
            print(
                f"[INFO] Splitting PDF into chunks (15 pages each) to avoid Free tier limits..."
            )
            chunks = split_pdf(pdf_path, chunk_size=2)
            print(f"[INFO] Created {len(chunks)} chunks")

            page_offset = 0

            for chunk_num, chunk in enumerate(chunks, 1):
                print(f"\n{'=' * 60}")
                print(
                    f"Processing Chunk {chunk_num}/{len(chunks)} (Pages {chunk['start_page']}-{chunk['end_page']})"
                )
                print(f"{'=' * 60}")

                poller = client.begin_analyze_document(
                    model_id="prebuilt-layout", document=chunk["bytes"]
                )

                result = poller.result()

                # Process each page in this chunk
                for page_num in range(len(result.pages)):
                    actual_page_num = page_offset + page_num + 1
                    page = result.pages[page_num]
                    print(f"\n--- Page {actual_page_num} ---")

                    # Get tables on this page
                    tables_on_page = [
                        table
                        for table in result.tables
                        if any(
                            region.page_number == page_num + 1
                            for cell in table.cells
                            for region in cell.bounding_regions
                        )
                    ]

                    if tables_on_page:
                        print(f"Found {len(tables_on_page)} table(s) on this page\n")

                        for i, table in enumerate(tables_on_page, 1):
                            print(f"Table {i}:")
                            markdown_table = table_to_markdown(table)
                            print(markdown_table)
                            print()
                    else:
                        # No tables, extract text
                        paragraphs_on_page = [
                            para
                            for para in result.paragraphs
                            if para.bounding_regions[0].page_number == page_num + 1
                        ]

                        if paragraphs_on_page:
                            text_parts = [para.content for para in paragraphs_on_page]
                            text = "\n".join(text_parts)
                            text = _clean_text(text)
                            print(text)

                page_offset += len(result.pages)

        else:
            # Process entire PDF at once
            print("Uploading to Azure Document Intelligence...")

            with open(pdf_path, "rb") as f:
                file_content = f.read()

            print("Analyzing document...")

            poller = client.begin_analyze_document(
                model_id="prebuilt-layout", document=file_content
            )

            result = poller.result()

            print(f"Successfully analyzed. Document has {len(result.pages)} pages.")

            # Process each page
            for page_num in range(len(result.pages)):
                page = result.pages[page_num]
                print(f"\n--- Page {page_num + 1} ---")

                # Get tables on this page
                tables_on_page = [
                    table
                    for table in result.tables
                    if any(
                        region.page_number == page_num + 1
                        for cell in table.cells
                        for region in cell.bounding_regions
                    )
                ]

                if tables_on_page:
                    print(f"Found {len(tables_on_page)} table(s) on this page\n")

                    for i, table in enumerate(tables_on_page, 1):
                        print(f"Table {i}:")
                        markdown_table = table_to_markdown(table)
                        print(markdown_table)
                        print()
                else:
                    # No tables, extract text
                    paragraphs_on_page = [
                        para
                        for para in result.paragraphs
                        if para.bounding_regions[0].page_number == page_num + 1
                    ]

                    if paragraphs_on_page:
                        text_parts = [para.content for para in paragraphs_on_page]
                        text = "\n".join(text_parts)
                        text = _clean_text(text)
                        print(text)

        print(f"\n--- Finished reading {file_path} ---")

    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    AZURE_ENDPOINT = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
    AZURE_KEY = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

    if not AZURE_ENDPOINT or not AZURE_KEY:
        print("Error: Azure credentials not found in .env file")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Error: You must provide a file path as an argument.")
        print("Example: python data_ingestion.py /path/to/your/file.pdf")
    else:
        read_pdf_with_azure(sys.argv[1], AZURE_ENDPOINT, AZURE_KEY, use_chunking=True)
