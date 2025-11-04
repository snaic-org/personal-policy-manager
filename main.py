#!/usr/bin/env python3
"""
Domain-Agnostic Chatbot API Server
Main entry point for the user-facing web application.
Handles user registration, login, document upload, and querying.
"""

from dotenv import load_dotenv
load_dotenv()

import argparse
import sys
import os
import json
import traceback
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from batch_manager import BatchManager
from query_processor import QueryProcessor
from document_processor import DocumentProcessor

# --- App Initialization ---

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# --- Configuration ---
# Make sure your .env file has your JWT_SECRET_KEY
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-fallback-key-for-dev') 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)
app.config['UPLOAD_FOLDER'] = 'documents' # We'll create subfolders per user

# --- Initialize Extensions ---
db = SQLAlchemy(app)
jwt = JWTManager(app)

# --- Initialize Chatbot Components ---
batch_manager = BatchManager()
query_processor = QueryProcessor(batch_manager)
doc_processor = DocumentProcessor()

# --- Database Model ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_batch_id(self):
        """Returns the user-specific batch_id."""
        return f"user_{self.id}"

# --- Authentication Endpoints ---

@app.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    password_confirm = data.get("passwordConfirm")

    if not username or not password or not password_confirm:
        return jsonify({"error": "Username and password, and password confirmation are required"}), 400

    if password != password_confirm:
        return jsonify({"error": "Passwords do not match"}), 400
    
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409

    new_user = User(username=username)
    new_user.set_password(password)
    
    db.session.add(new_user)
    db.session.commit()
    
    # Also create their document upload directory
    user_doc_dir = Path(app.config['UPLOAD_FOLDER']) / new_user.get_batch_id()
    user_doc_dir.mkdir(parents=True, exist_ok=True)

    return jsonify({"message": "User registered successfully"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401

    access_token = create_access_token(identity=str(user.id))
    return jsonify(access_token=access_token)

@app.route("/me", methods=["GET"])
@jwt_required()
def get_user_info():
    """Gets the current logged-in user's details."""
    try:
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)
        
        user = db.session.get(User, user_id_int)
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        return jsonify({
            "id": user.id,
            "username": user.username
        }), 200
        
    except Exception as e:
        print(f"Error getting user info: {str(e)}")
        return jsonify({"error": str(e)}), 500


# --- Document Management Endpoints ---

@app.route("/upload", methods=["POST"])
@jwt_required()
def upload_policies():
    try:
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)
        
        user = db.session.get(User, user_id_int) # Use the integer ID here
        if not user:
            return jsonify({"error": "User not found"}), 404
            
        batch_id = user.get_batch_id()
        user_doc_dir = Path(app.config['UPLOAD_FOLDER']) / batch_id
        
        if 'files' not in request.files:
            return jsonify({"error": "No files part in request"}), 400
        
        files = request.files.getlist('files')
        if not files:
             return jsonify({"error": "No files selected"}), 400

        saved_files = []
        processed_filenames = [] 
        
        for file in files:
            if not file.filename or file.filename.strip() == "":
                continue  
                
            filename = secure_filename(file.filename)
            
            if not filename:
                continue
                
            filepath = user_doc_dir / filename
            file.save(filepath)
            saved_files.append(str(filepath))
            processed_filenames.append(filename)
        
        if not saved_files:
            return jsonify({"error": "No valid files were saved. Check filenames."}), 400

        print(f"Processing batch '{batch_id}' with {len(saved_files)} files...")
        
        # --- Trigger Batch Processing ---
        user_doc_path = f"documents/{batch_id}/"
        document_files = []
        for ext in ['*.pdf', '*.docx', '*.txt', '*.md']:
            document_files.extend(Path(user_doc_path).glob(ext))
            
        if not document_files:
            return jsonify({"error": "No processable documents found after upload."}), 400

        success = doc_processor.create_batch(
            batch_id=batch_id,
            document_paths=[str(doc) for doc in document_files],
            batch_name=f"{user.username}'s Policies",
            description=f"Personal policies for user {user.username}"
        )
        
        if not success:
            return jsonify({"error": "Failed to process documents"}), 500

        return jsonify({"message": f"Successfully uploaded and processed: {', '.join(processed_filenames)}"}), 201

    except Exception as e:
        print(f"Error processing upload: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    

@app.route('/delete_file', methods=['POST'])
@jwt_required()
def delete_file():
    """Deletes a file and re-processes the user's batch."""
    try:
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)
        user = db.session.get(User, user_id_int)
        if not user:
            return jsonify({"error": "User not found"}), 404

        data = request.get_json()
        filename = data.get("filename")
        if not filename:
            return jsonify({"error": "Filename is required"}), 400

        # Secure the filename
        safe_filename = secure_filename(filename)
        if safe_filename != filename:
            return jsonify({"error": "Invalid filename"}), 400

        batch_id = user.get_batch_id()
        user_doc_dir = Path(app.config['UPLOAD_FOLDER']) / batch_id
        filepath = user_doc_dir / safe_filename

        if not filepath.exists():
            return jsonify({"error": "File not found"}), 404

        # 1. Delete the file
        os.remove(filepath)
        print(f"Deleted file: {filepath}")

        # 2. Re-process the batch
        # Find all *remaining* document files
        document_files = []
        for ext in ['*.pdf', '*.docx', '*.txt', '*.md']:
            document_files.extend(Path(user_doc_dir).glob(ext))

        if not document_files:
            # User deleted their last file. Remove the batch entirely.
            if batch_manager.delete_batch(batch_id):
                print(f"User deleted last file. Batch '{batch_id}' removed.")
                return jsonify({"message": f"Successfully deleted {filename}. All policies removed."})
            else:
                return jsonify({"error": "Failed to delete final batch"}), 500
        
        # User still has files, re-create the batch
        print(f"Re-processing batch '{batch_id}' with {len(document_files)} remaining files...")
        success = doc_processor.create_batch(
            batch_id=batch_id,
            document_paths=[str(doc) for doc in document_files],
            batch_name=f"{user.username}'s Policies",
            description=f"Personal policies for user {user.username}"
        )

        if not success:
            return jsonify({"error": "File deleted, but failed to re-process remaining documents"}), 500

        return jsonify({"message": f"Successfully deleted {filename} and re-processed policies."}), 200

    except Exception as e:
        print(f"Error deleting file: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500


@app.route('/list_files', methods=['GET'])
@jwt_required()
def list_files():
    user_id_str = get_jwt_identity()
    user_id_int = int(user_id_str)
    user = db.session.get(User, user_id_int)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    batch_id = user.get_batch_id() # e.g., "user_1"
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], batch_id)

    if not os.path.exists(user_folder):
        return jsonify({"files": []})

    files = os.listdir(user_folder)
    return jsonify({"files": files})

