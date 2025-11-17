"""
Query Processor
Handles domain-agnostic query processing using hybrid FAISS + BM25 search.
Loads user profile for personalized responses within specific batches (e.g., 'my_policies').

All hardcoded values moved to config.py
"""

import asyncio
import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
import re

from openai import OpenAI

from batch_manager import BatchManager
from utils.search import HybridSearchEngine
from src.intent_analyzer import IntentAnalyzer
from config.settings import settings as config


class QueryProcessor:
    def __init__(self, batch_manager: BatchManager):
        self.batch_manager = batch_manager
        self.search_engine = None
        self.current_batch_id = None
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.deep_research_enabled = config.DEEP_RESEARCH_ENABLED

    def _ensure_batch_loaded(self, batch_id: str) -> bool:
        """Ensure the specified batch is loaded in the search engine."""
        if self.current_batch_id == batch_id and self.search_engine:
            return True

        paths = self.batch_manager.get_batch_paths(batch_id)
        if not paths:
            print(f"Error: Batch '{batch_id}' configuration not found in registry.")
            return False

        print(f"Loading indexes for batch '{batch_id}'...")
        try:
            # Initialize with weights from settings
            self.search_engine = HybridSearchEngine(
                faiss_weight=config.faiss_weight,
                bm25_weight=config.bm25_weight
            )
            success = self.search_engine.load_indexes(
                faiss_path=paths["faiss_index"], bm25_path=paths["bm25_index"]
            )

            if success:
                self.current_batch_id = batch_id
                print(f"Successfully loaded indexes for batch '{batch_id}'.")
                return True
            else:
                print(f"Error: Failed to load indexes for batch '{batch_id}'.")
                self.search_engine = None
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
            if content and content not in seen_content:
                unique_results.append(result)
                seen_content.add(content)
        return unique_results

    def _rerank_insurance_results(
        self, query: str, results: List[Dict], max_results: int
    ) -> List[Dict]:
        """
        Apply simple insurance-domain heuristics:
        - Boost chunks that match the policy/rider likely relevant to the query.
        - Force-include a high-signal CI chunk (sum insured) for cancer/CI intent.
        - Force-include a high-signal health chunk (deductible/co-insurance) for hospital/treatment intent.
        """
        if not results:
            return []

        query_lower = query.lower()
        wants_ci = any(
            k in query_lower
            for k in [
                "cancer",
                "ci",
                "critical illness",
                "major cancer",
                "bypass",
                "cabg",
                "coronary artery",
                "heart attack",
                "stroke",
                "angioplasty",
            ]
        )
        wants_health = any(
            k in query_lower
            for k in [
                "hospital",
                "treatment",
                "surgery",
                "warded",
                "deductible",
                "co-insurance",
            ]
        )

        boosted = []
        currency_re = re.compile(r"(\$\s?\d|sgd|sum insured|payout|benefit)", re.I)
        health_re = re.compile(r"(deductible|co-?insurance|out[- ]of[- ]pocket)", re.I)

        forced_ci_candidate = None
        forced_ci_score = float("-inf")
        forced_health_candidate = None
        forced_health_score = float("-inf")

        for idx, res in enumerate(results):
            meta = res.get("metadata", {}) or {}
            content = (res.get("content") or "").lower()
            plan_context = meta.get("plan_context") or []

            score = res.get("score", 0) or 0
            # Preserve some original ordering
            score -= idx * 0.001

            if wants_ci and any("critical care enhancer" in pc.lower() for pc in plan_context):
                score += 5
            if wants_health and any("supremehealth" in pc.lower() for pc in plan_context):
                score += 3

            if "sum insured" in content or "$" in content or "benefit" in content:
                score += 2.5  # heavier weight to surface payout amounts
            if "deductible" in content or "co-insurance" in content:
                score += 1.0
            if "major cancer" in content or "critical illness" in content:
                score += 1.5

            # Track best CI chunk with explicit amount words
            if wants_ci and (
                any("critical care enhancer" in pc.lower() for pc in plan_context)
                or "critical care enhancer" in content
            ):
                has_amount_signal = bool(currency_re.search(content))
                bonus = 20
                if has_amount_signal:
                    bonus = 50  # force top placement when amount present
                ci_score = score + bonus
                if ci_score > forced_ci_score:
                    forced_ci_candidate = res
                    forced_ci_score = ci_score

            # Track best health chunk with deductible/co-insurance signals
            if wants_health and (
                any("supremehealth" in pc.lower() for pc in plan_context)
                or "supremehealth" in content
            ):
                has_health_signal = bool(health_re.search(content))
                bonus = 10
                if has_health_signal:
                    bonus = 30  # force top placement when deductible/co-insurance present
                health_score = score + bonus
                if health_score > forced_health_score:
                    forced_health_candidate = res
                    forced_health_score = health_score

            boosted.append((score, res))

        # Sort by boosted score descending
        boosted.sort(key=lambda x: x[0], reverse=True)
        reranked = [r for _, r in boosted]

        # Force-include the best CI chunk if relevant and not already in top slots
        if wants_ci and forced_ci_candidate:
            if forced_ci_candidate not in reranked[: max_results]:
                reranked = [forced_ci_candidate] + reranked

        # Force-include the best health chunk if relevant and not already in top slots
        if wants_health and forced_health_candidate:
            if forced_health_candidate not in reranked[: max_results]:
                reranked = [forced_health_candidate] + reranked

        return reranked[:max_results]

    def _inject_top_plan_chunks(
        self, plan_substr: str, signals: List[str], max_hits: int = 1
    ) -> List[Dict]:
        """
        Deterministically pull top chunks from loaded indexes for a given plan substring,
        prioritizing amount-bearing signals. Use this when critical plan facts are needed
        even if search/rerank missed them.
        """
        injected: List[Dict] = []
        try:
            chunks = getattr(self.search_engine, "bm25_chunks", []) or []
            metadata = getattr(self.search_engine, "bm25_metadata", []) or []
        except Exception:
            return injected

        scored = []
        for content, meta in zip(chunks, metadata):
            text = content or ""
            text_lower = text.lower()
            plan_ctx = meta.get("plan_context") or []
            if not any(plan_substr in pc.lower() for pc in plan_ctx):
                continue

            score = 0
            for s in signals:
                if s in text_lower:
                    score += 3
            if re.search(r"\$\s?\d", text):
                score += 6
            if "sum insured" in text_lower:
                score += 6
            if "deductible" in text_lower or "co-insurance" in text_lower:
                score += 4

            if score > 0:
                scored.append((score, content, meta))

        scored.sort(key=lambda x: x[0], reverse=True)
        for score, content, meta in scored[:max_hits]:
            injected.append(
                {
                    "content": content,
                    "metadata": meta,
                    "score": score + 1000,  # large to keep near top pre-rerank
                    "source": "forced_plan_chunk",
                }
            )

        return injected

    def _multi_policy_search(
        self, query: str, expanded_query: str, user_profile: Dict, chunks_per_policy: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform separate searches for each policy the user owns, then combine results.
        This ensures balanced representation across all policies.

        Args:
            query: Original user query
            expanded_query: Expanded query with additional keywords
            user_profile: User profile containing insurance_policies
            chunks_per_policy: Number of chunks to retrieve per policy (default: 10)

        Returns:
            Combined list of search results from all policies
        """
        insurance_policies = user_profile.get("insurance_policies", {})
        if not insurance_policies:
            print("No policies found in user profile, falling back to standard search")
            return self.search_engine.hybrid_search(
                query=expanded_query, top_k=config.SEARCH_TOP_K
            )

        all_results = []
        policy_filenames = list(insurance_policies.keys())

        # Detect if query is asking about amounts/coverage
        query_lower = query.lower()
        wants_amount = any(
            kw in query_lower
            for kw in ["how much", "amount", "sum insured", "coverage", "covered for", "$", "money", "payout"]
        )

        print(f"\n=== Multi-Policy Search ===")
        print(f"Searching across {len(policy_filenames)} policies: {policy_filenames}")

        for filename in policy_filenames:
            print(f"\nSearching policy: {filename}")
            policy_results = self.search_engine.hybrid_search(
                query=expanded_query,
                top_k=chunks_per_policy,
                filename_filter=filename
            )
            print(f"  → Retrieved {len(policy_results)} chunks from {filename}")

            # For amount queries on Life/CI policies, do an additional targeted search
            if wants_amount and "Manulife" in filename:
                print(f"  → Amount query detected - performing additional targeted search")
                amount_query = "sum insured benefit amount payout table premium"
                extra_results = self.search_engine.hybrid_search(
                    query=amount_query,
                    top_k=5,
                    filename_filter=filename
                )
                print(f"  → Retrieved {len(extra_results)} additional chunks with amount focus")

                # Add extra results, avoiding duplicates
                existing_content = {r.get("content", "") for r in policy_results}
                for extra in extra_results:
                    if extra.get("content", "") not in existing_content:
                        policy_results.append(extra)
                        print(f"     + Added extra chunk from page {extra.get('metadata', {}).get('page_number', '?')}")

            # Debug: Show page numbers and scores for Manulife
            if "Manulife" in filename:
                print(f"  → Manulife chunk details:")
                for i, result in enumerate(policy_results[:15], 1):
                    metadata = result.get("metadata", {})
                    page = metadata.get("page_number", "?")
                    score = result.get("combined_score", 0)
                    content_preview = result.get("content", "")[:60].replace("\n", " ")
                    has_dollar = "$" in result.get("content", "")
                    dollar_marker = " [$]" if has_dollar else ""
                    print(f"     #{i}: Page {page} (score: {score:.3f}){dollar_marker} - {content_preview}...")

            # Tag each result with its policy for tracking
            for result in policy_results:
                result["source_policy"] = filename
                all_results.append(result)

        print(f"\nTotal chunks retrieved: {len(all_results)} ({chunks_per_policy} per policy)")
        print(f"=== End Multi-Policy Search ===\n")

        return all_results

    def _expand_query(self, query: str) -> str:
        """
        Expands the user query using intelligent LLM rewriting and a hardcoded
        critical term map for the insurance domain.
        """
        added_keywords = set()
        query_lower = query.lower()

        # Add keywords from the critical term map (from config)
        for term, expansion in config.CRITICAL_TERM_MAP.items():
            if term in query_lower:
                added_keywords.add(expansion)

        # Add keywords from the policy type map (from config)
        for term, expansion in config.POLICY_TYPE_KEYWORDS.items():
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

        try:
            expansion_prompt = config.QUERY_EXPANSION_PROMPT.format(query=query)

            response = self.client.chat.completions.create(
                model=config.EXPANSION_MODEL,
                messages=[{"role": "user", "content": expansion_prompt}],
                max_tokens=config.EXPANSION_MAX_TOKENS,
                temperature=config.EXPANSION_TEMPERATURE,
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

            is_personal_batch = target_batch.startswith("user_")

            # Use multi-policy search for personal batches with user profiles
            if is_personal_batch and user_profile:
                raw_search_results = self._multi_policy_search(
                    query=query,
                    expanded_query=expanded_query,
                    user_profile=user_profile,
                    chunks_per_policy=10  # 10 chunks per policy
                )
            else:
                raw_search_results = self.search_engine.hybrid_search(
                    query=expanded_query, top_k=config.SEARCH_TOP_K
                )

            print(
                f"Retrieved {len(raw_search_results)} raw results from hybrid search."
            )

            # Quick intent flags for targeted boosts
            query_lower = query.lower()
            wants_ci = any(
                k in query_lower
                for k in [
                    "cancer",
                    "ci",
                    "critical illness",
                    "major cancer",
                    "bypass",
                    "cabg",
                    "coronary artery",
                    "heart attack",
                    "stroke",
                    "angioplasty",
                ]
            )
            wants_health = any(
                k in query_lower
                for k in [
                    "hospital",
                    "treatment",
                    "surgery",
                    "warded",
                    "deductible",
                    "co-insurance",
                ]
            )

            # Targeted second-pass search to force in key policy chunks if missing
            def _has_plan(results, name_substr: str) -> bool:
                for r in results:
                    meta = r.get("metadata") or {}
                    plan_context = meta.get("plan_context") or []
                    content = (r.get("content") or "").lower()
                    if any(name_substr in pc.lower() for pc in plan_context):
                        return True
                    if name_substr in content:
                        return True
                return False

            if wants_ci and not _has_plan(raw_search_results, "critical care enhancer"):
                extra_ci = self.search_engine.hybrid_search(
                    query="Critical Care Enhancer Rider sum insured payout benefit CCE",
                    top_k=5,
                )
                raw_search_results.extend(extra_ci)
                # Heuristic forced inclusion from index if amounts still missing
                forced_cce = self._inject_top_plan_chunks(
                    plan_substr="critical care enhancer",
                    signals=["sum insured", "$", "benefit", "payout", "500,000", "1,000,000"],
                    max_hits=2,
                )
                raw_search_results.extend(forced_cce)

            if wants_health and not _has_plan(raw_search_results, "supremehealth"):
                extra_health = self.search_engine.hybrid_search(
                    query="GREAT SupremeHealth P PLUS deductible co-insurance ward A",
                    top_k=5,
                )
                raw_search_results.extend(extra_health)
                forced_supreme = self._inject_top_plan_chunks(
                    plan_substr="supremehealth",
                    signals=["deductible", "co-insurance", "$3,500", "ward", "co payment", "co-payment"],
                    max_hits=2,
                )
                raw_search_results.extend(forced_supreme)

            unique_results = self._deduplicate_results(raw_search_results)
            # Domain-aware rerank/force-includes to get higher-signal chunks
            unique_results = self._rerank_insurance_results(
                query, unique_results, max_results=config.MAX_CONTEXT_CHUNKS + 3
            )
            # Debug: write reranked chunks to a log file for inspection
            try:
                from pathlib import Path

                debug_dir = Path("logs")
                debug_dir.mkdir(exist_ok=True)
                log_path = debug_dir / "reranked_chunks.txt"
                with open(log_path, "w", encoding="utf-8") as log_file:
                    log_file.write(f"Query: {query}\n")
                    log_file.write(
                        f"Total reranked: {len(unique_results)} (showing top {min(50, len(unique_results))})\n\n"
                    )
                    for i, r in enumerate(unique_results[: min(50, len(unique_results))], 1):
                        meta = r.get("metadata", {}) or {}
                        filename = meta.get("filename", "Unknown")
                        page = meta.get("page_number", "N/A")
                        plan_ctx = ", ".join(meta.get("plan_context") or [])
                        snippet = (r.get("content") or "").replace("\n", " ")[:400]
                        log_file.write(
                            f"#{i} {filename} p{page} | plans: {plan_ctx}\n{snippet}\n\n"
                        )
            except Exception as debug_err:
                print(f"[DEBUG] Failed to write reranked chunk log: {debug_err}")

            # Check if user explicitly asked to avoid deep research
            query_lower = query.lower()
            user_wants_own_policies_only = (
                "only refer to" in query_lower
                or "policies i own" in query_lower
                or "my policies" in query_lower
                or "do not use deep research" in query_lower
            )

            # Determine if we need deep research (feature-flagged off by default)
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

                return  # CRITICAL: prevents normal RAG stream from running

            # NORMAL RAG streaming with stream capture
            if unique_results:
                yield from self._generate_response_stream(
                    query, unique_results, is_personal_batch, user_profile
                )

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
        max_chunks_for_context = config.MAX_CONTEXT_CHUNKS
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
                    underwriting = policy_data.get("underwriting", {})
                    exclusions = underwriting.get("exclusions")

                    # Add policy and tier info
                    profile_info += f"  - Policy: {plan} (Tier: {tier})\n"

                    # Add rider info
                    if riders:
                        # Handle list of strings or list of dicts
                        rider_names = [
                            r.get("plan_name", r) if isinstance(r, dict) else r
                            for r in riders
                        ]
                        profile_info += f"    - Riders: {', '.join(rider_names)}\n"
                    else:
                        profile_info += f"    - Riders: None listed\n"

                    # Add Exclusions to prompt
                    if exclusions:
                        profile_info += (
                            f"    - !! IMPORTANT EXCLUSION: {exclusions} !!\n"
                        )
        else:
            user_name = "User"
            profile_info = "\n\n--- USER PROFILE (YOUR SOURCE OF TRUTH) ---\n- No user profile provided.\n"

        salutation = f"Hi {user_name.split()[0] if user_name != 'User' else 'Hi'},"

        # Use the system prompt from config with formatting
        prompt_instructions = config.INSURANCE_SYSTEM_PROMPT.format(
            profile_info=profile_info,
            context_from_docs=context_from_docs,
            salutation=salutation,
            original_query=original_query,
        )

        # Call OpenAI API with streaming
        try:
            print("Sending streaming request to OpenAI API...")
            if not self.client:
                raise ValueError("OpenAI client is not initialized.")

            stream = self.client.chat.completions.create(
                model=config.RESPONSE_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert financial advisor. Answer insurance questions using the provided document chunks AND the user profile. The user profile, especially underwriting exclusions, is the absolute source of truth and overrides all document chunks. Exclusions are policy-scoped (a health plan exclusion cannot cancel CI/Life benefits) — evaluate each relevant policy independently. State exact amounts from documents; if an amount is not found, use EXACTLY: 'Amount not found in provided documents.' Never say 'depends' or 'the exact amount is not specified.' Do NOT output the literal token '<USER PROFILE>'. No decorative arrows or emoji. End cleanly after the last factual statement—do not add offers to help or follow-up questions.",
                    },
                    {"role": "user", "content": prompt_instructions},
                ],
                max_tokens=config.RESPONSE_MAX_TOKENS,
                temperature=config.RESPONSE_TEMPERATURE,
                stream=True,
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
