from typing import List, Dict
from .ai.providers import trim_prompt

class HelperQuery:

    def __init__(self, max_chunks_per_query: int = 20):
        self.max_chunks_per_query = max_chunks_per_query

    def _format_enhanced_query(self, query: str, rag_results: List[Dict], intent: Dict[str, bool]) -> str:
        """Format the query for deep research with RAG context"""
        rag_context = self._format_rag_context(rag_results)
        objectives = []

        if intent.get("needs_comparison"):
            objectives.append("- Compare with similar policies from other insurers")
        if intent.get("asks_about_uncovered_features"):
            objectives.append("- Find alternative policies that might cover these features")
        if intent.get("requires_external_info"):
            objectives.append("- Research general information about this topic")
        if not objectives:
            objectives.append("- Provide relevant insurance information")

        return f"""User Query: {query}

            Current Policy Information:
            {rag_context}

            Research Objectives:
            {chr(10).join(objectives)}"""

    def _format_rag_context(self, results: List[Dict]) -> str:
        """Format RAG results as context for deep research while managing token limits"""
        # Sort results by relevance score if available
        if results and "score" in results[0]:
            results = sorted(results, key=lambda x: x.get("score", 0), reverse=True)

        max_chunks = min(len(results), self.max_chunks_per_query)
        context_parts = []
        total_length = 0
        max_length = 12000

        priority_keywords = ["coverage", "benefit", "limit", "sum assured", "premium", "claim"]

        def is_priority_chunk(content):
            return any(keyword in content.lower() for keyword in priority_keywords)

        # First pass: priority chunks
        for result in results[:max_chunks]:
            content = result.get("content", "").strip()
            metadata = result.get("metadata", {})
            if content and is_priority_chunk(content):
                policy_name = metadata.get("filename", "Unknown Policy")
                page = metadata.get("page_number", "N/A")
                chunk = f"From {policy_name} (Page {page}):\n{content}"
                if total_length + len(chunk) < max_length:
                    context_parts.append(chunk)
                    total_length += len(chunk)

        # Second pass: remaining chunks
        for result in results[:max_chunks]:
            content = result.get("content", "").strip()
            metadata = result.get("metadata", {})
            if content and not is_priority_chunk(content):
                policy_name = metadata.get("filename", "Unknown Policy")
                page = metadata.get("page_number", "N/A")
                chunk = f"From {policy_name} (Page {page}):\n{content}"
                if total_length + len(chunk) > max_length:
                    if "policy" in content.lower() or "coverage" in content.lower():
                        chunk = trim_prompt(chunk, max_length - total_length)
                        if chunk:
                            context_parts.append(chunk)
                    break
                context_parts.append(chunk)
                total_length += len(chunk)

        if not context_parts:
            return ""

        return "\n\n".join([
            "Information from your current policies:",
            "---",
            "\n\n".join(context_parts),
            "---"
        ])
