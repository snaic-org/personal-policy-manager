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
        self.user_profile = self._load_user_profile()  # Load profile on initialization

    def _load_user_profile(self) -> Optional[Dict[str, Any]]:
        """Loads the user profile from user_profile.json in the project root."""
        profile_path = Path("user_profile_basic.json")
        if profile_path.exists():
            try:
                with open(profile_path, "r") as f:
                    profile = json.load(f)
                    print("User profile loaded successfully.")
                    return profile
            except json.JSONDecodeError:
                print("Error: user_profile.json is not valid JSON.")
                return None
            except Exception as e:
                print(f"Error loading user profile: {e}")
                return None
        else:
            # it's okay if the profile doesn't exist, just means no personalization
            print(
                "Info: user_profile.json not found. Proceeding without personalization."
            )
            return None

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

    def _filter_results_by_profile(self, results: List[Dict]) -> List[Dict]:
        """Filters search results to only include documents listed in the user profile."""
        # Only filter if a profile with policies_owned exists
        if not self.user_profile or "policies_owned" not in self.user_profile:
            print("Info: No 'policies_owned' found in profile. Returning all results.")
            return results

        owned_policies = set(self.user_profile["policies_owned"])
        if not owned_policies:
            print(
                "Warning: 'policies_owned' list is empty in profile. Returning all results."
            )
            return results

        filtered_results = []
        for result in results:
            # Ensure metadata and filename exist before checking
            metadata = result.get("metadata", {})
            filename = metadata.get("filename")
            if filename and filename in owned_policies:
                filtered_results.append(result)

        print(
            f"Filtered results to {len(filtered_results)} chunks based on {len(owned_policies)} owned policies."
        )
        return filtered_results

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

    def process_query(self, query: str, batch_id: str = None) -> str:
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

            # is_personal_batch = (target_batch == "my_policies")
            is_personal_batch = target_batch.startswith("user_")

            relevant_results = raw_search_results
            if is_personal_batch:
                if self.user_profile:
                    relevant_results = self._filter_results_by_profile(
                        raw_search_results
                    )
                else:
                    print(
                        "Warning: Operating in personal batch mode but no user profile loaded."
                    )

            unique_results = self._deduplicate_results(relevant_results)
            print(
                f"Retained {len(unique_results)} unique relevant chunks after filtering/deduplication."
            )

            if not unique_results:
                if is_personal_batch and self.user_profile:
                    return f"Based on your profile, I couldn't find relevant information in your specific policy documents ('{', '.join(self.user_profile.get('policies_owned', []))}') for the question: '{query}'."
                else:
                    return f"No relevant information found in the documents of batch '{target_batch}' for the question: '{query}'."

            response = self._generate_response(query, unique_results, is_personal_batch)

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
        self, original_query: str, search_results: List[Dict], is_personal_batch: bool
    ) -> str:
        """Generate comprehensive response using retrieved chunks and potentially user profile."""
        if not search_results:
            return "I couldn't find any relevant information in the documents to answer your question."

        context_parts = []
        max_chunks_for_context = 30
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
                source_ref = f"[Source {i}: {filename}, Page {page}]"
                context_parts.append(f"{source_ref}\n{content}")
                cited_filenames.add(filename)

        if not context_parts:
            return "Error: Found relevant documents but failed to extract content for context."

        context_from_docs = "\n\n---\n\n".join(context_parts)

        # Enhanced profile handling with policy tiers
        if is_personal_batch and self.user_profile:
            user_name = self.user_profile.get("name", "User")
            policy_tiers = self.user_profile.get("policy_tiers", {})

            profile_info = f"\n\nUSER PROFILE:\n- User Name: {user_name}"
            if policy_tiers:
                profile_info += "\n- Policy Tiers:"
                for policy, tier in policy_tiers.items():
                    profile_info += f"\n  - {policy}: {tier} plan"
        else:
            user_name = "User"
            profile_info = ""

        salutation = f"Hi {user_name.split()[0] if user_name != 'User' else 'Hi'},"

        # Enhanced prompt with insurance terminology awareness and tier personalization
        prompt_instructions = f"""You are an expert financial advisor specializing in insurance policy analysis.
    Your task is to answer the user's question about their insurance coverage.

    IMPORTANT INSURANCE TERMINOLOGY EQUIVALENCE:
    - "Rental vehicle excess" = "Collision damage waiver (CDW)" = "Car rental insurance"
    - "Loss damage waiver (LDW)" = "Collision damage waiver (CDW)"
    - When a user asks about CDW and you find "rental vehicle excess" coverage, treat them as the same thing

    User Question: {original_query}
    {profile_info}

    POLICY DOCUMENT CHUNKS:
    --- START OF DOCUMENTS ---
    {context_from_docs}
    --- END OF DOCUMENTS ---

    CRITICAL RESPONSE RULES:
    1. **Base your answer on the document chunks above**
    2. **Use the user's specific policy tier** - if the profile shows they have a specific plan tier (e.g., "Prestige", "Platinum"), focus on that tier's benefits rather than listing all options
    3. **Understand insurance terminology equivalence** - connect related terms confidently
    4. **If you find relevant coverage information, explain it clearly with specific dollar amounts for their tier (e.g., "up to S$2,500")**
    5. **Cite every fact with [Source X: filename.pdf, Page Y]**
    6. **Be specific about coverage amounts, plan types, and conditions**
    7. **Start your response with: "{salutation}"**
    8. **Provide actionable advice based on the coverage found**
    9. **When multiple plan tiers are shown, focus on the user's specific tier from their profile**

    Generate a helpful response now:
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
            print("Received response from OpenAI API.")
            return final_answer

        except Exception as e:
            print(f"Error during OpenAI API call: {e}")
            return "Sorry, I encountered an error while generating the response. Please try again later or check the system logs."

    def process_query_stream(self, query: str, batch_id: str = None):
        """Process a query and yield response chunks for streaming."""
        try:
            # Determine the target batch
            target_batch = batch_id or self.batch_manager.get_default_batch()
            if not target_batch:
                yield "data: " + json.dumps({"error": "No batch specified and no default batch set."}) + "\n\n"
                return

            # Ensure the correct batch's indexes are loaded
            if not self._ensure_batch_loaded(target_batch):
                yield "data: " + json.dumps({"error": f"Failed to load or switch to batch '{target_batch}'."}) + "\n\n"
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

            relevant_results = raw_search_results
            if is_personal_batch:
                if self.user_profile:
                    relevant_results = self._filter_results_by_profile(
                        raw_search_results
                    )
                else:
                    print(
                        "Warning: Operating in personal batch mode but no user profile loaded."
                    )

            unique_results = self._deduplicate_results(relevant_results)
            print(
                f"Retained {len(unique_results)} unique relevant chunks after filtering/deduplication."
            )

            if not unique_results:
                if is_personal_batch and self.user_profile:
                    error_msg = f"Based on your profile, I couldn't find relevant information in your specific policy documents ('{', '.join(self.user_profile.get('policies_owned', []))}') for the question: '{query}'."
                else:
                    error_msg = f"No relevant information found in the documents of batch '{target_batch}' for the question: '{query}'."
                yield "data: " + json.dumps({"content": error_msg, "done": True}) + "\n\n"
                return

            # Stream the response generation
            for chunk in self._generate_response_stream(query, unique_results, is_personal_batch):
                yield chunk

            processing_time = time.time() - start_time
            print(f"Total processing time: {processing_time:.2f}s")

        except Exception as e:
            import traceback
            print(f"An unexpected error occurred in process_query_stream: {e}")
            traceback.print_exc()
            yield "data: " + json.dumps({"error": f"An error occurred while processing your query: {e}"}) + "\n\n"

    def _generate_response_stream(
        self, original_query: str, search_results: List[Dict], is_personal_batch: bool
    ):
        """Generate streaming response using retrieved chunks and potentially user profile."""
        if not search_results:
            yield "data: " + json.dumps({"content": "I couldn't find any relevant information in the documents to answer your question.", "done": True}) + "\n\n"
            return

        context_parts = []
        max_chunks_for_context = 30
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
                source_ref = f"[Source {i}: {filename}, Page {page}]"
                context_parts.append(f"{source_ref}\n{content}")
                cited_filenames.add(filename)

        if not context_parts:
            yield "data: " + json.dumps({"content": "Error: Found relevant documents but failed to extract content for context.", "done": True}) + "\n\n"
            return

        context_from_docs = "\n\n---\n\n".join(context_parts)

        # Enhanced profile handling with policy tiers
        if is_personal_batch and self.user_profile:
            user_name = self.user_profile.get("name", "User")
            policy_tiers = self.user_profile.get("policy_tiers", {})

            profile_info = f"\n\nUSER PROFILE:\n- User Name: {user_name}"
            if policy_tiers:
                profile_info += "\n- Policy Tiers:"
                for policy, tier in policy_tiers.items():
                    profile_info += f"\n  - {policy}: {tier} plan"
        else:
            user_name = "User"
            profile_info = ""

        salutation = f"Hi {user_name.split()[0] if user_name != 'User' else 'Hi'},"

        # Enhanced prompt with insurance terminology awareness and tier personalization
        prompt_instructions = f"""You are an expert financial advisor specializing in insurance policy analysis.
    Your task is to answer the user's question about their insurance coverage.

    IMPORTANT INSURANCE TERMINOLOGY EQUIVALENCE:
    - "Rental vehicle excess" = "Collision damage waiver (CDW)" = "Car rental insurance"
    - "Loss damage waiver (LDW)" = "Collision damage waiver (CDW)"
    - When a user asks about CDW and you find "rental vehicle excess" coverage, treat them as the same thing

    User Question: {original_query}
    {profile_info}

    POLICY DOCUMENT CHUNKS:
    --- START OF DOCUMENTS ---
    {context_from_docs}
    --- END OF DOCUMENTS ---

    CRITICAL RESPONSE RULES:
    1. **Base your answer on the document chunks above**
    2. **Use the user's specific policy tier** - if the profile shows they have a specific plan tier (e.g., "Prestige", "Platinum"), focus on that tier's benefits rather than listing all options
    3. **Understand insurance terminology equivalence** - connect related terms confidently
    4. **If you find relevant coverage information, explain it clearly with specific dollar amounts for their tier (e.g., "up to S$2,500")**
    5. **Cite every fact with [Source X: filename.pdf, Page Y]**
    6. **Be specific about coverage amounts, plan types, and conditions**
    7. **Start your response with: "{salutation}"**
    8. **Provide actionable advice based on the coverage found**
    9. **When multiple plan tiers are shown, focus on the user's specific tier from their profile**

    Generate a helpful response now:
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
                stream=True  # Enable streaming
            )

            print("Streaming response from OpenAI API...")
            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    content = chunk.choices[0].delta.content
                    yield "data: " + json.dumps({"content": content}) + "\n\n"

            # Send final done message
            yield "data: " + json.dumps({"done": True}) + "\n\n"
            print("Finished streaming response from OpenAI API.")

        except Exception as e:
            print(f"Error during OpenAI API streaming call: {e}")
            yield "data: " + json.dumps({"error": "Sorry, I encountered an error while generating the response. Please try again later or check the system logs."}) + "\n\n"

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get basic statistics about the search engine state."""
        if self.search_engine:
            return self.search_engine.get_stats()
        return {"error": "Search engine not initialized."}
