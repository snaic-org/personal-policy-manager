# # test_deep_research_standalone.py
# from research import DeepResearch

# researcher = DeepResearch()

# # Test without any RAG context
# query = "What are the best travel insurance policies in Singapore for rental car coverage?"
# results = researcher.research(query)

# print("Answer:", results.get('answer'))
# print("Sources:", results.get('sources'))


from src.intent_analyzer import IntentAnalyzer
import json
from dotenv import load_dotenv
load_dotenv()

intent_analyzer = IntentAnalyzer()
intent = intent_analyzer.analyze("do i need aia insurance on top of my great eastern policy?")
# intent = intent_analyzer.analyze("What is the deductible for my GREAT SupremeHealth P Plus plan?")
print(intent)

needs_research = (
    intent["needs_comparison"] or
    intent["asks_about_uncovered_features"] or
    intent["requires_external_info"] 
)

if needs_research:
    try:
        # Call your DeepResearch module here
        print("Starting deep research...")
        # ✅ Load your cached RAG results
        with open("unique_results_cache_fixed.json", "r", encoding="utf-8") as f:
            rag_results = json.load(f)

        import asyncio
        from src.run_integrate import run
        asyncio.run(run("do i need aia insurance on top of my great eastern policy?", intent, rag_results))
    except Exception as e:
        print(f"Error during deep research: {e}")
else:
    print("No deep research needed based on intent analysis.")