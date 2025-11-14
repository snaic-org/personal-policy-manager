import os
import json
import asyncio
import time
from pathlib import Path
from typing import List, Dict, Optional, Any, TypedDict, Callable
from dataclasses import dataclass

# Load environment variables if not already loaded
if not os.getenv("OPENAI_KEY") and not os.getenv("FIRECRAWL_KEY"):
    try:
        from dotenv import load_dotenv
        # Load environment variables from .env.local in the project root
        project_root = Path(__file__).parent.parent
        env_path = project_root / ".env.local"
        load_dotenv(env_path)
    except ImportError:
        print("Warning: python-dotenv not installed. Environment variables may not be loaded from .env.local")

# try:
#     from firecrawl import FirecrawlApp
# except ImportError:
#     # Fallback for different firecrawl package structures
#     try:
#         from firecrawl.firecrawl import FirecrawlApp
#     except ImportError:
#         print("Error: firecrawl package not found. Please install with: pip install firecrawl-py")
#         raise

from tavily import TavilyClient

# Initialize Tavily
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# Concurrency limit (keep for asyncio)
CONCURRENCY_LIMIT = int(os.getenv("TAVILY_CONCURRENCY", "2"))


from .ai.providers import generate_object, trim_prompt, parse_response
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


# Initialize Firecrawl
# CONCURRENCY_LIMIT = int(os.getenv("FIRECRAWL_CONCURRENCY", "2"))