# --- Chatbot Endpoints ---

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/query", methods=["POST"])
@jwt_required()
def query_endpoint():
    try:
        # 1. Get user ID from their token
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)

        user = db.session.get(User, user_id_int) # Use the integer ID here
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        # 2. The user's batch_id is their unique ID
        batch_id = user.get_batch_id()
        
        data = request.get_json(force=True, silent=True) or {}
        q = data.get("query") or data.get("question")

        if not q:
            return jsonify({"error": "Missing 'query' in request body"}), 400

        # 3. Check if the user's batch exists (have they uploaded docs?)
        if not batch_manager.get_batch_info(batch_id):
            return jsonify({"response": "I can't answer that yet. Please upload your policy documents first using the 'Upload' button.", "batch": batch_id}), 200

        # 4. Switch the chatbot to use ONLY this user's batch
        if not batch_manager.switch_batch(batch_id):
            return jsonify({"error": f"Failed to switch to user batch '{batch_id}'"}), 400

        # 5. Process the query
        print(f"Processing query for batch: {batch_id}")
        resp = query_processor.process_query(q)
        return jsonify({"response": resp, "batch": batch_id})
        
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500

# --- Main Server ---
def run_api_server(host="0.0.0.0", port=5000):
    with app.app_context():
        db.create_all()  # Create database tables if they don't exist
    print(f"Starting API server at http://{host}:{port}")
    app.run(host=host, port=port)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    run_api_server(port=port)