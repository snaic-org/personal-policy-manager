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
        Expands the user query using LLM to generate insurance-related terms.
        """
        try:
            expansion_prompt = f"""
          You are an insurance expert. A user is asking about insurance coverage.
          Generate 8-10 relevant insurance and policy terms that could help find information about their question.

          Focus on:
          - Technical insurance terms
          - Policy benefit names  
          - Related coverage types
          - Alternative wording for the same concepts

          User Question: "{query}"

          Output only the relevant terms separated by spaces (no explanations):
          """

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": expansion_prompt}],
                max_tokens=100,
                temperature=0.1,
            )

            keywords = response.choices[0].message.content.strip()
            expanded_query = f"{query} {keywords}"

            print(f"Query expanded (LLM) to: {expanded_query}")
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

            # print("\n=== DEBUG: SEARCH RESULTS ===")
            # for i, result in enumerate(unique_results[:20]):  # Show first 20 results
            #     content_preview = (
            #         result.get("content", "")[:200] + "..."
            #         if len(result.get("content", "")) > 200
            #         else result.get("content", "")
            #     )
            #     metadata = result.get("metadata", {})
            #     print(f"Result {i + 1}:")
            #     print(f"  File: {metadata.get('filename', 'Unknown')}")
            #     print(f"  Page: {metadata.get('page_number', 'Unknown')}")
            #     print(f"  Content: {content_preview}")
            #     print(f"  Score: {result.get('combined_score', 'N/A')}")
            #     print("---")
            # print("=== END DEBUG ===\n")

            # DEBUG: Check what TravelCare chunks exist
            print("\n=== TRAVELCARE CHUNKS DEBUG ===")
            travelcare_chunks = [
                r
                for r in unique_results
                if "TravelCare" in r.get("metadata", {}).get("filename", "")
            ]
            print(f"Found {len(travelcare_chunks)} TravelCare chunks in results")

            if len(travelcare_chunks) == 0:
                print("PROBLEM: No TravelCare chunks found in search results!")
                # Let's check if TravelCare chunks exist at all in the index
                all_results_raw = self.search_engine.hybrid_search(
                    "travel insurance rental", top_k=100
                )
                travelcare_raw = [
                    r
                    for r in all_results_raw
                    if "TravelCare" in r.get("metadata", {}).get("filename", "")
                ]
                print(
                    f"Found {len(travelcare_raw)} TravelCare chunks when searching 'travel insurance rental'"
                )
            print("=== END TRAVELCARE DEBUG ===\n")

            print("\n=== TRAVELCARE CONTENT DEBUG ===")
            travel_results = self.search_engine.hybrid_search(
                "travel insurance", top_k=20
            )
            travelcare_found = False
            for i, result in enumerate(travel_results[:10]):
                metadata = result.get("metadata", {})
                filename = metadata.get("filename", "")
                if "TravelCare" in filename:
                    print(f"TravelCare Chunk {i}:")
                    print(f"File: {filename}")
                    print(f"Page: {metadata.get('page_number', 'Unknown')}")
                    print(f"Content: {result.get('content', '')[:300]}...")
                    print("---")
                    travelcare_found = True

            if not travelcare_found:
                print(
                    "🚨 NO TravelCare chunks found even with 'travel insurance' search!"
                )
                print("Checking if ANY TravelCare chunks exist in the index...")

                # Check all possible searches
                for search_term in [
                    "TravelCare",
                    "GREAT",
                    "rental",
                    "vehicle",
                    "excess",
                ]:
                    test_results = self.search_engine.hybrid_search(
                        search_term, top_k=50
                    )
                    travelcare_count = sum(
                        1
                        for r in test_results
                        if "TravelCare" in r.get("metadata", {}).get("filename", "")
                    )
                    print(
                        f"  Search '{search_term}': {travelcare_count} TravelCare chunks"
                    )

            print("=== END CONTENT DEBUG ===\n")

            # DEBUG: Output all search results to file for inspection
            print("Writing all search results to debug_search_results.txt...")
            debug_filename = f"debug_search_results_{int(time.time())}.txt"
            with open(debug_filename, "w", encoding="utf-8") as f:
                f.write(f"DEBUG: Search Results for Query: {query}\n")
                f.write(f"Expanded Query: {expanded_query}\n")
                f.write("=" * 80 + "\n\n")

                # Write the top 50 results
                for i, result in enumerate(unique_results[:50], 1):
                    metadata = result.get("metadata", {})
                    content = result.get("content", "")

                    f.write(f"RESULT #{i}\n")
                    f.write(f"File: {metadata.get('filename', 'Unknown')}\n")
                    f.write(f"Page: {metadata.get('page_number', 'Unknown')}\n")
                    f.write(f"Score: {result.get('combined_score', 'N/A')}\n")
                    f.write(f"Content Length: {len(content)} chars\n")
                    f.write("-" * 40 + "\n")
                    f.write(f"CONTENT:\n{content}\n")
                    f.write("=" * 80 + "\n\n")

                # Also write a separate section for TravelCare chunks specifically
                f.write("\n\nTRAVELCARE CHUNKS SPECIFICALLY:\n")
                f.write("=" * 80 + "\n")

                travelcare_debug_results = self.search_engine.hybrid_search(
                    "GREAT TravelCare", top_k=100
                )
                travelcare_chunks = [
                    r
                    for r in travelcare_debug_results
                    if "TravelCare" in r.get("metadata", {}).get("filename", "")
                ]

                if travelcare_chunks:
                    for i, chunk in enumerate(travelcare_chunks[:20], 1):
                        metadata = chunk.get("metadata", {})
                        content = chunk.get("content", "")
                        f.write(f"TRAVELCARE CHUNK #{i}\n")
                        f.write(f"File: {metadata.get('filename', 'Unknown')}\n")
                        f.write(f"Page: {metadata.get('page_number', 'Unknown')}\n")
                        f.write(f"Content: {content}\n")
                        f.write("-" * 40 + "\n")
                else:
                    f.write("NO TRAVELCARE CHUNKS FOUND!\n")

            print(f"Debug file written: {debug_filename}")

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
        max_chunks_for_context = 15
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

        # Simple profile handling for basic profile
        if is_personal_batch and self.user_profile:
            user_name = self.user_profile.get("name", "User")
            profile_info = f"\n\nUSER PROFILE:\n- User Name: {user_name}"
        else:
            user_name = "User"
            profile_info = ""

        salutation = f"Hi {user_name.split()[0] if user_name != 'User' else 'Hi'},"

        # Clean, simple prompt
        prompt_instructions = f"""You are an expert financial advisor specializing in insurance policy analysis.
    Your task is to answer the user's question about their insurance coverage.

    User Question: {original_query}
    {profile_info}

    POLICY DOCUMENT CHUNKS:
    --- START OF DOCUMENTS ---
    {context_from_docs}
    --- END OF DOCUMENTS ---

    CRITICAL RESPONSE RULES:
    1. **Base your answer on the document chunks above**
    2. **Cite every fact with [Source X: filename.pdf, Page Y]**
    3. **If you find relevant coverage information, explain it clearly**
    4. **If information is missing, state that clearly**
    5. **Start your response with: "{salutation}"**

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
                        "content": "You are an expert financial advisor. Answer insurance questions using only the provided document chunks, with proper citations.",
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

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get basic statistics about the search engine state."""
        if self.search_engine:
            return self.search_engine.get_stats()
        return {"error": "Search engine not initialized."}
