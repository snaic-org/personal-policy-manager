import os
import json
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, TypedDict, Callable
from dataclasses import dataclass


# Load environment variables if not already loaded
if not os.getenv("GEMINI_API_KEY") and not os.getenv("TAVILY_API_KEY"):
    try:
        from dotenv import load_dotenv
        # Load environment variables from .env in the project root
        project_root = Path(__file__).parent.parent
        env_path = project_root / ".env"
        load_dotenv(env_path)
    except ImportError:
        print("Warning: python-dotenv not installed. Environment variables may not be loaded from .env")

from tavily import TavilyClient
# Initialize Tavily client 
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
# Concurrency limit (keep for asyncio)
CONCURRENCY_LIMIT = int(os.getenv("TAVILY_CONCURRENCY", "2"))

from .ai.providers_gemini import generate_object, trim_prompt, parse_response
from .prompt import system_prompt

def log(*args):
    """Helper function for consistent logging"""
    print(*args)

class ResearchProgress(TypedDict): 
    current_depth: int
    total_depth: int
    current_breadth: int
    total_breadth: int
    current_query: Optional[str]
    total_queries: int
    completed_queries: int

@dataclass
class ResearchResult:
    learnings: List[str]
    visited_urls: List[str]

@dataclass
class SerpQuery:
    query: str
    research_goal: str

async def generate_serp_queries(
    query: str, 
    num_queries: int = 3, 
    learnings: Optional[List[str]] = None
) -> List[SerpQuery]:
    """Generate SERP queries for research"""
    
    learnings_text = ""
    if learnings:
        learnings_text = f"\n\nHere are some learnings from previous research, use them to generate more specific queries: {chr(10).join(learnings)}"
    
    prompt = f"Given the following prompt from the user, generate a list of SERP queries to research the topic. Return a maximum of {num_queries} queries, but feel free to return less if the original prompt is clear. Make sure each query is unique and not similar to each other: <prompt>{query}</prompt>{learnings_text}"
    
    schema = {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The SERP query. Make it very specific and include exact terms."
                        },
                        "research_goal": {
                            "type": "string",
                            "description": """Generate highly detailed research goals that cover:
1. Specific coverage details (limits, exclusions, waiting periods)
2. Cost information (premiums, deductibles, co-pays)
3. Comparison points with other plans
4. Policy terms and conditions
5. Claim procedures and requirements
6. Provider network restrictions

Example: 'Find exact coverage limits for multifocal lens cataract surgery under Great Eastern SupremeHealth P Plus, including:
- Pre/post operative coverage
- Specific lens brands/types covered
- Annual claim limits
- Required pre-approvals
- Network restrictions
- Premium adjustments
- Comparison with other insurers' coverage'"""
                        }
                    },
                    "required": ["query", "research_goal"]
                },
                "description": f"List of SERP queries, max of {num_queries}"
            }
        },
        "required": ["queries"]
    }
    
    try:
        # Generate the response
        response = generate_object(system_prompt(), prompt, schema)
        if not response:
            log("Error: Empty response from generate_object")
            return []
            
        # Parse response
        result = parse_response(response)
        if not result or "error" in result:
            log(f"Error parsing response: {result.get('error') if result else 'No result'}")
            return []
            
        # Extract and validate queries
        queries_data = result.get("queries", [])
        if not queries_data:
            log("No queries found in response")
            return []
            
        # Build query list with validation
        queries = []
        for q in queries_data:
            if isinstance(q, dict) and "query" in q and "research_goal" in q:
                queries.append(SerpQuery(query=q["query"], research_goal=q["research_goal"]))
            else:
                log(f"Skipping invalid query format: {q}")
        
        log(f"Created {len(queries)} queries", [q.query for q in queries])
        return queries[:num_queries]
    
    except Exception as e:
        log(f"Error generating SERP queries: {e}")
        import traceback
        log(f"Full traceback: {traceback.format_exc()}")
        return []

