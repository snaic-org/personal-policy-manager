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
from flask import Flask, request, jsonify, Response, stream_with_context, send_file
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta, datetime, UTC

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

# --- Message Model ---

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(10), nullable=False) # 'user' or 'bot'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(UTC))

    user = db.relationship('User', backref=db.backref('messages', lazy=True))

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
    
@app.route('/delete_files', methods=['POST'])
@jwt_required()
def delete_files():
    """Deletes one or more files and re-processes the user's batch once."""
    try:
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)
        user = db.session.get(User, user_id_int)
        if not user:
            return jsonify({"error": "User not found"}), 404

        data = request.get_json()
        filenames = data.get("filenames")
        if not filenames or not isinstance(filenames, list):
            return jsonify({"error": "A list of 'filenames' is required"}), 400

        batch_id = user.get_batch_id()
        user_doc_dir = Path(app.config['UPLOAD_FOLDER']) / batch_id
        
        deleted_count = 0
        deleted_files_list = []

        # 1. Delete all requested files first
        for filename in filenames:
            safe_filename = secure_filename(filename)
            if safe_filename != filename:
                print(f"Skipping invalid filename: {filename}")
                continue # Skip potentially malicious filenames

            filepath = user_doc_dir / safe_filename

            if filepath.exists():
                os.remove(filepath)
                deleted_count += 1
                deleted_files_list.append(safe_filename)
                print(f"Deleted file: {filepath}")
            else:
                print(f"File not found, skipping: {filepath}")

        if deleted_count == 0:
            return jsonify({"error": "No valid files were found to delete"}), 404


        # 2. Re-process the batch *once*
        # Find all *remaining* document files
        document_files = []
        for ext in ['*.pdf', '*.docx', '*.txt', '*.md']:
            document_files.extend(Path(user_doc_dir).glob(ext))

        if not document_files:
            # User deleted their last file(s). Remove the batch entirely.
            if batch_manager.delete_batch(batch_id):
                print(f"User deleted last files. Batch '{batch_id}' removed.")
                return jsonify({"message": f"Successfully deleted {deleted_count} files. All policies removed."})
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
            return jsonify({"error": "Files deleted, but failed to re-process remaining documents"}), 500

        return jsonify({"message": f"Successfully deleted {deleted_count} files and re-processed policies."}), 200

    except Exception as e:
        print(f"Error deleting files: {str(e)}")
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

@app.route('/files/<filename>', methods=['GET'])
@jwt_required()
def serve_file(filename):
    """Serve a file from the user's document folder."""
    try:
        # Get user ID from JWT token
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)

        user = db.session.get(User, user_id_int)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Sanitize filename to prevent directory traversal
        safe_filename = secure_filename(filename)
        if not safe_filename or safe_filename != filename:
            return jsonify({"error": "Invalid filename"}), 400

        # Construct path to user's file
        batch_id = user.get_batch_id()
        user_folder = Path(app.config['UPLOAD_FOLDER']) / batch_id
        file_path = user_folder / safe_filename

        # Verify file exists and is within user's directory
        try:
            # Resolve to absolute path and check it's within user's folder
            resolved_path = file_path.resolve()
            resolved_user_folder = user_folder.resolve()

            if not str(resolved_path).startswith(str(resolved_user_folder)):
                return jsonify({"error": "Unauthorized access"}), 403

            if not resolved_path.exists() or not resolved_path.is_file():
                return jsonify({"error": "File not found"}), 404

        except Exception as e:
            print(f"Error resolving file path: {e}")
            return jsonify({"error": "File not found"}), 404

        # Determine content type based on file extension
        file_ext = safe_filename.lower().split('.')[-1]
        content_type_map = {
            'pdf': 'application/pdf',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'txt': 'text/plain',
            'md': 'text/markdown'
        }
        content_type = content_type_map.get(file_ext, 'application/octet-stream')

        # Serve the file
        return send_file(
            resolved_path,
            mimetype=content_type,
            as_attachment=False,  # Display inline in browser
            download_name=safe_filename
        )

    except Exception as e:
        print(f"Error serving file: {str(e)}")
        print(traceback.format_exc())
        return jsonify({"error": "Failed to serve file"}), 500

# --- Chatbot Endpoints ---

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})

@app.route("/history", methods=["GET"])
@jwt_required()
def get_history():
    """Gets the current user's chat history."""
    try:
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)
        
        messages = Message.query.filter_by(user_id=user_id_int).order_by(Message.timestamp.asc()).all()
        
        history = [{"role": msg.role, "content": msg.content} for msg in messages]
        return jsonify(history), 200
        
    except Exception as e:
        print(f"Error getting history: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/query", methods=["POST"])