# firecrawl = FirecrawlApp(
#     api_key=os.getenv("FIRECRAWL_KEY", ""),
#     api_url=os.getenv("FIRECRAWL_BASE_URL")
# )


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
                            "description": "The SERP query"
                        },
                        "research_goal": {
                            "type": "string",
                            "description": "First talk about the goal of the research that this query is meant to accomplish, then go deeper into how to advance the research once the results are found, mention additional research directions. Be as specific as possible, especially for additional research directions."
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
        response = generate_object(system_prompt(), prompt, schema)
        
        # Parse response
        result = parse_response(response)
        
        queries_data = result.get("queries", [])
        queries = [
            SerpQuery(query=q["query"], research_goal=q["research_goal"])
            for q in queries_data
        ]
        
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
        log(f"DEBUG: Found {len(result['results'])} items in search results")
        for i, item in enumerate(result["results"]):
            log(f"DEBUG: Item {i}: {list(item.keys())}")
            if "markdown" in item and item["markdown"]:
                content = trim_prompt(item["markdown"], 25000)
                contents.append(content)
                log(f"DEBUG: Added markdown content from item {i}")
            elif "content" in item and item["content"]:
                content = trim_prompt(item["content"], 25000)
                contents.append(content)
                log(f"DEBUG: Added content from item {i}")
    else:
        log(f"DEBUG: No 'results' key in result. Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
    
    log(f"Ran {query}, found {len(contents)} contents")
    
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
        
        learnings = result.get("learnings", [])
        follow_up_questions = result.get("follow_up_questions", [])
        
        log(f"Created {len(learnings)} learnings", learnings)
        return {
            "learnings": learnings,
            "follow_up_questions": follow_up_questions
        }
    
    except Exception as e:
        log(f"Error processing SERP result: {e}")
        return {"learnings": [], "follow_up_questions": []}


async def write_final_report(
    prompt: str,
    learnings: List[str],
    visited_urls: List[str]
) -> str:
    """Write final research report"""
    
    learnings_string = "\n".join([f"<learning>\n{learning}\n</learning>" for learning in learnings])
    
    report_prompt = trim_prompt(
    f"""Using the following user prompt and research learnings, write a comprehensive final report on the topic. 

        Requirements:
        - Make the report detailed, aiming for at least 3 pages.
        - Include all relevant insights from the research learnings.
        - Organize the report with clear headings and subheadings.
        - Synthesize information rather than just listing learnings.
        - Include tables, examples, or comparisons where helpful.
        - Ensure the report is professional, easy to read, and actionable.

        User Prompt:
        <prompt>{prompt}</prompt>

        Research Learnings:
        <learnings>
        {learnings_string}
        </learnings>
        """
        )

    
    schema = {
        "type": "object",
        "properties": {
            "report_markdown": {
                "type": "string",
                "description": "Final report on the topic in Markdown"
            }
        },
        "required": ["report_markdown"]
    }
    
    try:
        response = generate_object(system_prompt(), report_prompt, schema)
        result = parse_response(response)
        report = result.get("report_markdown", "")
        log(f"DEBUG: AI report content: {report[:500]}")  # Add this line to see what the AI returns
        # Append sources
        urls_section = f"\n\n## Sources\n\n" + "\n".join([f"- {url}" for url in visited_urls])
        return report + urls_section
    
    except Exception as e:
        log(f"Error writing final report: {e}")
        return "Error generating report"


async def write_final_answer(
    prompt: str,
    learnings: List[str]
) -> str:
    """Write final answer based on research"""
    
    learnings_string = "\n".join([f"<learning>\n{learning}\n</learning>" for learning in learnings])
    
    answer_prompt = trim_prompt(
        f"Given the following prompt from the user, write a final answer on the topic using the learnings from research. Follow the format specified in the prompt. Do not yap or babble or include any other text than the answer besides the format specified in the prompt. Keep the answer as concise as possible - usually it should be just a few words or maximum a sentence. Try to follow the format specified in the prompt (for example, if the prompt is using Latex, the answer should be in Latex. If the prompt gives multiple answer choices, the answer should be one of the choices).\n\n<prompt>{prompt}</prompt>\n\nHere are all the learnings from research on the topic that you can use to help answer the prompt:\n\n<learnings>\n{learnings_string}\n</learnings>"
    )
    
    schema = {
        "type": "object",
        "properties": {
            "exact_answer": {
                "type": "string",
                "description": "The final answer, make it short and concise, just the answer, no other text"
            }
        },
        "required": ["exact_answer"]
    }
    
    try:
        response = generate_object(system_prompt(), answer_prompt, schema)
        
        result = parse_response(response)
        
        return result.get("exact_answer", "")
    
    except Exception as e:
        log(f"Error writing final answer: {e}")
        return "Error generating answer"


async def deep_research(
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
                # Perform search using Tavily
                # result = tavily.search(
                #     query=serp_query.query,
                #     max_results=5,
                #     include_domains=[
                #     "www.moh.gov.sg",           # Ministry of Health Singapore
                #     "www.mas.gov.sg",           # Monetary Authority of Singapore
                #     "www.aia.com.sg",           # AIA Singapore
                #     "www.prudential.com.sg",    # Prudential Singapore
                #     "www.income.com.sg",        # NTUC Income
                #     "www.greateasternlife.com", # Great Eastern
                #     "www.policypal.com",        # PolicyPal Singapore
                #     ],
                #     exclude_domains=[
                #         "www.reddit.com",
                #         "www.quora.com",
                #         "medium.com",
                #         "blogspot.com",
                #         "forums.hardwarezone.com.sg"
                #     ]
                # )
                # log(f"DEBUG: Tavily search result for '{serp_query.query}': {len(result.data) if hasattr(result, 'data') else 'No data'} items found")
# new one w date 

                # Perform search using Tavily (conditionally filter by date)
                query_text = serp_query.query.lower()

                # Check if the user likely wants recent info
                wants_recent = any(keyword in query_text for keyword in ["current", "latest", "recent", "new", "2025", "this year"])

                search_kwargs = {
                    "query": serp_query.query,
                    "max_results": 5,
                    "include_domains": [
                        "www.moh.gov.sg",           # Ministry of Health Singapore
                        "www.mas.gov.sg",           # Monetary Authority of Singapore
                        "www.aia.com.sg",           # AIA Singapore
                        "www.prudential.com.sg",    # Prudential Singapore
                        "www.income.com.sg",        # NTUC Income
                        "www.greateasternlife.com", # Great Eastern
                        "www.policypal.com",        # PolicyPal Singapore
                    ],
                    "exclude_domains": [
                        "www.reddit.com",
                        "www.quora.com",
                        "medium.com",
                        "blogspot.com",
                        "forums.hardwarezone.com.sg"
                    ]
                }

                # Add time filter if query implies recency
                if wants_recent:
                    search_kwargs["time_range"] = "year"
                    log(f"Applying recent filter for query: {serp_query.query}")

                # Execute Tavily search
                result = tavily.search(**search_kwargs)
                log(f"DEBUG: Tavily search result for '{serp_query.query}': {len(result.data) if hasattr(result, 'data') else 'No data'} items found")

                new_urls = []
                scraped_contents = []

                # Tavily search returns a list of dicts with 'url'
                if "results" in result and result["results"]:
                    for item in result["results"]:
                        url = item.get("url")
                        content = item.get("content") or item.get("markdown", "")
                        if url:
                            new_urls.append(url)
                            scraped_contents.append({
                                "url": url,
                                "markdown": content
                            })

                log(f"Found {len(new_urls)} URLs, successfully scraped {len(scraped_contents)} pages")

                new_breadth = max(1, breadth // 2)
                new_depth = depth - 1

                processed_result = {
                    "results": scraped_contents
                }

                processed = await process_serp_result(
                    serp_query.query,
                    processed_result,
                    num_follow_up_questions=new_breadth
                )

                all_learnings = learnings + processed["learnings"]
                all_urls = visited_urls + new_urls

                if new_depth > 0:
                    log(f"Researching deeper, breadth: {new_breadth}, depth: {new_depth}")

                    report_progress({
                        "current_depth": new_depth,
                        "current_breadth": new_breadth,
                        "completed_queries": progress["completed_queries"] + 1,
                        "current_query": serp_query.query
                    })

                    next_query = f"""
Previous research goal: {serp_query.research_goal}
Follow-up research directions: {chr(10).join(processed["follow_up_questions"])}
                    """.strip()

                    return await deep_research(
                        next_query,
                        new_breadth,
                        new_depth,
                        all_learnings,
                        all_urls,
                        on_progress
                    )
                else:
                    report_progress({
                        "current_depth": 0,
                        "completed_queries": progress["completed_queries"] + 1,
                        "current_query": serp_query.query
                    })
                    return ResearchResult(learnings=all_learnings, visited_urls=all_urls)

            except Exception as e:
                if "timeout" in str(e).lower():
                    log(f"Timeout error running query: {serp_query.query}: {e}")
                else:
                    log(f"Error running query: {serp_query.query}: {e}")
                return ResearchResult(learnings=[], visited_urls=[])
    
    # Execute all queries concurrently
    tasks = [process_query(query) for query in serp_queries]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results
    all_learnings = set(learnings)
    all_urls = set(visited_urls)
    
    for result in results:
        if isinstance(result, ResearchResult):
            all_learnings.update(result.learnings)
            all_urls.update(result.visited_urls)
        elif isinstance(result, Exception):
            log(f"Task failed with exception: {result}")
    
    return ResearchResult(
        learnings=list(all_learnings),
        visited_urls=list(all_urls)
    )
