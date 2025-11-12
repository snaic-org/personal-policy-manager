import os
from pathlib import Path
from typing import List, Tuple, Dict, Any
import re
from docx import Document
from dotenv import load_dotenv
from .pdf_extractor import extract_pages_with_azure

load_dotenv()


class FileHandler:
    """Handles processing of various document formats."""

    def __init__(self, **kwargs):
        # --- NEW: Load Azure credentials ---
        self.azure_endpoint = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT")
        self.azure_key = os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY")

        if not self.azure_endpoint or not self.azure_key:
            raise ValueError("Azure credentials not found in .env file")

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
            # --- NEW: This block is now much simpler ---
            if file_path.suffix.lower() == ".pdf":
                # Call your new Azure worker function
                page_texts = extract_pages_with_azure(
                    str(file_path), self.azure_endpoint, self.azure_key
                )
            elif file_path.suffix.lower() == ".docx":
                page_texts = self._extract_docx_text(file_path)
            elif file_path.suffix.lower() in [".txt", ".md"]:
                page_texts = self._extract_text_file(file_path)
            else:
                print(f"Unsupported file format: {file_path.suffix}")
                return [], []
            # --- END NEW BLOCK ---

            if not page_texts:
                print(f"No text extracted from {file_path.name}")
                return [], []

            # --- START: Insurance-Aware Metadata Logic (This is unchanged) ---
            # This logic is now applied to the *clean* Azure output

            INSURER_PLAN_KEYWORDS = {
                "GREAT_SupremeHealth_Benefits.pdf": re.compile(
                    r"\b(P PLUS|P PRIME|A PLUS|B PLUS|STANDARD|GREAT TotalCare)\b",
                    re.IGNORECASE,
                ),
                "SINGLIFE_TRAVEL_POLICY.pdf": re.compile(
                    r"\b(Prestige|Plus|Lite)\b", re.IGNORECASE
                ),
                "Manulife_Policy_Illustration_REDACTED.pdf": re.compile(
                    r"(Critical Care Enhancer|Total and Permanent Disability Plus Rider)",
                    re.IGNORECASE,
                ),
            }

            filename = file_path.name
            plan_regex = INSURER_PLAN_KEYWORDS.get(filename)
            # --- END: Insurance-Aware Metadata Logic ---

            all_chunks = []
            all_metadata = []

            # This loop now iterates over the clean page data from Azure
            for page_info in page_texts:
                page_num = page_info["page_num"]
                page_content = page_info["text"]

                if not page_content.strip():
                    continue

                # Your strategy: one chunk per page
                chunk = page_content

                # Extract page heading
                heading_match = re.search(
                    r"^\s*(#{1,3})\s*(.+)$", page_content, re.MULTILINE
                )

                # --- NEW: Use table headers as headings if no markdown header ---
                table_header_match = re.search(
                    r"^\s*\|(.+)\|", page_content, re.MULTILINE
                )

                if heading_match:
                    page_heading = heading_match.group(2).strip()
                elif table_header_match:
                    # Use the first table's header as the heading
                    page_heading = (
                        table_header_match.group(1).split("|")[0].strip()
                    )  # Get first column name
                else:
                    first_line = next(
                        (line for line in page_content.split("\n") if line.strip()),
                        f"Page {page_num}",
                    )
                    page_heading = first_line.strip()

                # --- START: Smart Metadata Population (This is unchanged) ---
                found_plans = []
                if plan_regex:
                    found_plans = list(set(plan_regex.findall(page_content)))

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
                        normalized_plans.append(plan)
                # --- END: Smart Metadata Population ---

                all_metadata.append(
                    {
                        "source": str(file_path),
                        "filename": file_path.name,
                        "page_number": page_num,
                        "page_heading": page_heading,
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
            import traceback

            traceback.print_exc()
            return [], []

    # --- We no longer need the old PDF extractors ---
    # def _extract_pdf_text_pymupdf4llm(self, file_path: Path) -> List[Dict]: ...
    # def _extract_pdf_text_fallback(self, file_path: Path) -> List[Dict]: ...
    # (You can delete them)

    def _extract_docx_text(self, file_path: Path) -> List[Dict]:
        """Extract text from DOCX file."""
        page_texts = []
        try:
            doc = Document(file_path)
            full_text = ""
            for paragraph in doc.paragraphs:
                full_text += paragraph.text + "\n"
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
            page_texts.append({"page_num": 1, "text": self._clean_text(text)})
            return page_texts
        except Exception as e:
            print(f"Error reading text file {file_path.name}: {e}")
            return []

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
        text = re.sub(r" +", " ", text)
        text = re.sub(r"\t+", " ", text)
        text = re.sub(r"\*\*\s*\*\*", "", text)
        text = re.sub(r"_{2,}", "", text)
        text = self._remove_email_signature(text)
        return text.strip()

    def _remove_email_signature(self, text: str) -> str:
        """Remove common email signature closings"""
        signature_regex = re.compile(
            r"(?m)(?:\n|\A)\s*(?:Best regards,|Best Regards,|Regards,|Sincerely,|Kind regards,|Kind Regards,|Yours sincerely,|Yours faithfully,|Thanks,|Thank you,|Thank you for your time,?)\s*(?:\n[^\n]{0,120})?(?:\n[^\n]{0,120})?\s*\Z",
            flags=re.IGNORECASE,
        )
        new_text = signature_regex.sub("\n", text)
        new_text = re.sub(r"(?m)^\s*\[?Your Name\]?\s*$", "\n", new_text)
        return new_text.rstrip()
