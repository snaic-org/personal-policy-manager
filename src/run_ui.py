# run.py integrated with RAG and follow-up questions for UI

import asyncio
from typing import List, Dict, Optional
from src.helper_query import HelperQuery
from .ai.providers import get_model
from .deep_research import deep_research, write_final_report, write_final_answer
from .feedback import generate_feedback

async def run_ui(
    query: str,
    intent: dict,
    rag_results: List[Dict],
    followup_answers: Optional[List[str]] = None,
    mode: str = "report"
):
    """
    UI-friendly async generator for deep research.
    Yields dicts with keys like 'followup_questions', 'info', 'learnings', 'visited_urls', 'report'.
    """

    print("run_ui called with query:", query)

    is_report = mode != "answer"

    # Step 1: Initialize model
    try:
        client, model_name = get_model()
        yield {"info": f"Using model: {model_name}"}
        print(f"Using model: {model_name}")
    except Exception as e:
        yield {"error": f"Error initializing model: {e}"}
        print(f"Error initializing model: {e}")
        return

    # Step 2: Format initial query with RAG
    helper = HelperQuery(max_chunks_per_query=20)
    formatted_query = helper._format_enhanced_query(query=query, rag_results=rag_results, intent=intent)
    combined_query = formatted_query
    yield {"info": f"Formatted query: {formatted_query}"}

    # Step 3: Generate follow-up questions
    try:
        follow_up_questions = await generate_feedback(formatted_query)
        if follow_up_questions:
            yield {"followup_questions": follow_up_questions}

                # FORCE deep research without waiting for answers
            yield {"info": "Skipping follow-up answers and continuing with deep research..."}

            # If answers are provided, append them to the query
            # if followup_answers and len(followup_answers) == len(follow_up_questions):
            #     qa_pairs = "\n".join([f"Q: {q}\nA: {a}" for q, a in zip(follow_up_questions, followup_answers)])
            #     combined_query += f"\n\nFollow-up Q&A:\n{qa_pairs}"
            #     yield {"info": "Follow-up answers received, proceeding with deep research..."}
            # else:
            #     # Stop here and let UI collect answers
            #     return
    except Exception as e:
        yield {"warning": f"Error generating follow-up questions: {e}"}
        print(f"Error generating follow-up questions: {e}")

    # Step 4: Perform deep research
    try:
        yield {"info": "Starting deep research..."}
        print("Starting deep research...")
        result = await deep_research(query=combined_query, breadth=2, depth=1)
        yield {"info": "Deep research completed. Generating report..."}
        print("Deep research completed. Generating report...")

        if is_report:
            report = await write_final_report(
                prompt=combined_query,
                learnings=result.learnings,
                visited_urls=result.visited_urls
            )
            yield {
                "learnings": result.learnings,
                "visited_urls": result.visited_urls,
                ""
                "report": report
            }
            with open("report.md", "w", encoding="utf-8") as f:
                f.write(report)
        else:
            answer = await write_final_answer(
                prompt=combined_query,
                learnings=result.learnings
            )
            yield {
                "learnings": result.learnings,
                "answer": answer
            }

    except Exception as e:
        import traceback
        traceback.print_exc()
        yield {"error": f"Error during deep research: {e}"}
