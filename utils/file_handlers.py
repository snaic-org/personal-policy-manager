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

    def __init__(self, chunk_size: int = 2000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

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

            # Create chunks and metadata
            all_chunks = []
            all_metadata = []

            for page_info in page_texts:
                page_num = page_info["page_num"]
                page_content = page_info["text"]

                # Create chunks for this page's content
                chunks = self._create_chunks(page_content)

                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    all_metadata.append(
                        {
                            "source": str(file_path),
                            "filename": file_path.name,
                            "page_number": page_num,
                            "year": self._extract_year_from_filename(file_path.name),
                            "chunk_id": f"p{page_num}-{i}",
                            "chunk_size": len(chunk),
                            "file_type": file_path.suffix.lower(),
                        }
                    )

            return all_chunks, all_metadata

        except Exception as e:
            print(f"Error processing {file_path.name}: {e}")
            return [], []

    def _extract_pdf_text_pymupdf4llm(self, file_path: Path) -> List[Dict]:
        """Extract text from PDF using pymupdf4llm (optimized for LLMs)."""
        page_texts = []
        try:
            import pymupdf4llm

            # Extract markdown-formatted text (handles tables well)
            md_text = pymupdf4llm.to_markdown(str(file_path))

            # Split by pages (pymupdf4llm includes page markers)
            pages = md_text.split("\n-----\n")  # Default page separator

            for page_num, page_content in enumerate(pages, 1):
                if page_content.strip():  # Skip empty pages
                    cleaned_text = self._clean_text(page_content)
                    page_texts.append({"page_num": page_num, "text": cleaned_text})

            # If no page separators found, treat as single page
            if len(pages) == 1:
                cleaned_text = self._clean_text(md_text)
                page_texts = [{"page_num": 1, "text": cleaned_text}]

            return page_texts

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

        return text.strip()

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

    def _create_chunks(self, text: str) -> List[str]:
        """Split text into chunks with overlap."""
        if len(text) <= self.chunk_size:
            return [text]

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)

            move = self.chunk_size - self.chunk_overlap
            start += move

            # Ensure last chunk captures the end
            if start + self.chunk_size > len(text) and start < len(text):
                chunks.append(text[start:])
                break

        return [c.strip() for c in chunks if c.strip()]