async def process_serp_result(
    query: str,
    result: Dict[str, Any],
    num_learnings: int = 3,
    num_follow_up_questions: int = 3
) -> Dict[str, List[str]]:
    """Process SERP search results"""
    
    # Extract content from search results
    contents = []
    if "results" in result:
        for i, item in enumerate(result["results"]):
            if "markdown" in item and item["markdown"]:
                contents.append(trim_prompt(item["markdown"], 25000))
            elif "content" in item and item["content"]:
                contents.append(trim_prompt(item["content"], 25000))
    if not contents:
        return {"learnings": [], "follow_up_questions": []}
    
    contents_text = "\n".join([f"<content>\n{content}\n</content>" for content in contents])
    prompt = trim_prompt(
        f"Given the following contents from a SERP search for the query <query>{query}</query>, generate a list of learnings from the contents. Return a maximum of {num_learnings} learnings, but feel free to return less if the contents are clear. Make sure each learning is unique and not similar to each other. The learnings should be concise and to the point, as detailed and information dense as possible. Make sure to include any entities like people, places, companies, products, things, etc in the learnings, as well as any exact metrics, numbers, or dates. The learnings will be used to research the topic further.\n\n<contents>{contents_text}</contents>"
    )

    schema = {
        "type": "object",
        "properties": {
            "learnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": f"List of learnings, max of {num_learnings}"
            },
            "follow_up_questions": {
                "type": "array", 
                "items": {"type": "string"},
                "description": f"List of follow-up questions to research the topic further, max of {num_follow_up_questions}"
            }
        },
        "required": ["learnings", "follow_up_questions"]
    }

    try:
        response = generate_object(system_prompt(), prompt, schema, timeout=60)
        result = parse_response(response)
        return {
            "learnings": result.get("learnings", []),
            "follow_up_questions": result.get("follow_up_questions", [])
        }
    except Exception as e:
        log(f"Error processing SERP result: {e}")
        return {"learnings": [], "follow_up_questions": []}

