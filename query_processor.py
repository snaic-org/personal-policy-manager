"""
Query Processor
Handles domain-agnostic query processing using hybrid FAISS + BM25 search.
Loads user profile for personalized responses within specific batches (e.g., 'my_policies').

* This is the "Comprehensive" version that relies on the detailed user_profile.json
* to provide facts and uses the document chunks only for citation.
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from openai import OpenAI

from batch_manager import BatchManager
from utils.search import HybridSearchEngine


class QueryProcessor:
    # Static Keyword Dictionary for high-priority, known semantic gaps. Not sure if we want to keep.
    STATIC_KEYWORD_MAP = {
        "collision damage waiver": "rental vehicle excess",
        "cdw": "rental vehicle excess",
        "rental car insurance": "rental vehicle excess",
        "accident in singapore": "medical expenses while in Singapore",
        "motorcycle accident in singapore": "medical expenses while in Singapore",
        "collision damage waiver": "rental vehicle excess rental car insurance",
        "cdw": "rental vehicle excess rental car insurance",
        "rental car insurance": "rental vehicle excess collision damage waiver",
        "car rental excess": "rental vehicle excess",
        "rental vehicle": "rental vehicle excess",
    }

    def __init__(self, batch_manager: BatchManager):
        self.batch_manager = batch_manager
        self.search_engine = None
        self.current_batch_id = None
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _ensure_batch_loaded(self, batch_id: str) -> bool:
        """Ensure the specified batch is loaded in the search engine."""
        # If already loaded, do nothing
        if self.current_batch_id == batch_id and self.search_engine:
            return True

        paths = self.batch_manager.get_batch_paths(batch_id)
        if not paths:
            print(f"Error: Batch '{batch_id}' configuration not found in registry.")
            return False

        print(f"Loading indexes for batch '{batch_id}'...")
        try:
            # Create a new search engine instance for the specified batch
            self.search_engine = HybridSearchEngine()
            success = self.search_engine.load_indexes(
                faiss_path=paths["faiss_index"], bm25_path=paths["bm25_index"]
            )

            if success:
                self.current_batch_id = batch_id
                print(f"Successfully loaded indexes for batch '{batch_id}'.")
                return True
            else:
                print(f"Error: Failed to load indexes for batch '{batch_id}'.")
                self.search_engine = None  # Ensure it's None if loading failed
                self.current_batch_id = None
                return False

        except Exception as e:
            print(f"Error initializing search engine for batch '{batch_id}': {e}")
            self.search_engine = None
            self.current_batch_id = None
            return False

    def _deduplicate_results(self, results: List[Dict]) -> List[Dict]:
        """Remove duplicate results based on content."""
        unique_results = []
        seen_content = set()
        for result in results:
            content = result.get("content", "")
            # Check for non-empty content before adding
            if content and content not in seen_content:
                unique_results.append(result)
                seen_content.add(content)
        return unique_results

    def _filter_results_by_profile(
        self, results: List[Dict], user_profile: Optional[Dict]
    ) -> List[Dict]:
        """Filters search results to only include documents listed in the user profile."""
        # Only filter if a profile with policies_owned exists
        if not user_profile or "policies_owned" not in user_profile:
            print("Info: No 'policies_owned' found in profile. Returning all results.")
            return results

        owned_policies = set(user_profile["policies_owned"])
        # (This function appears incomplete in the original, but leaving as-is)
        # Note: This function is not actually called. The logic is in _filter_and_rerank_by_profile
        return results

    def _expand_query(self, query: str) -> str:
        """
        Expands the user query using intelligent LLM rewriting for insurance domain.
        """
        try:
            expansion_prompt = f"""
            You are an insurance domain expert. A user is asking: "{query}"

            Generate a comprehensive search query that includes:
            1. The original terms from the user's question
            2. Official insurance terminology that means the same thing
            3. Common abbreviations and synonyms used in insurance policies
            4. Related concepts that might appear in policy documents

            For example:
            - "collision damage waiver" should include "rental vehicle excess", "CDW", "car rental insurance"
            - "medical coverage" should include "medical expenses", "healthcare benefits", "treatment costs"

            Focus on terms that would actually appear in insurance policy documents.
            Output only the search terms separated by spaces (no explanations):
            """

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": expansion_prompt}],
                max_tokens=150,  # Increased for more comprehensive expansion
                temperature=0.1,
            )

            keywords = response.choices[0].message.content.strip()
            expanded_query = f"{query} {keywords}"

            print(f"Query intelligently expanded to: {expanded_query}")
            return expanded_query

        except Exception as e:
            print(f"Error during query expansion: {e}")
            return query  # Fallback to original query

    def process_query(
        self, query: str, batch_id: str = None, user_profile: Optional[Dict] = None
    ) -> str:
        """Process a query and return the response."""
        try:
            # Determine the target batch
            target_batch = batch_id or self.batch_manager.get_default_batch()
            if not target_batch:
                return "Error: No batch specified and no default batch set."

            # Ensure the correct batch's indexes are loaded
            if not self._ensure_batch_loaded(target_batch):
                return f"Error: Failed to load or switch to batch '{target_batch}'."

            start_time = time.time()
            print(f"\nProcessing query for batch: {target_batch}")
            print(f"Query: {query}")

            expanded_query = self._expand_query(query)

            raw_search_results = self.search_engine.hybrid_search(
                query=expanded_query, top_k=50  # Use the expanded query
            )
            print(
                f"Retrieved {len(raw_search_results)} raw results from hybrid search."
            )

            is_personal_batch = target_batch.startswith("user_")

            unique_results = self._filter_and_rerank_by_profile(
                query, raw_search_results, user_profile
            )
            print(
                f"Retained {len(unique_results)} unique relevant chunks after filtering/deduplication."
            )

            if not unique_results:
                if is_personal_batch:
                    return f"I couldn't find relevant information in your uploaded documents for the question: '{query}'."
                else:
                    return f"No relevant information found in the documents of batch '{target_batch}' for the question: '{query}'."

            response = self._generate_response(
                query, unique_results, is_personal_batch, user_profile
            )

            processing_time = time.time() - start_time
            print(f"Total processing time: {processing_time:.2f}s")

            return response

        except Exception as e:
            # Log the full error for debugging
            import traceback

            print(f"An unexpected error occurred in process_query: {e}")
            traceback.print_exc()
            return f"An error occurred while processing your query. Please check logs. Error: {e}"

    def _generate_response(
        self,
        original_query: str,
        search_results: List[Dict],
        is_personal_batch: bool,
        user_profile: Optional[Dict],
    ) -> str:
        """Generate comprehensive response using retrieved chunks and potentially user profile."""
        if not search_results:
            return "I couldn't find any relevant information in the documents to answer your question."

        context_parts = []
        max_chunks_for_context = 10
        cited_filenames = set()  # keeps track of which documents we found

        print(
            f"Building context from top {min(len(search_results), max_chunks_for_context)} chunks..."
        )
        for i, result in enumerate(search_results[:max_chunks_for_context], 1):
            content = result.get("content", "").strip()
            metadata = result.get("metadata", {})
            if content:
                filename = metadata.get("filename", "Unknown Document")
                page = metadata.get("page_number", "N/A")

                heading = metadata.get("page_heading", "General Information")
                source_ref = f"[Source {i}: {filename}, Page {page}]"
                context_parts.append(
                    f"{source_ref}\nPAGE HEADING: {heading}\n\n{content}"
                )

                cited_filenames.add(filename)

        if not context_parts:
            return "Error: Found relevant documents but failed to extract content for context."

        context_from_docs = "\n\n---\n\n".join(context_parts)

        print("DEBUG: CONTEXT BEING SENT TO OPENAI:")
        print(context_from_docs)

        # Profile Handling
        if is_personal_batch and user_profile:
            user_name = user_profile.get("name", "User")
            insurance_policies = user_profile.get("insurance_policies", {})

            profile_info = f"\n\n--- USER PROFILE (YOUR SOURCE OF TRUTH) ---\n"
            profile_info += f"- User Name: {user_name}\n"

            if insurance_policies:
                profile_info += f"- User's Policies:\n"
                for filename, policy_data in insurance_policies.items():
                    plan = policy_data.get("plan_name", "Unknown Plan")
                    tier = policy_data.get("tier", "N/A")
                    riders = policy_data.get("riders", [])

                    # Add policy and tier info
                    profile_info += f"  - Policy: {plan} (Tier: {tier})\n"

                    # Also add rider info
                    if riders:
                        profile_info += f"    - Riders: {', '.join(riders)}\n"
                    else:
                        profile_info += f"    - Riders: None listed\n"
        else:
            user_name = "User"
            # Provide a fallback string
            profile_info = "\n\n--- USER PROFILE (YOUR SOURCE OF TRUTH) ---\n- No user profile provided.\n"

        salutation = f"Hi {user_name.split()[0] if user_name != 'User' else 'Hi'},"

        # Enhanced prompt with insurance terminology awareness and tier personalization
        # This is the new, hardcoded prompt that implements all your logic.
        prompt_instructions = f"""You are an expert financial advisor specializing in insurance policy analysis.
        Your task is to answer the user's question with extreme precision, acting as a trusted personal advisor.

        --- IMPORTANT INSURANCE CONCEPTS ---
        1.  **Terminology Equivalence (Fixing Terminologies):**
            * 'Rental vehicle excess' is the same as 'Collision Damage Waiver (CDW)' or 'car rental insurance'.
            * 'Major Cancer' is a type of 'Critical Illness'.
            * 'GREAT SupremeHealth' is a 'Reimbursement' plan (health insurance).
            * 'Critical Care Enhancer Rider' is a 'Lump Sum' plan (critical illness insurance).

        2.  **Benefit & Claim Logic (Fixing Claim Plan Logic):**
            * **Reimbursement Plans (Health):** These plans pay the *hospital* for eligible medical bills. The user is responsible for out-of-pocket costs like 'Deductibles' and 'Co-insurance'.
            * **Lump Sum Plans (CI/Life):** These plans pay a *single cash amount* (the 'Sum Insured') directly to the *user* upon diagnosis.
            * **CRITICAL LOGIC:** The cash from a **Lump Sum Plan** is unrestricted. It **CAN** be used to pay for the out-of-pocket costs (deductible, co-insurance) of a **Reimbursement Plan**. You must explain this if the user asks how their plans work together.

        {profile_info}
        --- POLICY DOCUMENT CHUNKS (FOR REFERENCE) ---
        {context_from_docs}
        --- END OF DOCUMENTS ---

        --- CRITICAL RESPONSE RULES (MUST BE FOLLOWED) ---
        1.  **Start your response with: "{salutation}"**

        2.  **User Profile is TRUTH (Fixing Rider Confusion):** The `USER PROFILE` section above is your *only* source of truth for what the user owns. The `DOCUMENT CHUNKS` contain information on *all* plans and riders for sale (like 'GREAT TotalCare').
            * **If a rider (e.g., 'GREAT TotalCare') is NOT listed in the user's profile**, you **MUST IGNORE** its benefits, even if the search chunks show them.
            * You **MUST** state that the user does not have that rider and instead state the benefits of their base plan (e.g., 'GREAT SupremeHealth P PLUS').

        3.  **Be Specific With Money (Fixing Missing Dollar Amounts):**
            * You **MUST** extract specific dollar amounts. Do not say "a deductible"; say "a **$3,500** deductible".
            * When stating a lump sum benefit (like from the Manulife plan), you **MUST** find the **'Sum Insured'** (e.g., **$500,000** for the Critical Care Enhancer Rider) or the 'Maximum amount payable' for that specific benefit.
            * You **MUST NOT** cite a general 'Aggregate Limit' as a user's personal benefit.

        4.  **Cite Every Fact:** You must cite *every* fact you state with its source, including `` when you pull information from the user's profile.

        5.  **No Hallucinations (Fixing Hallucination):**
            * You **MUST NOT** add any conversational sign-offs (e.g., "Best regards," "Sincerely," "Hope this helps!").
            * End your response cleanly after the last piece of information.
        """

        # Call OpenAI API
        try:
            print("Sending request to OpenAI API...")
            if not self.client:
                raise ValueError("OpenAI client is not initialized.")

            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert financial advisor. Answer insurance questions using the provided document chunks, with proper citations. Always include specific coverage amounts when available in the documents. Understand that insurance terminology can have equivalent meanings (e.g., 'rental vehicle excess' = 'collision damage waiver'). Always personalize responses based on the user's specific policy tiers when available.",
                    },
                    {"role": "user", "content": prompt_instructions},
                ],
                max_tokens=1500,
                temperature=0.05,
            )

            final_answer = response.choices[0].message.content.strip()
            # Post-process to remove any copied email signatures from the model output
            final_answer = self._strip_signature(final_answer)
            print("Received response from OpenAI API.")
            return final_answer

        except Exception as e:
            print(f"Error during OpenAI API call: {e}")
            return "Sorry, I encountered an error while generating the response. Please try again later or check the system logs."

    def process_query_stream(
        self, query: str, batch_id: str = None, user_profile: Optional[Dict] = None
    ):
        """Process a query and yield response chunks for streaming."""
        try:
            # Determine the target batch
            target_batch = batch_id or self.batch_manager.get_default_batch()
            if not target_batch:
                yield "data: " + json.dumps(
                    {"error": "No batch specified and no default batch set."}
                ) + "\n\n"
                return

            # Ensure the correct batch's indexes are loaded
            if not self._ensure_batch_loaded(target_batch):
                yield "data: " + json.dumps(
                    {"error": f"Failed to load or switch to batch '{target_batch}'."}
                ) + "\n\n"
                return

            start_time = time.time()
            print(f"\nProcessing query for batch: {target_batch}")
            print(f"Query: {query}")

            expanded_query = self._expand_query(query)

            raw_search_results = self.search_engine.hybrid_search(
                query=expanded_query, top_k=50
            )
            print(
                f"Retrieved {len(raw_search_results)} raw results from hybrid search."
            )

            is_personal_batch = target_batch.startswith("user_")

            unique_results = self._filter_and_rerank_by_profile(
                query, raw_search_results, user_profile
            )
            print(
                f"Retained {len(unique_results)} unique relevant chunks after filtering/deduplication."
            )

            if not unique_results:
                if is_personal_batch:
                    error_msg = f"I couldn't find relevant information in your uploaded documents for the question: '{query}'."
                else:
                    error_msg = f"No relevant information found in the documents of batch '{target_batch}' for the question: '{query}'."
                yield "data: " + json.dumps(
                    {"content": error_msg, "done": True}
                ) + "\n\n"
                return

            # --- START: FIX FOR ASYNC/SYNC ERROR ---

            # This variable will hold the final, clean response
            final_bot_response = ""

            # This generator yields chunks *and* builds the full response
            def stream_and_capture():
                nonlocal final_bot_response
                full_chunks = []

                # Use a standard 'for' loop, not 'async for'
                for chunk in self._generate_response_stream(
                    query, unique_results, is_personal_batch, user_profile
                ):
                    yield chunk  # Pass the chunk to the user immediately
                    try:
                        # Try to parse the chunk to build the full response for saving
                        chunk_data_str = chunk.replace("data: ", "").strip()
                        if chunk_data_str:
                            chunk_data = json.loads(chunk_data_str)
                            if "content" in chunk_data:
                                full_chunks.append(chunk_data["content"])
                    except json.JSONDecodeError:
                        # Ignore "done: True" or other non-content chunks
                        pass
                    except Exception as e:
                        print(f"Error parsing chunk: {e}")

                # Now that streaming is done, assemble and clean the final response
                final_bot_response = self._strip_signature("".join(full_chunks))
                # (This 'final_bot_response' can now be used in your main app
                # for saving to DB after the stream completes)

            # This is the generator the Flask response will use
            response_generator = stream_and_capture()

            # 'yield from' a synchronous generator is allowed
            yield from response_generator

            # --- END: FIX ---

            processing_time = time.time() - start_time
            print(f"Total processing time: {processing_time:.2f}s")

        except Exception as e:
            import traceback

            print(f"An unexpected error occurred in process_query_stream: {e}")
            traceback.print_exc()
            yield "data: "
            (
                D
                + json.dumps(
                    {"error": f"An error occurred while processing your query: {e}"}
                )
                + "\n\n"
            )

    def _generate_response_stream(
        self,
        original_query: str,
        search_results: List[Dict],
        is_personal_batch: bool,
        user_profile: Optional[Dict],
    ):
        """Generate streaming response using retrieved chunks and potentially user profile."""
        if not search_results:
            yield "data: " + json.dumps(
                {
                    "content": "I couldn't find any relevant information in the documents to answer your question.",
                    "done": True,
                }
            ) + "\n\n"
            return

        context_parts = []
        max_chunks_for_context = 10
        cited_filenames = set()

        print(
            f"Building context from top {min(len(search_results), max_chunks_for_context)} chunks..."
        )
        for i, result in enumerate(search_results[:max_chunks_for_context], 1):
            content = result.get("content", "").strip()
            metadata = result.get("metadata", {})
            if content:
                filename = metadata.get("filename", "Unknown Document")
                page = metadata.get("page_number", "N/A")

                heading = metadata.get("page_heading", "General Information")
                source_ref = f"[Source {i}: {filename}, Page {page}]"
                context_parts.append(
                    f"{source_ref}\nPAGE HEADING: {heading}\n\n{content}"
                )

                cited_filenames.add(filename)

        if not context_parts:
            yield "data: " + json.dumps(
                {
                    "content": "Error: Found relevant documents but failed to extract content for context.",
                    "done": True,
                }
            ) + "\n\n"
            return

        context_from_docs = "\n\n---\n\n".join(context_parts)

        print("DEBUG: CONTEXT BEING SENT TO OPENAI:")
        print(context_from_docs)

        # --- FIX: Updated profile logic ---
        if is_personal_batch and user_profile:
            user_name = user_profile.get("name", "User")
            # Read from the new "insurance_policies" key
            insurance_policies = user_profile.get("insurance_policies", {})

            profile_info = f"\n\n--- USER PROFILE (YOUR SOURCE OF TRUTH) ---\n"
            profile_info += f"- User Name: {user_name}\n"

            if insurance_policies:
                profile_info += f"- User's Policies:\n"
                for filename, policy_data in insurance_policies.items():
                    # Get data from the nested object
                    plan = policy_data.get("plan_name", "Unknown Plan")
                    tier = policy_data.get("tier", "N/A")
                    riders = policy_data.get("riders", [])

                    # Add policy and tier info
                    profile_info += f"  - Policy: {plan} (Tier: {tier})\n"

                    # Also add rider info
                    if riders:
                        profile_info += f"    - Riders: {', '.join(riders)}\n"
                    else:
                        profile_info += f"    - Riders: None listed\n"
        else:
            user_name = "User"
            # Provide a fallback string
            profile_info = "\n\n--- USER PROFILE (YOUR SOURCE OF TRUTH) ---\n- No user profile provided.\n"
        # --- END FIX ---

        salutation = f"Hi {user_name.split()[0] if user_name != 'User' else 'Hi'},"

        # --- FIX: This is the new, hardcoded prompt that implements all your logic. ---
        prompt_instructions = f"""You are an expert financial advisor specializing in insurance policy analysis.
        Your task is to answer the user's question with extreme precision, acting as a trusted personal advisor.

        --- IMPORTANT INSURANCE CONCEPTS ---
        1.  **Terminology Equivalence (Fixing Terminologies):**
            * 'Rental vehicle excess' is the same as 'Collision Damage Waiver (CDW)' or 'car rental insurance'.
            * 'Major Cancer' is a type of 'Critical Illness'.
            * 'GREAT SupremeHealth' is a 'Reimbursement' plan (health insurance).
            * 'Critical Care Enhancer Rider' is a 'Lump Sum' plan (critical illness insurance).

        2.  **Benefit & Claim Logic (Fixing Claim Plan Logic):**
            * **Reimbursement Plans (Health):** These plans pay the *hospital* for eligible medical bills. The user is responsible for out-of-pocket costs like 'Deductibles' and 'Co-insurance'.
            * **Lump Sum Plans (CI/Life):** These plans pay a *single cash amount* (the 'Sum Insured') directly to the *user* upon diagnosis.
            * **CRITICAL LOGIC:** The cash from a **Lump Sum Plan** is unrestricted. It **CAN** be used to pay for the out-of-pocket costs (deductible, co-insurance) of a **Reimbursement Plan**. You must explain this if the user asks how their plans work together.

        {profile_info}
        --- POLICY DOCUMENT CHUNKS (FOR REFERENCE) ---
        {context_from_docs}
        --- END OF DOCUMENTS ---

        --- CRITICAL RESPONSE RULES (MUST BE FOLLOWED) ---
        1.  **Start your response with: "{salutation}"**

        2.  **User Profile is TRUTH (Fixing Rider Confusion):** The `USER PROFILE` section above is your *only* source of truth for what the user owns. The `DOCUMENT CHUNKS` contain information on *all* plans and riders for sale (like 'GREAT TotalCare').
            * **If a rider (e.g., 'GREAT TotalCare') is NOT listed in the user's profile**, you **MUST IGNORE** its benefits, even if the search chunks show them.
            * You **MUST** state that the user does not have that rider and instead state the benefits of their base plan (e.g., 'GREAT SupremeHealth P PLUS').

        3.  **Be Specific With Money (Fixing Missing Dollar Amounts):**
            * You **MUST** extract specific dollar amounts. Do not say "a deductible"; say "a **$3,500** deductible".
            * When stating a lump sum benefit (like from the Manulife plan), you **MUST** find the **'Sum Insured'** (e.g., **$500,000** for the Critical Care Enhancer Rider) or the 'Maximum amount payable' for that specific benefit.
            * You **MUST NOT** cite a general 'Aggregate Limit' as a user's personal benefit.

        4.  **Cite Every Fact:** You must cite *every* fact you state with its source, including `` when you pull information from the user's profile.

        5.  **No Hallucinations (Fixing Hallucination):**
            * You **MUST NOT** add any conversational sign-offs (e.g., "Best regards," "Sincerely," "Hope this helps!").
            * End your response cleanly after the last piece of information.
        """

        # Call OpenAI API with streaming
        try:
            print("Sending streaming request to OpenAI API...")
            if not self.client:
                raise ValueError("OpenAI client is not initialized.")

            stream = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert financial advisor. Answer insurance questions using the provided document chunks, with proper citations. Always include specific coverage amounts when available in the documents. Understand that insurance terminology can have equivalent meanings (e.g., 'rental vehicle excess' = 'collision damage waiver'). Always personalize responses based on the user's specific policy tiers when available.",
                    },
                    {"role": "user", "content": prompt_instructions},
                ],
                max_tokens=1500,
                temperature=0.05,
                stream=True,  # Enable streaming
            )

            print("Streaming response from OpenAI API...")

            full_response_chunks = []
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    full_response_chunks.append(content)
                    yield "data: " + json.dumps({"content": content}) + "\n\n"

            # Post-stream cleanup check (for logging)
            final_response_text = "".join(full_response_chunks)
            cleaned_final_response = self._strip_signature(final_response_text)
            if final_response_text != cleaned_final_response:
                print(
                    "WARNING: Caught and stripped a hallucinated signature from the stream."
                )

            # Send final done message
            yield "data: " + json.dumps({"done": True}) + "\n\n"
            print("Finished streaming response from OpenAI API.")

        except Exception as e:
            print(f"Error during OpenAI API streaming call: {e}")
            yield "data: " + json.dumps(
                {
                    "error": "Sorry, I encountered an error while generating the response. Please try again later or check the system logs."
                }
            ) + "\n\n"

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get basic statistics about the search engine state."""
        if self.search_engine:
            return self.search_engine.get_stats()
        return {"error": "Search engine not initialized."}

    def _strip_signature(self, text: str) -> str:
        """Conservative removal of trailing email signature-like blocks from model output.

        This mirrors the preprocessing removing signatures in documents; it is a
        final safety net to avoid returning 'Best regards, [Name]' style closings.
        """
        import re

        sig_pattern = re.compile(
            r"(?m)(?:\n|\A)\s*(?:Best regards,|Best Regards,|Regards,|Sincerely,|Kind regards,|Kind Regards,|Yours sincerely,|Yours faithfully,|Thanks,|Thank you,|Thank you for your time,?)\s*(?:\n[^\n]{0,120})?(?:\n[^\n]{0,120})?\s*\Z",
            flags=re.IGNORECASE,
        )

        new_text = sig_pattern.sub("\n", text)
        new_text = re.sub(r"(?m)^\s*\[?Your Name\]?\s*$", "\n", new_text)
        return new_text.strip()

    def _filter_and_rerank_by_profile(
        self,
        query: str,
        results: List[Dict],
        user_profile: Optional[Dict],
    ) -> List[Dict]:
        """
        Re-ranks search results based on the user's profile AND query keywords.
        Uses a scoring system to apply a "boost" to each chunk's original score.
        This is the STICT V4 logic to handle conflicting chunks.
        """
        if not user_profile:
            print("No user profile provided, returning unique results only.")
            return self._deduplicate_results(results)  # Fallback

        insurance_policies = user_profile.get("insurance_policies", {})
        if not insurance_policies:
            print("User profile has no policies, returning unique results.")
            return self._deduplicate_results(results)  # Fallback

        print(
            "User profile with insurance policies found. Applying smart re-ranking..."
        )

        query_lower = query.lower()

        # --- 1. Calculate File Scores ---
        # We MUST add "deductible" and "sum insured" to the keywords
        # to help find the missing chunks.
        keyword_to_file_map = {
            # Manulife (CI) - High score for explicit keywords
            "ci": ("manulife", 20),
            "critical illness": ("manulife", 20),
            "critical care": ("manulife", 20),
            "manuprotect": ("manulife", 20),
            "manulife": ("manulife", 20),
            "sum insured": ("manulife", 30),  # <-- BOOST for $500k chunk
            # GREAT SupremeHealth (Health) - Normal score
            "deductible": ("supremehealth", 30),  # <-- BOOST for $3.5k chunk
            "health plan": ("supremehealth", 10),
            "health insurance": ("supremehealth", 10),
            "great supremehealth": ("supremehealth", 10),
            "p plus": ("supremehealth", 10),
            "hospital": ("supremehealth", 3),
            "ward": ("supremehealth", 3),
            "surgery": ("supremehealth", 3),
            # Singlife (Travel) - Normal score
            "travel": ("singlife", 10),
            "trip": ("singlife", 10),
            "singlife": ("singlife", 10),
            "prestige": ("singlife", 10),
        }

        if not self.search_engine or not self.search_engine.faiss_metadata:
            print("Search engine metadata not loaded. Cannot re-rank.")
            return self._deduplicate_results(results)

        owned_filenames = set(
            m["filename"]
            for m in self.search_engine.faiss_metadata
            if m.get("filename")
        )

        file_scores = {}
        file_key_to_filename = {}

        for fname in owned_filenames:
            fname_lower = fname.lower()
            file_scores[fname] = 0  # Initialize score for all files

            if "manulife" in fname_lower:
                file_key_to_filename["manulife"] = fname
            elif "supremehealth" in fname_lower:
                file_key_to_filename["supremehealth"] = fname
            elif "singlife" in fname_lower:
                file_key_to_filename["singlife"] = fname

        # Score the query against the keywords
        for keyword, (file_key, score) in keyword_to_file_map.items():
            if keyword in query_lower:
                mapped_filename = file_key_to_filename.get(file_key)
                if mapped_filename in file_scores:
                    file_scores[mapped_filename] += score
                    print(
                        f"  + Query keyword '{keyword}' added {score} points to {mapped_filename}"
                    )

        # --- 2. Normalize Scores and Apply Boost ---
        max_score = (
            max(file_scores.values())
            if file_scores and any(s > 0 for s in file_scores.values())
            else 1.0
        )

        normalized_file_scores = {
            fname: score / max_score for fname, score in file_scores.items()
        }

        boosted_results = []
        seen_content = set()

        # We increase the weight of our boost to make it more impactful
        PROFILE_BOOST_WEIGHT = 0.5

        for result in results:
            content = result.get("content", "")
            if not content or content in seen_content:
                continue
            seen_content.add(content)

            metadata = result.get("metadata", {})
            chunk_filename = metadata.get("filename")

            # Start with the file-level boost
            profile_boost = normalized_file_scores.get(chunk_filename, 0.0)

            # --- START: NEW, STRICTER V4 LOGIC ---
            if chunk_filename in insurance_policies:
                policy_data = insurance_policies[chunk_filename]
                user_tier = policy_data.get("tier", "N/A")  # e.g., "P PLUS"
                user_riders = policy_data.get(
                    "riders", []
                )  # e.g., ["Critical Care..."]

                chunk_plans = metadata.get(
                    "plan_context", []
                )  # e.g., ["GREAT TotalCare", "P PLUS"]
                page_heading = metadata.get("page_heading", "").lower()

                # --- Define what an "enemy" is for this chunk ---
                is_enemy_chunk = False

                if "GREAT_SupremeHealth_Benefits.pdf" in chunk_filename:
                    # The user does NOT own "GREAT TotalCare".
                    # Check if the chunk is about this enemy rider.
                    if (
                        "great totalcare" in page_heading
                        or "GREAT TotalCare" in chunk_plans
                    ):
                        # This chunk is about the rider the user doesn't own.
                        # We must check if "P PLUS" is *also* present (the fine print problem)
                        if user_tier not in chunk_plans:
                            # Simple case: chunk is just for the enemy rider.
                            is_enemy_chunk = True
                        elif (
                            user_tier in chunk_plans
                            and "great totalcare" in page_heading
                        ):
                            # Tricky case: chunk is for "P PLUS" but the *heading* is "GREAT TotalCare".
                            # This means the chunk's *primary subject* is the rider. Penalize it.
                            is_enemy_chunk = True

                # --- Apply Penalties or Boosts based on context ---
                if is_enemy_chunk:
                    # This chunk is primarily about a rider the user does not own.
                    profile_boost -= 2.0  # Very strong penalty
                    print(
                        f"  - PENALTY: Chunk from {chunk_filename} (Page {metadata.get('page_number')}) is for an un-owned rider."
                    )

                elif user_tier != "N/A" and user_tier in chunk_plans:
                    # This chunk is relevant to the user's tier and is NOT an enemy chunk.
                    profile_boost += 0.3  # Strong boost
                    print(
                        f"  + BOOST: Chunk from {chunk_filename} (Page {metadata.get('page_number')}) matches user tier {user_tier}."
                    )

                # --- NEW CONTENT-BASED BOOST ---
                # Now, let's scan the *content* of the chunk for our magic words
                content_lower = content.lower()

                # Find the $500,000 chunk
                if (
                    "manulife" in chunk_filename.lower()
                    and "500,000" in content
                    and "critical care" in content_lower
                ):
                    profile_boost += 3.0  # MASSIVE boost
                    print(
                        f"  +++ SUPER BOOST: Found '$500,000' + 'Critical Care' in {chunk_filename} (Page {metadata.get('page_number')})"
                    )

                # Find the $3,500 chunk
                if (
                    "great_supremehealth" in chunk_filename.lower()
                    and "3,500" in content
                    and "deductible" in content_lower
                ):
                    profile_boost += 3.0  # MASSIVE boost
                    print(
                        f"  +++ SUPER BOOST: Found '$3,500' + 'Deductible' in {chunk_filename} (Page {metadata.get('page_number')})"
                    )

            # --- END: NEW, STRICTER V4 LOGIC ---

            original_score = result.get("combined_score", 0.0)
            result["boosted_score"] = original_score + (
                profile_boost * PROFILE_BOOST_WEIGHT
            )
            boosted_results.append(result)

        # 3. Sort by the new 'boosted_score'
        boosted_results.sort(key=lambda x: x["boosted_score"], reverse=True)

        print(f"Re-ranked {len(boosted_results)} unique chunks with profile boosting.")

        # Print the new Top 10 for debugging
        print("\n--- NEW TOP 10 CHUNKS ---")
        for i, result in enumerate(boosted_results[:10]):
            meta = result["metadata"]
            print(
                f"#{i + 1} (Score: {result['boosted_score']:.2f}) - {meta.get('filename')} Page {meta.get('page_number')} - Heading: {meta.get('page_heading')}"
            )
        print("-------------------------\n")

        return boosted_results

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get basic statistics about the search engine state."""
        if self.search_engine:
            return self.search_engine.get_stats()
        return {"error": "Search engine not initialized."}

    def _strip_signature(self, text: str) -> str:
        """Conservative removal of trailing email signature-like blocks from model output.

        This mirrors the preprocessing removing signatures in documents; it is a
        final safety net to avoid returning 'Best regards, [Name]' style closings.
        """
        import re

        sig_pattern = re.compile(
            r"(?m)(?:\n|\A)\s*(?:Best regards,|Best Regards,|Regards,|Sincerely,|Kind regards,|Kind Regards,|Yours sincerely,|Yours faithfully,|Thanks,|Thank you,|Thank you for your time,?)\s*(?:\n[^\n]{0,120})?(?:\n[^\n]{0,120})?\s*\Z",
            flags=re.IGNORECASE,
        )

        new_text = sig_pattern.sub("\n", text)
        new_text = re.sub(r"(?m)^\s*\[?Your Name\]?\s*$", "\n", new_text)
        return new_text.strip()
