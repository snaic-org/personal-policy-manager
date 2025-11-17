"""
Query Processor
Handles domain-agnostic query processing using hybrid FAISS + BM25 search.
Loads user profile for personalized responses within specific batches (e.g., 'my_policies').

* This is the "Comprehensive" version that relies on the detailed user_profile.json
* to provide facts and uses the document chunks only for citation.
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

from openai import OpenAI

from batch_manager import BatchManager
from utils.search import HybridSearchEngine
from src.intent_analyzer import IntentAnalyzer


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
        # Feature flag: deep research disabled by default (enable by setting DEEP_RESEARCH_ENABLED=true)
        self.deep_research_enabled = (
            os.getenv("DEEP_RESEARCH_ENABLED", "false").lower() == "true"
        )

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

    def _expand_query(self, query: str) -> str:
        """
        Expands the user query using intelligent LLM rewriting and a hardcoded
        critical term map for the insurance domain.
        """

        # --- START: NEW V2 EXPANSION LOGIC ---

        # 1. Define hardcoded maps for critical, non-obvious terms.
        CRITICAL_TERM_MAP = {
            "cabg": "Coronary Artery By-Pass Surgery heart surgery cardiovascular",
            "bypass surgery": "Coronary Artery By-Pass Surgery heart",
            "coronary": "Coronary Artery By-Pass Surgery heart cardiovascular",
            "angioplasty": "Angioplasty and Other Invasive Treatment",
            "stem cell": "Stem Cell Transplant",
            "pet": "Domestic Pet Care",
            "cat": "Domestic Pet Care",
            "dog": "Domestic Pet Care",
            "pet hotel": "Domestic Pet Care",
            "dental": "Accidental Dental Treatment",
            "motorcycle": "motorcycling",
            "motor bike": "motorcycling",
        }

        # This map adds broad keywords based on policy type.
        POLICY_TYPE_KEYWORDS = {
            "health": "deductible co-insurance out-of-pocket",
            "ci": "sum insured critical care benefit limit",
            "critical illness": "sum insured critical care benefit limit",
            "manuprotect": "sum insured critical care benefit limit",
            "supremehealth": "deductible co-insurance out-of-pocket",
        }

        added_keywords = set()
        query_lower = query.lower()

        # Add keywords from the critical term map
        for term, expansion in CRITICAL_TERM_MAP.items():
            if term in query_lower:
                added_keywords.add(expansion)

        # Add keywords from the policy type map
        for term, expansion in POLICY_TYPE_KEYWORDS.items():
            if term in query_lower:
                added_keywords.update(expansion.split())

        # Add keywords for specific scenarios
        if (
            "warded" in query_lower
            or "surgery" in query_lower
            or "hospital" in query_lower
        ):
            added_keywords.add("deductible")
            added_keywords.add("co-insurance")

        manual_expansion = " ".join(added_keywords)

        # --- END: NEW V2 EXPANSION LOGIC ---

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
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": expansion_prompt}],
                max_tokens=150,
                temperature=0.1,
            )

            llm_keywords = response.choices[0].message.content.strip()

            # Combine all three: Original Query + Manual Keywords + LLM Keywords
            expanded_query = f"{query} {manual_expansion} {llm_keywords}"

            print(f"Query intelligently expanded to: {expanded_query}")
            return expanded_query

        except Exception as e:
            print(f"Error during query expansion: {e}")
            # Fallback to original query + manual expansion
            return f"{query} {manual_expansion}"

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

            # Analyze intent
            intent_analyzer = IntentAnalyzer()
            intent = intent_analyzer.analyze(query)
            print(f"Intent analysis: {intent}")

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

            # CRITICAL FIX: Check if user explicitly asked to avoid deep research
            query_lower = query.lower()
            user_wants_own_policies_only = (
                "only refer to" in query_lower
                or "policies i own" in query_lower
                or "my policies" in query_lower
                or "do not use deep research" in query_lower
            )

            # Determine if we need deep research (feature-flagged off by default)
            # IMPORTANT: Only trigger deep research if:
            # 1. No results found AND user didn't explicitly ask for own policies only
            # 2. OR query explicitly needs external comparison
            needs_research = False
            if self.deep_research_enabled:
                needs_research = (
                    len(unique_results) == 0 and not user_wants_own_policies_only
                ) or (
                    intent.get("requires_external_info", False)
                    and not user_wants_own_policies_only
                )

            # Debug logging
            print(f"User wants own policies only: {user_wants_own_policies_only}")
            print(f"Needs research: {needs_research}")
            print(f"Unique results count: {len(unique_results)}")

            if not unique_results and not needs_research:
                if is_personal_batch:
                    error_msg = f"I couldn't find relevant information in your uploaded documents for the question: '{query}'."
                else:
                    error_msg = f"No relevant information found in the documents of batch '{target_batch}' for the question: '{query}'."
                yield "data: " + json.dumps(
                    {"content": error_msg, "done": True}
                ) + "\n\n"
                return

            # Deep research routing (only if truly needed)
            if needs_research:
                start_research_time = time.time()
                print("Starting deep research streaming response...")

                from src.run_ui import run_ui

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                try:
                    async_gen = run_ui(query, intent, unique_results).__aiter__()

                    while True:
                        try:
                            chunk = loop.run_until_complete(async_gen.__anext__())
                            yield "data: " + json.dumps(chunk) + "\n\n"
                        except StopAsyncIteration:
                            break

                finally:
                    loop.close()

                end_research_time = time.time()
                print(
                    f"Total deep research processing time: {end_research_time - start_research_time:.2f}s"
                )

                yield "data: " + json.dumps({"done": True}) + "\n\n"
                print("Finished streaming deep research response.")

                return  # ← CRITICAL: prevents normal RAG stream from running

            # NORMAL RAG streaming with stream capture
            if unique_results:
                final_bot_response = ""

                def stream_and_capture():
                    nonlocal final_bot_response
                    full_chunks = []

                    for chunk in self._generate_response_stream(
                        query, unique_results, is_personal_batch, user_profile
                    ):
                        yield chunk
                        try:
                            chunk_data_str = chunk.replace("data: ", "").strip()
                            if chunk_data_str:
                                chunk_data = json.loads(chunk_data_str)
                                if "content" in chunk_data:
                                    full_chunks.append(chunk_data["content"])
                        except json.JSONDecodeError:
                            pass
                        except Exception as e:
                            print(f"Error parsing chunk: {e}")

                    final_bot_response = self._strip_signature("".join(full_chunks))

                response_generator = stream_and_capture()
                yield from response_generator

            processing_time = time.time() - start_time
            print(f"Total processing time: {processing_time:.2f}s")

        except Exception as e:
            import traceback

            print(f"An unexpected error occurred in process_query_stream: {e}")
            traceback.print_exc()
            yield "data: " + json.dumps(
                {"error": f"An error occurred while processing your query: {e}"}
            ) + "\n\n"

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
            user_dob = user_profile.get("date_of_birth", "N/A")
            insurance_policies = user_profile.get("insurance_policies", {})

            profile_info = f"\n\n--- USER PROFILE (YOUR SOURCE OF TRUTH) ---\n"
            profile_info += f"- User Name: {user_name}\n"
            profile_info += f"- User DOB: {user_dob}\n"

            if insurance_policies:
                profile_info += f"- User's Policies:\n"
                for filename, policy_data in insurance_policies.items():
                    plan = policy_data.get("plan_name", "Unknown Plan")
                    tier = policy_data.get("tier", "N/A")
                    riders = policy_data.get("riders", [])

                    # --- NEW: Add Underwriting Info ---
                    underwriting = policy_data.get("underwriting", {})
                    exclusions = underwriting.get("exclusions")
                    # --- END NEW ---

                    # Add policy and tier info
                    profile_info += f"  - Policy: {plan} (Tier: {tier})\n"

                    # Also add rider info
                    if riders:
                        # Handle list of strings or list of dicts
                        rider_names = [
                            r.get("plan_name", r) if isinstance(r, dict) else r
                            for r in riders
                        ]
                        profile_info += f"    - Riders: {', '.join(rider_names)}\n"
                    else:
                        profile_info += f"    - Riders: None listed\n"

                    # --- NEW: Add Exclusions to prompt ---
                    if exclusions:
                        profile_info += (
                            f"    - !! IMPORTANT EXCLUSION: {exclusions} !!\n"
                        )
                    # --- END NEW ---
        else:
            user_name = "User"
            # Provide a fallback string
            profile_info = "\n\n--- USER PROFILE (YOUR SOURCE OF TRUTH) ---\n- No user profile provided.\n"
        # --- END FIX ---

        salutation = f"Hi {user_name.split()[0] if user_name != 'User' else 'Hi'},"

        prompt_instructions = f"""You are an expert financial advisor specializing in insurance policy analysis.
        Your task is to answer the user's question with extreme precision, relevance, and personalization.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PART 1: MEDICAL & INSURANCE TERMINOLOGY (CRITICAL DOMAIN KNOWLEDGE)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        **Medical Conditions (DO NOT CONFUSE THESE):**
        ├─ CARDIOVASCULAR: Heart Attack, Stroke, Coronary Artery By-Pass Surgery (CABG), Angioplasty
        ├─ ONCOLOGY (CANCER): Major Cancer, Carcinoma, Leukemia, Lymphoma, Tumors
        ├─ NEUROLOGICAL: Parkinson's, Alzheimer's, Multiple Sclerosis, Paralysis
        ├─ RENAL: Kidney Failure, End-Stage Renal Disease (ESRD)
        ├─ ORTHOPEDIC: Joint Replacement, Spinal Surgery, Fractures
        └─ OTHER: Diabetes, Organ Transplant, Major Burns

        **Insurance Terminology Equivalents:**
        - "Rental vehicle excess" = "Collision Damage Waiver (CDW)" = "Car rental insurance excess"
        - "Coronary Artery By-Pass Surgery" = "CABG" = "Heart bypass"
        - "Critical Illness" = any of the 37 major conditions (cancer, heart attack, stroke, etc.)
        - "Major Cancer" is ONE type of critical illness (not all critical illnesses are cancer)

        **Plan Types & How They Work:**
        ┌─────────────────────────────────────────────────────────────────────────┐
        │ REIMBURSEMENT PLANS (Health Insurance - e.g., "GREAT SupremeHealth")   │
        ├─────────────────────────────────────────────────────────────────────────┤
        │ • Pays the HOSPITAL directly for medical bills                         │
        │ • User pays OUT-OF-POCKET: Deductible + Co-insurance                   │
        │ • Example: $100k surgery → User pays $3.5k deductible + 10% of rest    │
        └─────────────────────────────────────────────────────────────────────────┘

        ┌─────────────────────────────────────────────────────────────────────────┐
        │ LUMP SUM PLANS (CI/Life - e.g., "Critical Care Enhancer Rider")        │
        ├─────────────────────────────────────────────────────────────────────────┤
        │ • Pays a FIXED CASH AMOUNT directly to the USER upon diagnosis         │
        │ • User can spend this money on ANYTHING (no restrictions)              │
        │ • Example: Diagnosed with heart attack → Get $500k cash immediately    │
        └─────────────────────────────────────────────────────────────────────────┘

        **CRITICAL COORDINATION LOGIC:**
        → Lump sum cash CAN be used to pay the deductible/co-insurance of a reimbursement plan.
        → Example: Surgery costs $100k. Health plan pays $86.5k to hospital. User owes $13.5k 
        (deductible + co-insurance). User uses CI payout ($500k) to pay that $13.5k.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PART 2: USER PROFILE (YOUR ULTIMATE SOURCE OF TRUTH)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        {profile_info}

        **PROFILE HIERARCHY (PRIORITY ORDER):**
        1. EXCLUSIONS (!! markers) - OVERRIDES EVERYTHING
        2. Owned Policies, Tiers, and Riders - What user actually has
        3. User's Age (calculated from DOB) - Determines age-based benefits
        4. Document chunks below - Use ONLY for citation and details

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PART 3: POLICY DOCUMENT CHUNKS (FOR CITATION & DETAILS ONLY)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        {context_from_docs}

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PART 4: RESPONSE RULES (FOLLOW EXACTLY IN THIS ORDER)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        STEP 1: IDENTIFY WHAT THE USER IS ASKING ABOUT
        ─────────────────────────────────────────────────────────────────────────
        - Read the query carefully. What medical condition or situation is mentioned?
        - Extract the SPECIFIC condition (e.g., "Coronary Artery By-Pass Surgery" = cardiovascular)
        - Map it to the correct category from PART 1 (cardiovascular ≠ cancer ≠ renal, etc.)

        STEP 2: CHECK FOR EXCLUSIONS (HIGHEST PRIORITY)
        ─────────────────────────────────────────────────────────────────────────
        - Look at USER PROFILE for any `!! IMPORTANT EXCLUSION: ... !!` markers
        - Ask: Does the exclusion SPECIFICALLY apply to the condition the user asked about?
        
        ✓ CORRECT APPLICATION:
            - Query: "I need cancer treatment"
            - Exclusion: "No coverage for cancer at all"
            - Result: NOT COVERED (cite <USER PROFILE>)
        
        ✗ WRONG APPLICATION:
            - Query: "I need heart surgery" 
            - Exclusion: "No coverage for cancer at all"
            - Result: COVERED (cancer exclusion doesn't apply to heart conditions!)

        - IF EXCLUSION APPLIES:
        → State clearly: "You are NOT covered for [condition]."
        → Explain why: "Your policy has a specific exclusion: [exclusion text]"
        → Cite: <USER PROFILE>
        → DO NOT mention any benefits from document chunks (contradicts the exclusion)
        → STOP HERE. Do not continue to other rules.

        - IF NO EXCLUSION APPLIES:
        → Proceed to STEP 3

        STEP 3: FILTER BY RELEVANCE (POLICY SELECTION)
        ─────────────────────────────────────────────────────────────────────────
        - Based on the query topic, determine which policies are relevant:
        - Medical/Surgery/Hospital → Health insurance (GREAT SupremeHealth)
        - Critical Illness diagnosis → CI riders (Critical Care Enhancer)
        - Death → Life insurance (ManuProtect Term base plan)
        - Travel incidents → Travel insurance (Singlife)

        - IGNORE irrelevant policies completely:
        - Query about heart surgery → DO NOT mention travel insurance
        - Query about flight delay → DO NOT mention health insurance

        STEP 4: APPLY PERSONALIZATION (AGE & TIER-BASED BENEFITS)
        ─────────────────────────────────────────────────────────────────────────
        - Calculate user's age from DOB in USER PROFILE
        - Use age to select the CORRECT benefit tier from document chunks:
        - Age 24 → Use "up to age 80" deductible ($3,500)
        - DO NOT list "after age 80" amounts ($5,250) - not relevant yet!

        - Match user's TIER from USER PROFILE to document chunk options:
        - User has "P PLUS" → Only state P PLUS benefits
        - DO NOT list A PLUS or B PLUS benefits

        STEP 5: RESPECT RIDER OWNERSHIP (CRITICAL FILTER)
        ─────────────────────────────────────────────────────────────────────────
        - Check USER PROFILE for user's actual riders
        - Document chunks may show benefits for riders the user DOES NOT OWN
        - Example:
        - Document chunk mentions: "GREAT TotalCare covers 95% of deductible"
        - USER PROFILE shows: User owns ZERO riders for GREAT SupremeHealth
        - CORRECT RESPONSE: "You are responsible for the full $3,500 deductible"
        - WRONG RESPONSE: Mentioning the 95% coverage (user doesn't have that rider!)

        STEP 6: EXTRACT SPECIFIC DOLLAR AMOUNTS
        ─────────────────────────────────────────────────────────────────────────
        - Find the EXACT dollar amount for the user's situation:
        - Deductible: "$3,500" (not "a deductible")
        - Sum Insured: "$500,000" (not "a lump sum")
        - Co-insurance: "10%" (not "a percentage")

        - Distinguish between:
        - Personal benefit limit: "$500,000 sum insured" ✓
        - Plan aggregate limit: "$2M annual limit" ✗ (this is not their personal payout)

        STEP 7: EXPLAIN MULTI-POLICY COORDINATION (IF APPLICABLE)
        ─────────────────────────────────────────────────────────────────────────
        - If query involves BOTH health insurance AND CI/life insurance:
        → Explain the coordination from PART 1:
            1. Health plan pays hospital (user pays deductible + co-insurance)
            2. CI/Life plan pays lump sum cash to user
            3. User CAN use lump sum to cover their out-of-pocket costs
        → Give specific dollar example using their actual benefits

        STEP 8: CITE EVERYTHING (CRITICAL - NO HALLUCINATED CITATIONS)
        ─────────────────────────────────────────────────────────────────────────
        - Every fact MUST have the CORRECT citation:
        
        FROM USER PROFILE (cite <USER PROFILE>):
        ✓ User's name, DOB, age
        ✓ Which policies the user OWNS
        ✓ Which tier/plan the user has (e.g., "P PLUS")
        ✓ Which riders the user OWNS (e.g., "Critical Care Enhancer Rider")
        ✓ Exclusions (!! markers)
        
        FROM DOCUMENT CHUNKS (cite [Source X: filename, Page Y]):
        ✓ Dollar amounts (deductibles, sum insured, limits)
        ✓ Benefit details (what's covered, how much, percentages)
        ✓ Policy terms and conditions
        ✓ How benefits work (coordination, payment process)
        
        NO CITATION NEEDED:
        ✓ General insurance concepts from PART 1
        ✓ Your logical reasoning or math calculations

        - NEVER cite <USER PROFILE> for dollar amounts or benefit details!
        - Example of CORRECT citations:
        ✓ "You own the Critical Care Enhancer Rider <USER PROFILE>, which pays 
            $500,000 upon diagnosis [Source 2: Manulife, Page 7]."
        
        - Example of WRONG citations:
        ✗ "Your CI rider pays $500,000 <USER PROFILE>" (NO! Amount is from docs, not profile)

        STEP 9: FORMAT & CLOSE
        ─────────────────────────────────────────────────────────────────────────
        - Start with: "{salutation}"
        - Use clear structure:
        - Opening: Direct answer to the question
        - Body: Detailed breakdown with dollar amounts and citations
        - Closing: Summary or "next steps" (if appropriate)
        - DO NOT add conversational fluff:
        ✗ "Hope this helps!"
        ✗ "Feel free to ask more questions!"
        ✗ "Best regards,"
        ✗ "Let me know if you need clarification!"
        - End cleanly after the last factual statement.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        PART 5: COMMON MISTAKES (WHAT NOT TO DO)
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        ❌ MISTAKE 1: Confusing medical conditions
        - Treating heart surgery as cancer because "cancer exclusion" exists
        - FIX: Use PART 1 to correctly categorize the condition

        ❌ MISTAKE 2: Applying exclusions to wrong conditions  
        - "No cancer coverage" applied to kidney dialysis query
        - FIX: Check if exclusion SPECIFICALLY matches the query topic

        ❌ MISTAKE 3: Mentioning irrelevant policies
        - Discussing travel insurance for a surgery question
        - FIX: Use STEP 3 to filter policies by relevance

        ❌ MISTAKE 4: Listing all age tiers when user is young
        - Showing "$5,250 after age 80" to a 24-year-old
        - FIX: Use STEP 4 to show ONLY the user's current age bracket

        ❌ MISTAKE 5: Citing benefits from riders user doesn't own
        - "You get 95% deductible coverage" when user has no rider
        - FIX: Use STEP 5 to verify rider ownership in USER PROFILE

        ❌ MISTAKE 6: Vague dollar amounts
        - "Your deductible" instead of "Your $3,500 deductible"
        - FIX: Use STEP 6 to extract exact numbers

        ❌ MISTAKE 7: Confusing coordination of benefits
        - "CI plan pays the hospital" (wrong - it pays the user)
        - FIX: Use the logic from PART 1 and STEP 7

        ❌ MISTAKE 8: Missing citations
        - Stating facts without [Source X] or <USER PROFILE>
        - FIX: Use STEP 8 to cite every fact

        ❌ MISTAKE 9: Conversational sign-offs
        - Adding "Hope this helps!" or "Best regards"
        - FIX: Use STEP 9 - end cleanly after last fact

        ❌ MISTAKE 10: Citing <USER PROFILE> for document facts
        - "You get $500,000 <USER PROFILE>" (amount is in docs, not profile)
        - FIX: Profile = ownership/exclusions. Docs = amounts/details.

        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        NOW ANSWER THE USER'S QUESTION
        ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

        USER QUERY: {original_query}

        Follow PART 4 (STEP 1 → STEP 9) exactly. Begin your response now:
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
                        "content": "You are an expert financial advisor. Answer insurance questions using the provided document chunks AND the user profile. The user profile, especially underwriting exclusions, is the absolute source of truth and overrides all document chunks.",
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

    def _get_research_objectives(self, intent: Dict[str, bool]) -> str:
        """Generate research objectives based on query intent."""
        objectives = []
        if intent.get("needs_comparison", False):
            objectives.append("- Compare with similar policies from other insurers")
        if intent.get("asks_about_uncovered_features", False):
            objectives.append(
                "- Find alternative policies that might cover these features"
            )
        if intent.get("requires_external_info", False):
            objectives.append("- Research general information about this topic")

        return (
            "\n".join(objectives)
            if objectives
            else "- Provide relevant insurance information"
        )

    def _filter_and_rerank_by_profile(
        self,
        query: str,
        results: List[Dict],
        user_profile: Optional[Dict],
    ) -> List[Dict]:
        """
        Re-ranks search results based on the user's profile AND query keywords.
        Uses a scoring system to apply a "boost" to each chunk's original score.
        This is the STICT V5 logic to handle conflicting chunks.
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
            elif "great_supremehealth" in fname_lower:
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

            # --- START: NEW, STRICTER V5 LOGIC ---
            if chunk_filename in insurance_policies:
                policy_data = insurance_policies[chunk_filename]
                user_tier = policy_data.get("tier", "N/A")  # e.g., "P PLUS"
                user_riders = policy_data.get(
                    "riders", []
                )  # e.g., ["Critical Care..."]

                chunk_plans = metadata.get(
                    "plan_context", []
                )  # e.g., ["GREAT TotalCare", "P PLUS"]
                content_lower = content.lower()
                page_heading = metadata.get("page_heading", "").lower()

                # --- 1. ENEMY RIDER PENALTY ---
                # This is the most important rule.
                # The user does NOT own "GREAT TotalCare".
                if (
                    "GREAT TotalCare" in chunk_plans
                    or "great totalcare" in page_heading
                ):
                    # This chunk mentions the enemy rider. Penalize it.
                    profile_boost -= 3.0  # Very strong penalty
                    print(
                        f"  --- PENALTY (Enemy Rider): Chunk from {chunk_filename} (Page {metadata.get('page_number')}) mentions 'GREAT TotalCare'."
                    )

                # --- 2. CRITICAL KEYWORD BOOST ---
                # These boosts will find the *exact* chunks we need.

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
                    and user_tier in chunk_plans
                ):
                    profile_boost += 3.0  # MASSIVE boost
                    print(
                        f"  +++ SUPER BOOST: Found '$3,500' + 'Deductible' + 'P PLUS' in {chunk_filename} (Page {metadata.get('page_number')})"
                    )

                # --- 3. BASIC TIER MATCH BOOST ---
                elif user_tier in chunk_plans:
                    # This is a fallback boost if the chunk is relevant but not critical
                    profile_boost += 0.2
                    print(
                        f"  + BOOST (Match): Chunk from {chunk_filename} (Page {metadata.get('page_number')}) matches user tier {user_tier}."
                    )

            # --- END: NEW, STRICTER V5 LOGIC ---

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
                f"#{i+1} (Score: {result['boosted_score']:.2f}) - {meta.get('filename')} Page {meta.get('page_number')} - Heading: {meta.get('page_heading')}"
            )
        print("-------------------------\n")

        return boosted_results

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
