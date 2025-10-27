"""
Query Processor
Handles domain-agnostic query processing using hybrid FAISS + BM25 search.
Loads user profile for personalized responses within specific batches (e.g., 'my_policies').
"""

import os
import json
import time
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from openai import OpenAI

from utils.search import HybridSearchEngine
from batch_manager import BatchManager

class QueryProcessor:
    def __init__(self, batch_manager: BatchManager):
        self.batch_manager = batch_manager
        self.search_engine = None
        self.current_batch_id = None
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.user_profile = self._load_user_profile() # Load profile on initialization

    def _load_user_profile(self) -> Optional[Dict[str, Any]]:
        """Loads the user profile from user_profile.json in the project root."""
        profile_path = Path("user_profile.json")
        if profile_path.exists():
            try:
                with open(profile_path, 'r') as f:
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
            print("Info: user_profile.json not found. Proceeding without personalization.")
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
                faiss_path=paths["faiss_index"],
                bm25_path=paths["bm25_index"]
            )

            if success:
                self.current_batch_id = batch_id
                print(f"Successfully loaded indexes for batch '{batch_id}'.")
                return True
            else:
                print(f"Error: Failed to load indexes for batch '{batch_id}'.")
                self.search_engine = None # Ensure it's None if loading failed
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
            content = result.get('content', '')
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
            print("Warning: 'policies_owned' list is empty in profile. Returning all results.")
            return results

        filtered_results = []
        for result in results:
            # Ensure metadata and filename exist before checking
            metadata = result.get('metadata', {})
            filename = metadata.get('filename')
            if filename and filename in owned_policies:
                filtered_results.append(result)

        print(f"Filtered results to {len(filtered_results)} chunks based on {len(owned_policies)} owned policies.")
        return filtered_results

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

            # --- Step 1: Perform Hybrid Search ---
            # Retrieve a larger set initially to allow for filtering
            raw_search_results = self.search_engine.hybrid_search(
                query=query,
                top_k=20 # Get more results initially
            )
            print(f"Retrieved {len(raw_search_results)} raw results from hybrid search.")

            # --- Step 2: Filter based on Profile (if applicable) ---
            # Define which batches should trigger personalization (e.g., based on name convention)
            is_personal_batch = (target_batch == "my_policies") # Example condition

            relevant_results = raw_search_results
            if is_personal_batch:
                if self.user_profile:
                    relevant_results = self._filter_results_by_profile(raw_search_results)
                else:
                    # Decide behavior: proceed without filtering or return an error/warning?
                    print("Warning: Operating in personal batch mode but no user profile loaded.")
                    # Let's proceed without filtering in this case, but log it.

            # --- Step 3: Deduplicate ---
            unique_results = self._deduplicate_results(relevant_results)
            print(f"Retained {len(unique_results)} unique relevant chunks after filtering/deduplication.")

            if not unique_results:
                if is_personal_batch and self.user_profile:
                    return f"Based on your profile, I couldn't find relevant information in your specific policy documents ('{', '.join(self.user_profile.get('policies_owned',[]))}') for the question: '{query}'."
                else:
                    return f"No relevant information found in the documents of batch '{target_batch}' for the question: '{query}'."

            # --- Step 4: Generate Response ---
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

    def _generate_response(self, original_query: str, search_results: List[Dict], is_personal_batch: bool) -> str:
        """Generate comprehensive response using retrieved chunks and potentially user profile."""
        if not search_results:
            # This check is slightly redundant due to the check in process_query, but safe to keep.
            return "I couldn't find any relevant information in the documents to answer your question."

        # --- Build Context String ---
        context_parts = []
        max_chunks_for_context = 15 # Limit context size for LLM

        print(f"Building context from top {min(len(search_results), max_chunks_for_context)} chunks...")
        for i, result in enumerate(search_results[:max_chunks_for_context], 1):
            content = result.get('content', '').strip()
            metadata = result.get('metadata', {})
            if content: # Ensure content is not empty
                filename = metadata.get('filename', 'Unknown Document')
                page = metadata.get('page_number', 'N/A')
                # Use a consistent source format
                source_ref = f"[Source {i}: {filename}, Page {page}]"
                context_parts.append(f"{source_ref}\n{content}")

        if not context_parts:
            return "Error: Found relevant documents but failed to extract content for context."

        context = "\n\n---\n\n".join(context_parts) # Use separator for clarity

        # --- Prepare Profile Information String (if applicable) ---
        profile_info_string = ""
        user_name = None
        if is_personal_batch and self.user_profile:
            print("Including user profile information in the prompt.")
            profile_items = []
            user_name = self.user_profile.get('name')
            if user_name:
                profile_items.append(f"- User Name: {user_name}")
            if self.user_profile.get('date_of_birth'):
                profile_items.append(f"- Date of Birth: {self.user_profile.get('date_of_birth')}")
            # Optionally add brief policy details, mindful of token limits
            owned_policies = self.user_profile.get('policies_owned', [])
            if owned_policies:
                profile_items.append(f"- Policies Owned: {', '.join(owned_policies)}")
            # Add more details carefully if needed from 'policy_details'

            if profile_items:
                 profile_info_string = "\n\nUSER PROFILE CONTEXT:\n" + "\n".join(profile_items)


        # --- Construct the Final Prompt ---
        # Base prompt instructions
        prompt_instructions = f"""You are an expert assistant with STRICT EVIDENCE REQUIREMENTS.
Answer the question based ONLY on the provided documents ('AVAILABLE DOCUMENTS' section below) and user profile ('USER PROFILE CONTEXT' section below, if provided).

{'This question is specifically about the user detailed in the USER PROFILE CONTEXT. Tailor your answer accordingly, referring to "your policy/policies".' if profile_info_string else 'Answer based generally on the documents provided.'}

Your Task: Answer the following question:
>>> {original_query} <<<
{profile_info_string}

AVAILABLE DOCUMENTS:
--- START OF DOCUMENTS ---
{context}
--- END OF DOCUMENTS ---

CRITICAL RESPONSE RULES:
1. **Base Answer ONLY on AVAILABLE DOCUMENTS:** Do not use any prior knowledge or external information.
2. **Cite EVERYTHING:** Every piece of information MUST end with a citation like [Source X] or [Sources X, Y], referencing the source number from the AVAILABLE DOCUMENTS section.
3. **Handle Missing Information:** If the documents don't answer the question or part of it, explicitly state that and cite the sources checked. Example: "The provided documents do not specify the waiting period for Condition Z [no mention in Sources 1-5]."
4. **Be Specific to User (if profile provided):** If USER PROFILE CONTEXT exists, address the user (e.g., "John, your policy...") and focus on their owned policies.
5. **Be Comprehensive but Concise:** Include all relevant details found in the documents but avoid unnecessary jargon or repetition.
6. **Quote Sparingly:** Prefer summarizing information with citations. Use direct quotes only if essential and keep them short.
7. **No Assumptions:** Do not infer or assume details not explicitly stated. Explicitly state if something is not mentioned.

PROHIBITED:
- Answering without citations.
- Using information outside the AVAILABLE DOCUMENTS.
- Making up details or features.
- Claiming one option is "better" unless the documents provide explicit comparative evidence.

Generate the answer now following all rules:
"""

        # --- Call OpenAI API ---
        try:
            print("Sending request to OpenAI API...")
            if not self.client:
                 raise ValueError("OpenAI client is not initialized.")

            response = self.client.chat.completions.create(
                model="gpt-4o-mini", # Use "gpt-4o" for potentially better reasoning if needed
                messages=[
                    {"role": "system", "content": "You are a precise assistant providing answers strictly based on given documents and user context, citing every piece of information."},
                    {"role": "user", "content": prompt_instructions}
                ],
                max_tokens=1500, # Adjust based on expected answer length
                temperature=0.05, # Very low temperature for factual, consistent answers
                stop=None # Let the model decide when to stop
            )

            final_answer = response.choices[0].message.content.strip()
            print("Received response from OpenAI API.")
            return final_answer

        except Exception as e:
            print(f"Error during OpenAI API call: {e}")
            # Provide a more user-friendly error message, but log the technical details
            return "Sorry, I encountered an error while generating the response. Please try again later or check the system logs."

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get basic statistics about the search engine state."""
        if self.search_engine:
            return self.search_engine.get_stats()
        return {"error": "Search engine not initialized."}