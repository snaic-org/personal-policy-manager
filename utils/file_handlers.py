# utils/file_handlers.py

"""
File Handlers
Handles processing of different document formats (PDF, DOCX, TXT, MD).
Uses pymupdf4llm for robust PDF text extraction with better table handling.
"""

import os
from pathlib import Path
from typing import List, Tuple, Dict, Any
import re
from docx import Document


class FileHandler:
    """Handles processing of various document formats."""

    def __init__(self, **kwargs):
        # chunk_size and chunk_overlap are no longer needed here
        pass

    def process_document(
        self, file_path: str
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Process a document and return chunks with metadata."""
        file_path = Path(file_path)

        if not file_path.exists():
            print(f"File not found: {file_path}")
            return [], []

        # Extract text based on file type
        try:
            if file_path.suffix.lower() == ".pdf":
                page_texts = self._extract_pdf_text_pymupdf4llm(file_path)
            elif file_path.suffix.lower() == ".docx":
                page_texts = self._extract_docx_text(file_path)
            elif file_path.suffix.lower() in [".txt", ".md"]:
                page_texts = self._extract_text_file(file_path)
            else:
                print(f"Unsupported file format: {file_path.suffix}")
                return [], []

            if not page_texts:
                print(f"No text extracted from {file_path.name}")
                return [], []

            # --- START: New Insurance-Aware Metadata Logic ---

            # Define plan keywords specific to each insurer.
            # We use \b for word boundaries (e.g., \bP PLUS\b) to ensure
            # "P PLUS" doesn't accidentally match "P PRIME".
            INSURER_PLAN_KEYWORDS = {
                # Great Eastern: Tiers from the benefits table
                "GREAT_SupremeHealth_Benefits.pdf": re.compile(
                    r"\b(P PLUS|P PRIME|A PLUS|B PLUS|STANDARD|GREAT TotalCare)\b",
                    re.IGNORECASE,
                ),
                # Singlife: Tiers from the summary of cover
                "SINGLIFE_TRAVEL_POLICY.pdf": re.compile(
                    r"\b(Prestige|Plus|Lite)\b", re.IGNORECASE
                ),
                # Manulife: This plan has no tiers, but we can tag riders.
                "Manulife_Policy_Illustration_REDACTED.pdf": re.compile(
                    r"(Critical Care Enhancer|Total and Permanent Disability Plus Rider)",
                    re.IGNORECASE,
                ),
            }

            # Get the correct regex for the file being processed
            filename = file_path.name
            plan_regex = INSURER_PLAN_KEYWORDS.get(filename)

            # --- END: New Insurance-Aware Metadata Logic ---

            all_chunks = []
            all_metadata = []

            for page_info in page_texts:
                page_num = page_info["page_num"]
                page_content = page_info["text"]

                if not page_content.strip():
                    continue  # Skip empty pages

                chunk = page_content

                # Extract page heading (your existing logic)
                heading_match = re.search(
                    r"^\s*(#{1,3})\s*(.+)$", page_content, re.MULTILINE
                )
                if heading_match:
                    page_heading = heading_match.group(2).strip()
                else:
                    first_line = next(
                        (line for line in page_content.split("\n") if line.strip()),
                        f"Page {page_num}",
                    )
                    page_heading = first_line.strip()

                # --- START: New Metadata Population Logic ---
                found_plans = []
                if plan_regex:
                    # Scan the page content for any plan keywords
                    # Use set() to get only unique matches
                    found_plans = list(set(plan_regex.findall(page_content)))

                # Normalize found keywords to a consistent case for matching
                # This ensures "p plus" and "P PLUS" are treated the same.
                normalized_plans = []
                for plan in found_plans:
                    if "p plus" in plan.lower():
                        normalized_plans.append("P PLUS")
                    elif "p prime" in plan.lower():
                        normalized_plans.append("P PRIME")
                    elif "a plus" in plan.lower():
                        normalized_plans.append("A PLUS")
                    elif "b plus" in plan.lower():
                        normalized_plans.append("B PLUS")
                    elif "great totalcare" in plan.lower():
                        normalized_plans.append("GREAT TotalCare")
                    elif "prestige" in plan.lower():
                        normalized_plans.append("Prestige")
                    elif "plus" in plan.lower():
                        normalized_plans.append("Plus")
                    elif "lite" in plan.lower():
                        normalized_plans.append("Lite")
                    elif "standard" in plan.lower():
                        normalized_plans.append("STANDARD")
                    elif "critical care" in plan.lower():
                        normalized_plans.append("Critical Care Enhancer")
                    elif "total and permanent disability" in plan.lower():
                        normalized_plans.append(
                            "Total and Permanent Disability Plus Rider"
                        )
                    else:
                        normalized_plans.append(plan)  # Fallback

                # --- END: New Metadata Population Logic ---

                all_metadata.append(
                    {
                        "source": str(file_path),
                        "filename": file_path.name,
                        "page_number": page_num,
                        "page_heading": page_heading,
                        # Use the new normalized list, ensuring uniqueness
                        "plan_context": list(
                            set(normalized_plans)
                        ),  # <-- THE ENHANCED METADATA
                        "chunk_id": f"p{page_num}-0",
                        "chunk_size": len(chunk),
                        "file_type": file_path.suffix.lower(),
                    }
                )
                all_chunks.append(chunk)

            return all_chunks, all_metadata

        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            return [], []

    def _extract_pdf_text_pymupdf4llm(self, file_path: Path) -> List[Dict]:
        """
        Extract text from PDF, guaranteeing one chunk per page.
        Iterates pages with fitz and converts each page to markdown.
        """
        page_texts = []
        try:
            import fitz  # PyMuPDF
            import pymupdf4llm  # We still use it for the cleaning logic if needed

            doc = fitz.open(file_path)

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Use the built-in markdown converter for the single page
                # This is more robust for page-by-page splitting
                page_md_text = page.get_text("markdown")

                if page_md_text.strip():
                    cleaned_text = self._clean_text(page_md_text)
                    page_texts.append({"page_num": page_num + 1, "text": cleaned_text})

            doc.close()

            if not page_texts:
                # Fallback if markdown extract fails
                print(
                    f"Markdown extraction produced no text, trying fallback for {file_path.name}"
                )
                return self._extract_pdf_text_fallback(file_path)

            return page_texts

        except Exception as e:
            print(f"pymupdf4llm/fitz failed for {file_path.name}: {e}")
            # Fallback to basic PyMuPDF
            return self._extract_pdf_text_fallback(file_path)

        except Exception as e:
            print(f"pymupdf4llm failed for {file_path.name}: {e}")
            # Fallback to basic PyMuPDF
            return self._extract_pdf_text_fallback(file_path)

    def _extract_pdf_text_fallback(self, file_path: Path) -> List[Dict]:
        """Fallback PDF extraction using basic PyMuPDF."""
        page_texts = []
        try:
            import fitz  # PyMuPDF

            doc = fitz.open(file_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()

                # Try to extract tables
                try:
                    tables = page.find_tables()
                    table_text = ""
                    for table in tables:
                        df = table.to_pandas()
                        table_text += "\n\n" + df.to_string(index=False)
                    text += table_text
                except:
                    pass

                page_texts.append(
                    {"page_num": page_num + 1, "text": self._clean_text(text)}
                )

            doc.close()
            return page_texts

        except Exception as e:
            print(f"Fallback PDF extraction failed for {file_path.name}: {e}")
            return []

    def _extract_docx_text(self, file_path: Path) -> List[Dict]:
        """Extract text from DOCX file."""
        page_texts = []
        try:
            doc = Document(file_path)
            full_text = ""
            for paragraph in doc.paragraphs:
                full_text += paragraph.text + "\n"

            # DOCX has no concept of pages, so we treat it as one page
            page_texts.append({"page_num": 1, "text": self._clean_text(full_text)})
            return page_texts
        except Exception as e:
            print(f"Error reading DOCX {file_path.name}: {e}")
            return []

    def _extract_text_file(self, file_path: Path) -> List[Dict]:
        """Extract text from TXT or MD file."""
        page_texts = []
        try:
            with open(file_path, "r", encoding="utf-8") as file:
                text = file.read()

            # Treat as one page
            page_texts.append({"page_num": 1, "text": self._clean_text(text)})
            return page_texts
        except Exception as e:
            print(f"Error reading text file {file_path.name}: {e}")
            return []

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove excessive newlines but keep structure
        text = re.sub(
            r"\n\s*\n\s*\n+", "\n\n", text
        )  # Multiple newlines -> double newline
        text = re.sub(r" +", " ", text)  # Multiple spaces -> single space
        text = re.sub(r"\t+", " ", text)  # Tabs -> spaces

        # Clean up common markdown artifacts from pymupdf4llm
        text = re.sub(r"\*\*\s*\*\*", "", text)  # Empty bold markers
        text = re.sub(r"_{2,}", "", text)  # Multiple underscores

        # Remove common email/signature blocks to avoid copying them into chunks
        text = self._remove_email_signature(text)

        return text.strip()

    def _remove_email_signature(self, text: str) -> str:
        """Remove common email signature closings (e.g., "Best regards, [Name]")

        This targets short signature blocks that commonly appear at the end of
        pages or extracted text. It is intentionally conservative to avoid
        removing legitimate policy content.
        """
        # Pattern: a closing like 'Best regards,' possibly followed by a name or
        # up to two short lines. Only remove when it appears near the end of the
        # given text block.
        signature_regex = re.compile(
            r"(?m)(?:\n|\A)\s*(?:Best regards,|Best Regards,|Regards,|Sincerely,|Kind regards,|Kind Regards,|Yours sincerely,|Yours faithfully,|Thanks,|Thank you,|Thank you for your time,?)\s*(?:\n[^\n]{0,120})?(?:\n[^\n]{0,120})?\s*\Z",
            flags=re.IGNORECASE,
        )

        new_text = signature_regex.sub("\n", text)

        # Remove placeholder signatures like '[Your Name]' alone on a line
        new_text = re.sub(r"(?m)^\s*\[?Your Name\]?\s*$", "\n", new_text)

        # Collapse trailing whitespace/newlines
        return new_text.rstrip()

    def _extract_year_from_filename(self, filename: str) -> int:
        """Extract year from filename."""
        match = re.search(r"(\d{4})", filename)  # Look for 4-digit year
        if match:
            year = int(match.group(1))
            if 1900 <= year <= 2100:  # Reasonable year range
                return year

        # Fallback: look for 2-digit year
        match = re.search(r"(\d{2})", filename)
        if match:
            year = int(match.group(1))
            if year < 100:
                year += 2000  # Assume 20xx
                return year
        return None

    # This function is no longer used by process_document
    def _create_chunks(self, text: str) -> List[str]:
        """Split text into chunks with overlap."""
        if len(text) <= 1000:  # You can set a reasonable small size
            return [text]

        # This logic is now a fallback for very large pages
        print(
            "Warning: Page content is very large, falling back to fixed chunking for this page."
        )
        chunk_size = 2000
        chunk_overlap = 200
        chunks = []
        start = 0

        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)

            move = chunk_size - chunk_overlap
            start += move

            # Ensure last chunk captures the end
            if start + chunk_size > len(text) and start < len(text):
                chunks.append(text[start:])
                break

        return [c.strip() for c in chunks if c.strip()]
