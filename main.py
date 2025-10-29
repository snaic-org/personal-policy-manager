#!/usr/bin/env python3
"""
Domain-Agnostic Chatbot CLI
Main entry point for querying documents across different domains.
"""

import argparse
import sys
import os
import json
from pathlib import Path

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from batch_manager import BatchManager
from query_processor import QueryProcessor

# lightweight HTTP server option using Flask
def run_api_server(batch_manager: BatchManager, host="0.0.0.0", port=5000):
    from flask import Flask, request, jsonify
    from flask_cors import CORS
    import traceback  # Add for error logging

    app = Flask(__name__)
    CORS(app)  # Enable CORS for all routes

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"})

    @app.route("/query", methods=["POST"])
    def query_endpoint():
        try:
            data = request.get_json(force=True, silent=True) or {}
            print(f"Received query request: {data}")  # Debug log
            
            q = data.get("query") or data.get("question")
            batch = data.get("batch")

            if not q:
                return jsonify({"error": "Missing 'query' in request body"}), 400

            # Determine batch to use
            batch_id = batch or batch_manager.get_default_batch()
            if not batch_id:
                return jsonify({"error": "No batch specified and no default batch set"}), 400

            if not batch_manager.switch_batch(batch_id):
                return jsonify({"error": f"Failed to switch to batch '{batch_id}'"}), 400

            qp = QueryProcessor(batch_manager)
            resp = qp.process_query(q)
            return jsonify({"response": resp, "batch": batch_id})
            
        except Exception as e:
            print(f"Error processing query: {str(e)}")
            print(traceback.format_exc())  # Detailed error log
            return jsonify({"error": str(e)}), 500

    print(f"Starting API server at http://{host}:{port}")
    app.run(host=host, port=port)

def main():
    parser = argparse.ArgumentParser(description="Domain-Agnostic Document Chatbot")

    # Main query argument
    parser.add_argument("query", nargs="?", help="Question to ask the chatbot")

    # Batch management options
    parser.add_argument("--batch", help="Specify which document batch to use")
    parser.add_argument("--list-batches", action="store_true", help="List all available batches")
    parser.add_argument("--batch-info", help="Show information about a specific batch")
    parser.add_argument("--set-default", help="Set default batch for queries")

    # API/server mode for React UI
    parser.add_argument("--serve", action="store_true", help="Run HTTP API server for React UI")
    parser.add_argument("--port", type=int, default=5000, help="Port for API server (default: 5000)")

    args = parser.parse_args()

    try:
        # Initialize managers
        batch_manager = BatchManager()

        # If serve mode requested, start API server
        if args.serve:
            print(f"Starting API server on port {args.port} ...")
            run_api_server(batch_manager, port=args.port)
            return

        # Handle batch listing
        if args.list_batches:
            batches = batch_manager.list_batches()
            if not batches:
                print("No document batches found.")
                print("Create a batch using: python setup_batch.py <batch_name>")
                return

            print("Available batches:")
            for batch_id, info in batches.items():
                print(f"- {batch_id} ({info.get('doc_count', 0)} documents, created {info.get('created_at', 'unknown')})")
            return

        # Handle batch info
        if args.batch_info:
            info = batch_manager.get_batch_info(args.batch_info)
            if info:
                print(f"Batch: {args.batch_info}")
                print(f"Name: {info.get('name', 'Unknown')}")
                print(f"Description: {info.get('description', 'No description')}")
                print(f"Documents: {info.get('doc_count', 0)}")
                print(f"Created: {info.get('created_at', 'Unknown')}")
            else:
                print(f"Batch '{args.batch_info}' not found.")
            return

        # Handle setting default batch
        if args.set_default:
            if batch_manager.set_default_batch(args.set_default):
                print(f"Default batch set to: {args.set_default}")
            else:
                print(f"Batch '{args.set_default}' not found.")
            return

        # Handle query
        if not args.query:
            print("Please provide a question or use --help for options.")
            return

        # Determine which batch to use
        batch_id = args.batch or batch_manager.get_default_batch()
        if not batch_id:
            print("No batch specified and no default batch set.")
            print("Use --batch <batch_name> or set a default with --set-default <batch_name>")
            print("Available batches:")
            batches = batch_manager.list_batches()
            for bid in batches.keys():
                print(f"  - {bid}")
            return

        # Switch to specified batch
        if not batch_manager.switch_batch(batch_id):
            print(f"Failed to switch to batch '{batch_id}'.")
            return

        # Initialize query processor and process question
        query_processor = QueryProcessor(batch_manager)

        print(f"Using batch: {batch_id}")
        print(f"Question: {args.query}")
        print("Processing...")

        response = query_processor.process_query(args.query)

        print("\nResponse:")
        print("=" * 50)
        print(response)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()