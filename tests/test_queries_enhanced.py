"""
Enhanced Evaluation Test Suite for Insurance Policy Queries
Expanded to cover multiple insurance providers (10 documents)
Tests the RAG pipeline for correctness, balance, and evidence requirements.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from batch_manager import BatchManager
from query_processor import QueryProcessor
from typing import Dict, List, Any
import json
from datetime import datetime

class QueryEvaluator:
    """Evaluates RAG responses against expected criteria."""

    def __init__(self, batch_manager: BatchManager, query_processor: QueryProcessor):
        self.batch_manager = batch_manager
        self.query_processor = query_processor

    def evaluate_response(self, query: str, response: str, expected: Dict) -> Dict[str, Any]:
        """Evaluate a single response against expected criteria."""
        results = {
            "query": query,
            "response": response,
            "passed": True,
            "failures": [],
            "warnings": [],
            "score": 0,
            "max_score": 0
        }

        # Check 1: Must contain required terms
        if "must_contain" in expected:
            results["max_score"] += len(expected["must_contain"])
            for term in expected["must_contain"]:
                if term.lower() in response.lower():
                    results["score"] += 1
                else:
                    results["passed"] = False
                    results["failures"].append(f"Missing required term: '{term}'")

        # Check 2: Must cite multiple policies in comparisons
        if "must_cite_policies" in expected:
            results["max_score"] += len(expected["must_cite_policies"])
            for policy in expected["must_cite_policies"]:
                if policy.lower() in response.lower():
                    results["score"] += 1
                else:
                    results["failures"].append(f"Missing policy reference: '{policy}'")
                    results["passed"] = False

        # Check 3: Should acknowledge limitations
        if expected.get("should_acknowledge_limitations"):
            results["max_score"] += 1
            limitation_phrases = [
                "don't have", "doesn't provide", "cannot", "not available",
                "don't mention", "doesn't discuss", "not found", "insufficient",
                "do not provide", "documents do not"
            ]
            if any(phrase in response.lower() for phrase in limitation_phrases):
                results["score"] += 1
            else:
                results["warnings"].append("Should acknowledge data limitations when appropriate")

        # Check 4: Must have source citations
        if expected.get("must_cite_sources"):
            results["max_score"] += 1

            # Check if this is a "no data found" response
            no_data_phrases = [
                "don't provide", "do not provide", "documents do not",
                "no information", "cannot provide", "not available"
            ]
            is_no_data_response = any(phrase in response.lower() for phrase in no_data_phrases)

            has_citation = "[source" in response.lower() or "source " in response.lower()

            # Pass if either has citations OR is clearly a no-data response
            if has_citation or is_no_data_response:
                results["score"] += 1
            else:
                results["failures"].append("Missing source citations")
                results["passed"] = False

        # Check 5: Should not make specific claims
        if "should_not_claim" in expected:
            results["max_score"] += len(expected["should_not_claim"])
            for claim in expected["should_not_claim"]:
                if claim.lower() not in response.lower():
                    results["score"] += 1
                else:
                    results["failures"].append(f"Made prohibited claim: '{claim}'")
                    results["passed"] = False

        # Check 6: Must acknowledge if comparing different profiles
        if expected.get("must_acknowledge_different_profiles"):
            results["max_score"] += 1
            profile_phrases = [
                "different", "not comparable", "different age", "different health",
                "different profile", "cannot directly compare", "varies"
            ]
            if any(phrase in response.lower() for phrase in profile_phrases):
                results["score"] += 1
            else:
                results["warnings"].append("Should note when comparing different customer profiles")

        # Check 7: Expected outcome matches
        if "expected_outcome" in expected:
            results["max_score"] += 1
            outcome = expected["expected_outcome"].lower()
            if outcome in response.lower():
                results["score"] += 1
            else:
                results["warnings"].append(f"Expected to mention: '{expected['expected_outcome']}'")

        # Check 8: Response length check (for comprehensive answers)
        if expected.get("min_response_length"):
            results["max_score"] += 1
            if len(response) >= expected["min_response_length"]:
                results["score"] += 1
            else:
                results["warnings"].append(f"Response too short (expected >{expected['min_response_length']} chars)")

        # Calculate pass percentage
        if results["max_score"] > 0:
            results["pass_percentage"] = (results["score"] / results["max_score"]) * 100
        else:
            results["pass_percentage"] = 0

        return results


# Enhanced Test Cases covering 10 insurance providers
TEST_CASES = [
    {
        "name": "Multi-Provider Comparison - Coverage Breadth",
        "query": "Compare the critical illness coverage across AIA, FWD, and MSIG policies. Which offers the most comprehensive protection?",
        "expected": {
            "must_contain": ["aia", "fwd", "msig", "coverage"],
            "must_cite_policies": ["AIA", "FWD", "MSIG"],
            "must_cite_sources": True,
            "min_response_length": 500
        }
    },
    {
        "name": "Multi-Provider Comparison - Early Stage Benefits",
        "query": "Which insurance providers offer early-stage critical illness coverage, and how do their benefits compare?",
        "expected": {
            "must_contain": ["early", "stage", "coverage"],
            "must_cite_sources": True,
            "min_response_length": 400
        }
    },
    {
        "name": "Specific Feature Query - Multi-Pay Benefits",
        "query": "Which policies offer multi-pay critical illness benefits and what are the key differences?",
        "expected": {
            "must_contain": ["multi", "pay"],
            "must_cite_sources": True,
            "min_response_length": 300
        }
    },
    {
        "name": "Provider-Specific Deep Dive - AIA Coverage",
        "query": "What are the unique features and benefits of AIA's critical illness policies?",
        "expected": {
            "must_contain": ["aia"],
            "must_cite_sources": True,
            "min_response_length": 300
        }
    },
    {
        "name": "Comparison - Diabetes Coverage",
        "query": "How do different insurers handle diabetes-related critical illness coverage?",
        "expected": {
            "must_contain": ["diabetes"],
            "must_cite_sources": True,
            "min_response_length": 400
        }
    },
    {
        "name": "Comparison - Cancer Coverage",
        "query": "Compare the cancer coverage benefits across all available policies, including early and late stage.",
        "expected": {
            "must_contain": ["cancer"],
            "must_cite_sources": True,
            "min_response_length": 500
        }
    },
    {
        "name": "Specific Feature - ICU Benefits",
        "query": "Which policies include ICU benefits and what do they cover?",
        "expected": {
            "must_contain": ["icu"],
            "must_cite_sources": True
        }
    },
    {
        "name": "Recommendation Query - Young Professional",
        "query": "What would be the best critical illness policy for a 30-year-old healthy professional based on the available options?",
        "expected": {
            "must_contain": ["policy", "coverage"],
            "must_cite_sources": True,
            "min_response_length": 400
        }
    },
    {
        "name": "Comparison - Premium Payment Options",
        "query": "What premium payment structures are available across different insurers?",
        "expected": {
            "must_contain": ["premium", "payment"],
            "must_cite_sources": True,
            "min_response_length": 300
        }
    },
    {
        "name": "Feature Availability - Riders and Add-ons",
        "query": "What optional riders and add-on benefits are available across all the policies?",
        "expected": {
            "must_contain": ["rider"],
            "must_cite_sources": True,
            "min_response_length": 400
        }
    },
    {
        "name": "Comparison - Claim Process",
        "query": "How do the claim processes differ between the major insurance providers?",
        "expected": {
            "must_contain": ["claim"],
            "must_cite_sources": True,
            "min_response_length": 300
        }
    },
    {
        "name": "Coverage Gaps - Pre-existing Conditions",
        "query": "Which policies offer the best coverage for people with pre-existing conditions?",
        "expected": {
            "must_contain": ["pre-existing", "condition"],
            "must_cite_sources": True,
            "min_response_length": 300
        }
    },
    {
        "name": "Unavailable Data - Market Share",
        "query": "What are the market share percentages for each insurance provider?",
        "expected": {
            "must_cite_sources": True,
            "should_acknowledge_limitations": True,
            "expected_outcome": "do not provide"
        }
    },
    {
        "name": "Complex Comparison - Value Proposition",
        "query": "For someone seeking the best value for money, which policies offer the strongest combination of coverage, benefits, and features?",
        "expected": {
            "must_contain": ["coverage", "benefit"],
            "must_cite_sources": True,
            "min_response_length": 600
        }
    },
    {
        "name": "Specific Condition - Heart Disease",
        "query": "Compare how heart disease and related conditions are covered across different policies.",
        "expected": {
            "must_contain": ["heart"],
            "must_cite_sources": True,
            "min_response_length": 400
        }
    }
]


def run_evaluation(batch_name: str = "insurance"):
    """Run all test cases and generate evaluation report."""

    print("="*80)
    print("ENHANCED INSURANCE POLICY RAG EVALUATION")
    print("Testing with 10 insurance providers")
    print("="*80)
    print()

    # Initialize components
    batch_manager = BatchManager()
    query_processor = QueryProcessor(batch_manager)
    evaluator = QueryEvaluator(batch_manager, query_processor)

    # Switch to test batch
    if not batch_manager.switch_batch(batch_name):
        print(f"Failed to load batch '{batch_name}'")
        return

    # Run tests
    results = []
    passed_tests = 0
    total_tests = len(TEST_CASES)

    for i, test_case in enumerate(TEST_CASES, 1):
        print(f"\n[Test {i}/{total_tests}] {test_case['name']}")
        print("-" * 80)
        print(f"Query: {test_case['query']}")
        print()

        # Get response
        response = query_processor.process_query(test_case['query'])

        # Show truncated response
        if len(response) > 400:
            print(f"Response:\n{response[:400]}...")
        else:
            print(f"Response:\n{response}")
        print()

        # Evaluate
        eval_result = evaluator.evaluate_response(
            test_case['query'],
            response,
            test_case['expected']
        )

        results.append(eval_result)

        # Print results
        if eval_result['passed']:
            passed_tests += 1
            print(f"[PASS] {eval_result['score']}/{eval_result['max_score']} checks ({eval_result['pass_percentage']:.1f}%)")
        else:
            print(f"[FAIL] {eval_result['score']}/{eval_result['max_score']} checks ({eval_result['pass_percentage']:.1f}%)")

        if eval_result['failures']:
            print("Failures:")
            for failure in eval_result['failures']:
                print(f"  - {failure}")

        if eval_result['warnings']:
            print("Warnings:")
            for warning in eval_result['warnings']:
                print(f"  - {warning}")

        print()

    # Summary
    print("="*80)
    print("EVALUATION SUMMARY")
    print("="*80)
    print(f"Tests Passed: {passed_tests}/{total_tests} ({(passed_tests/total_tests)*100:.1f}%)")
    print()

    # Detailed breakdown
    total_score = sum(r['score'] for r in results)
    total_max_score = sum(r['max_score'] for r in results)
    print(f"Overall Score: {total_score}/{total_max_score} ({(total_score/total_max_score)*100:.1f}%)")
    print()

    # Save results
    output_file = f"evaluation_results_enhanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump({
            'summary': {
                'total_tests': total_tests,
                'passed_tests': passed_tests,
                'pass_rate': (passed_tests/total_tests)*100,
                'overall_score': total_score,
                'max_score': total_max_score,
                'score_percentage': (total_score/total_max_score)*100,
                'total_providers': 10,
                'total_chunks': 339
            },
            'results': results
        }, f, indent=2)

    print(f"Detailed results saved to: {output_file}")
    print()

    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run Enhanced RAG evaluation tests")
    parser.add_argument("--batch", default="insurance", help="Batch name to test against")

    args = parser.parse_args()

    run_evaluation(args.batch)