async def perform_research(
    query: str,
    breadth: int,
    depth: int,
    learnings: Optional[List[str]] = None,
    visited_urls: Optional[List[str]] = None,
    on_progress: Optional[Callable[[ResearchProgress], None]] = None
) -> ResearchResult:
    """Perform deep research on a query"""
    if learnings is None:
        learnings = []
    if visited_urls is None:
        visited_urls = []
    
    progress = ResearchProgress(
        current_depth=depth,
        total_depth=depth,
        current_breadth=breadth,
        total_breadth=breadth,
        current_query=None,
        total_queries=0,
        completed_queries=0
    )
    
    def report_progress(update: Dict[str, Any]):
        progress.update(update)
        if on_progress:
            on_progress(progress)

    # Generate SERP queries
    serp_queries = await generate_serp_queries(query, learnings=learnings, num_queries=breadth)
    if not serp_queries:
        return ResearchResult(learnings=learnings, visited_urls=visited_urls)
    
    report_progress({
        "total_queries": len(serp_queries),
        "current_query": serp_queries[0].query if serp_queries else None
    })

    # Create semaphore for concurrency control
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def process_query(serp_query: SerpQuery):
        async with semaphore:
            try:
                query_text = serp_query.query.lower()
                wants_recent = any(keyword in query_text for keyword in ["current", "latest", "recent", "new", "2025", "this year"])

                search_kwargs = {
                    "query": serp_query.query,
                    "max_results": 8,  # Increased from 5
                    "include_domains": [
                        "www.moh.gov.sg",
                        "www.aia.com.sg",
                        "www.prudential.com.sg",
                        "www.income.com.sg",
                        "www.greateasternlife.com",
                        "www.axa.com.sg",
                        "www.manulife.com.sg",
                        "www.dollarbureau.com",
                        "www.moneysmart.sg",
                        "www.straitstimes.com",
                        "www.channelnewsasia.com",
                        "www.comparefirst.sg"
                    ],
                    # "search_depth": "advanced",  # Using advanced instead of deep
                    # "search_engine": "google",  # Added to ensure comprehensive search
                    "api_max_retries": 3,  # Added for reliability
                    "query_context": "singapore health insurance coverage details comparisons reviews site:.sg"
                }

                if wants_recent:
                    search_kwargs["time_range"] = "year"
                
                result = tavily.search(**search_kwargs)
                new_urls = []
                scraped_contents = []

                if isinstance(result, dict) and "results" in result:
                    for item in result["results"]:
                        url = item.get("url")
                        content = item.get("content") or item.get("markdown", "")
                        if url:
                            new_urls.append(url)
                            scraped_contents.append({"url": url, "markdown": content})

                processed_result = {"results": scraped_contents}
                processed = await process_serp_result(
                    serp_query.query,
                    processed_result,
                    num_follow_up_questions=max(1, breadth // 2)
                )

                all_learnings = learnings + processed["learnings"]
                all_urls = visited_urls + new_urls

                if depth > 1:
                    # Enhanced recursive research logic
                    # next_queries = []
                    
                    # # Add follow-up questions from processing
                    # if processed["follow_up_questions"]:
                    #     next_queries.extend(processed["follow_up_questions"])
                    
                    # # Generate comparison queries if we found specific details
                    # if any("price" in l.lower() or "cost" in l.lower() or "coverage" in l.lower() for l in processed["learnings"]):
                    #     next_queries.append(f"compare {serp_query.query} with alternatives")
                    
                    next_query = f"""
                    User original question: {query}
Previous research goal: {serp_query.research_goal}
Current findings: {chr(10).join(processed["learnings"])}
Follow-up directions:
{chr(10).join(f'- {q}' for q in next_queries)}
                    """.strip()

                    return await perform_research(
                        next_query,
                        breadth,  # Maintain breadth instead of reducing
                        depth - 1,
                        all_learnings,
                        all_urls,
                        on_progress
                    )
                else:
                    return ResearchResult(learnings=all_learnings, visited_urls=all_urls)

            except Exception as e:
                log(f"Error processing query: {serp_query.query}: {e}")
                return ResearchResult(learnings=[], visited_urls=[])
    
    tasks = [process_query(query) for query in serp_queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    all_learnings = set(learnings)
    all_urls = set(visited_urls)
    
    for result in results:
        if isinstance(result, ResearchResult):
            all_learnings.update(result.learnings)
            all_urls.update(result.visited_urls)
    
    return ResearchResult(learnings=list(all_learnings), visited_urls=list(all_urls))

async def write_final_report(
    prompt: str,
    learnings: List[str],
    visited_urls: List[str]
) -> str:
    """Write final research report"""
    if not learnings:
        log("No learnings available for report generation")
        return "I apologize, but I couldn't find any relevant information through research."
        
    learnings_string = "\n".join([f"- {learning}" for learning in learnings])
    
    
    report_prompt = trim_prompt(
        f"""
            Given the user's query and research findings, act as a **licensed Singapore insurance advisor**.
            If information from multiple insurers is available, **recommend the best plan by name** and justify why.
            If details are insufficient, identify what’s missing (e.g., premium cost, waiting period, exclusions).

            User Query: {prompt}

            Research Findings:
            {learnings_string}

            Instructions:
            1. Start with a Direct Answer:
            - Begin with "Yes", "No", or "Partially" when applicable
            - Give a 1-2 sentence summary of the key finding

            2. Structure (use these exact sections):
            ▶ Current Coverage
            - List what's currently covered
            - Include specific amounts and conditions
            
            ▶ Options & Alternatives
            - List relevant alternatives
            - Include costs when available
            
            ▶ Key Considerations
            - List important factors to consider
            - Include any warnings or special notes
            
            ▶ Next Steps
            - Bullet point specific actions to take
            - Include contact information or deadlines

            3. Formatting:
            - Use bullet points for better readability
            - Bold key terms and amounts
            - Keep paragraphs to 2-3 sentences max
            - Include specific numbers and dates
            - Mark deadlines or critical info with ⚠️

            Provide your response as a JSON object with the report in Markdown format."""
    )
    
    schema = {
        "type": "object",
        "properties": {
            "report_markdown": {
                "type": "string",
                "description": "Final report in Markdown format with clear sections and detailed information"
            }
        },
        "required": ["report_markdown"]
    }
    
    try:
        response = generate_object(system_prompt(), report_prompt, schema)
        log(f"Generated response: {response[:200]}...")  # Log first 200 chars for debugging
        
        result = parse_response(response)
        if not result or 'report_markdown' not in result:
            log(f"Invalid report format: {result}")
            return "Error: Could not generate a proper report from the research findings."
            
        report = result['report_markdown'].strip()
        if not report:
            log("Empty report generated")
            return "Error: Generated report was empty."
            
        # Add sources in a structured way
        urls_section = "\n\n## Sources\n\n" + "\n".join([
            f"{i+1}. Research Source {i+1}\n\n   {url}\n"
            for i, url in enumerate(visited_urls)
        ])
        
        return report + urls_section
        
    except Exception as e:
        log(f"Error writing final report: {e}")
        import traceback
        log(f"Full traceback: {traceback.format_exc()}")
        return f"Error generating report: {str(e)}"
    
# Export the functions needed by deep_research.py
__all__ = ['perform_research', 'write_final_report', 'ResearchResult']