@jwt_required()
def query_endpoint():
    try:
        # 1. Get user ID from their token
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)

        user = db.session.get(User, user_id_int)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # 2. The user's batch_id is their unique ID
        batch_id = user.get_batch_id()
        data = request.get_json(force=True, silent=True) or {}
        q = data.get("query") or data.get("question")
        if not q:
            return jsonify({"error": "Missing 'query' in request body"}), 400

        # Save the user's question to the database
        user_message = Message(user_id=user_id_int, role="user", content=q)
        db.session.add(user_message)

        # 3. Check if the user's batch exists (have they uploaded docs?)
        if not batch_manager.get_batch_info(batch_id):
            response_text = "I can't answer that yet. Please upload your policy documents first using the 'Upload' button."
            bot_message = Message(user_id=user_id_int, role="bot", content=response_text)
            db.session.add(bot_message)
            db.session.commit() # Commit both messages
            return jsonify({"response": response_text, "batch": batch_id}), 200

        # 4. Switch the chatbot to use ONLY this user's batch
        if not batch_manager.switch_batch(batch_id):
            return jsonify({"error": f"Failed to switch to user batch '{batch_id}'"}), 400

        # 5. Process the query
        print(f"Processing query for batch: {batch_id}")
        resp = query_processor.process_query(q, batch_id=batch_id)

        # Save the bot's response to the database
        bot_message = Message(user_id=user_id_int, role="bot", content=resp)
        db.session.add(bot_message)
        db.session.commit() # Commit both user and bot messages

        return jsonify({"response": resp, "batch": batch_id})

    except Exception as e:
        print(f"Error processing query: {str(e)}")
        print(traceback.format_exc())
        db.session.rollback() # Rollback if any error occurs
        return jsonify({"error": str(e)}), 500

@app.route("/query/stream", methods=["POST"])
@jwt_required()
def query_stream_endpoint():
    try:
        # 1. Get user ID from their token
        user_id_str = get_jwt_identity()
        user_id_int = int(user_id_str)

        user = db.session.get(User, user_id_int)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # 2. The user's batch_id is their unique ID
        batch_id = user.get_batch_id()
        data = request.get_json(force=True, silent=True) or {}
        q = data.get("query") or data.get("question")
        if not q:
            return jsonify({"error": "Missing 'query' in request body"}), 400

        # Save the user's question to the database
        user_message = Message(user_id=user_id_int, role="user", content=q)
        db.session.add(user_message)
        db.session.commit()

        # 3. Check if the user's batch exists (have they uploaded docs?)
        if not batch_manager.get_batch_info(batch_id):
            response_text = "I can't answer that yet. Please upload your policy documents first using the 'Upload' button."
            bot_message = Message(user_id=user_id_int, role="bot", content=response_text)
            db.session.add(bot_message)
            db.session.commit()

            def error_stream():
                yield "data: " + json.dumps({"content": response_text, "done": True}) + "\n\n"

            return Response(stream_with_context(error_stream()),
                          mimetype='text/event-stream',
                          headers={
                              'Cache-Control': 'no-cache',
                              'X-Accel-Buffering': 'no'
                          })

        # 4. Switch the chatbot to use ONLY this user's batch
        if not batch_manager.switch_batch(batch_id):
            def error_stream():
                yield "data: " + json.dumps({"error": f"Failed to switch to user batch '{batch_id}'"}) + "\n\n"

            return Response(stream_with_context(error_stream()),
                          mimetype='text/event-stream',
                          headers={
                              'Cache-Control': 'no-cache',
                              'X-Accel-Buffering': 'no'
                          })

        # 5. Stream the query processing
        print(f"Streaming query for batch: {batch_id}")

        def generate():
            full_response = []
            try:
                for chunk in query_processor.process_query_stream(q, batch_id=batch_id):
                    yield chunk
                    # Accumulate response content for database storage
                    try:
                        chunk_data = json.loads(chunk.replace("data: ", "").strip())
                        if "content" in chunk_data:
                            full_response.append(chunk_data["content"])
                    except:
                        pass

                # Save the complete bot response to the database
                complete_response = "".join(full_response)
                if complete_response:
                    bot_message = Message(user_id=user_id_int, role="bot", content=complete_response)
                    db.session.add(bot_message)
                    db.session.commit()

            except Exception as e:
                print(f"Error during streaming: {str(e)}")
                print(traceback.format_exc())
                yield "data: " + json.dumps({"error": str(e)}) + "\n\n"

        return Response(stream_with_context(generate()),
                       mimetype='text/event-stream',
                       headers={
                           'Cache-Control': 'no-cache',
                           'X-Accel-Buffering': 'no'
                       })

    except Exception as e:
        print(f"Error processing streaming query: {str(e)}")
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