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
from flask_jwt_extended import create_access_token, get_jwt_identity, jwt_required, JWTManager, get_jwt
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import timedelta, datetime, UTC
from functools import wraps
import secrets

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from batch_manager import BatchManager
from query_processor import QueryProcessor
from document_processor import DocumentProcessor

# --- App Initialization ---

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# --- Configuration ---
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'default-fallback-key-for-dev') 
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=1)
app.config['UPLOAD_FOLDER'] = 'documents'

INSURER_INVITE_CODE = os.getenv('INSURER_INVITE_CODE', 'default-insurer-invite-code-for-dev')
if INSURER_INVITE_CODE == 'default-insurer-invite-code-for-dev':
    print("WARNING: Using default INSURER_INVITE_CODE. Set this in your .env file for security.")

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
    role = db.Column(db.String(20), nullable=False, default='customer')
    created_by_insurer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
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

# --- Master Decorator ---

def get_target_customer(fn):
    """
    Master decorator to get the target customer for an action.
    - If actor is 'customer', target_customer is the actor.
    - If actor is 'insurer', target_customer is from <customer_id> in URL.
    Performs all auth and tenancy checks.
    Injects 'target_customer' and 'actor' into the decorated function.
    """
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        actor_id = int(get_jwt_identity())
        actor = db.session.get(User, actor_id)
        if not actor:
            return jsonify({"error": "Actor not found"}), 401

        customer_id_from_url = kwargs.get('customer_id')
        target_customer = None

        if actor.role == 'customer':
            if customer_id_from_url is not None:
                return jsonify({"error": "Customers cannot access other users' data"}), 403
            target_customer = actor
        
        elif actor.role == 'insurer':
            if customer_id_from_url is None:
                return jsonify({"error": "Insurer must specify a customer_id in URL"}), 400
            
            target_customer = db.session.get(User, customer_id_from_url)
            
            if not target_customer or target_customer.created_by_insurer_id != actor_id:
                return jsonify({"error": "Customer not found or not managed by you"}), 403
            
            # Clean kwargs before passing to function
            del kwargs['customer_id']

        else:
            return jsonify({"error": "Unauthorized role"}), 403
        
        if not target_customer:
             return jsonify({"error": "Could not determine target customer"}), 500

        # Inject both actor and target_customer
        return fn(target_customer=target_customer, actor=actor, *args, **kwargs)
    return wrapper

# --- Authentication Endpoints ---

@app.route("/register", methods=["POST"])
def register():
    """Registers a new customer account."""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    password_confirm = data.get("passwordConfirm")
    name = data.get("name")
    date_of_birth = data.get("date_of_birth")
    gender = data.get("gender")
    smoking_status = data.get("smoking_status")
    
    if not all([username, password, password_confirm, name, date_of_birth, gender, smoking_status]):
        return jsonify({"error": "All fields are required"}), 400
    if password != password_confirm:
        return jsonify({"error": "Passwords do not match"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409

    new_user = User(username=username, role='customer')
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    
    profile_data = {"name": name, "date_of_birth": date_of_birth, "gender": gender, "smoking_status": smoking_status}
    _create_user_profile(new_user, profile_data)
    
    (Path(app.config['UPLOAD_FOLDER']) / new_user.get_batch_id()).mkdir(parents=True, exist_ok=True)
    return jsonify({"message": "User registered successfully"}), 201

@app.route("/register/insurer", methods=["POST"])
def register_insurer():
    """Registers a new insurer account. Requires a valid invite code."""
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    password_confirm = data.get("passwordConfirm")
    invite_code = data.get("inviteCode")

    if not username or not password or not password_confirm:
        return jsonify({"error": "Username, password, and confirmation are required"}), 400
    if not invite_code:
        return jsonify({"error": "Invite code is required"}), 400
    if password != password_confirm:
        return jsonify({"error": "Passwords do not match"}), 400
    if invite_code != INSURER_INVITE_CODE:
        return jsonify({"error": "Invalid invite code"}), 403
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409

    new_user = User(username=username, role='insurer')
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Insurer account registered successfully"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401
    
    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={'role': user.role}
    )
    return jsonify(access_token=access_token, role=user.role)

@app.route("/me", methods=["GET"])
@jwt_required()
def get_user_info():
    """Gets the current logged-in user's details."""
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"id": user.id, "username": user.username}), 200

# --- Internal Helper Functions ---

def _get_user_profile_path(user: User) -> Path:
    """Returns the Path to the user's profile JSON file."""
    batch_id = user.get_batch_id()
    user_doc_dir = Path(app.config['UPLOAD_FOLDER']) / batch_id
    user_doc_dir.mkdir(parents=True, exist_ok=True)
    profile_path = user_doc_dir / "user_profile.json"
    return profile_path

def _create_user_profile(user: User, profile_data: dict[str, any]):
    """Saves the initial profile data for a new user."""
    profile_path = _get_user_profile_path(user)
    new_profile = {
        "name": profile_data.get("name"),
        "date_of_birth": profile_data.get("date_of_birth"),
        "gender": profile_data.get("gender"),
        "smoking_status": profile_data.get("smoking_status"),
        "insurance_policies": {}
    }
    try:
        with open(profile_path, "w") as f:
            json.dump(new_profile, f, indent=2)
    except Exception as e:
        print(f"Error creating user_profile.json for user {user.id}: {e}")

def _update_profile_on_delete(user: User, deleted_filenames: list[str]):
    """Updates the user's profile JSON file by removing references to deleted files."""
    profile_path = _get_user_profile_path(user)
    if not profile_path.exists(): return
    try:
        with open(profile_path, "r") as f:
            profile_data = json.load(f)
        if "insurance_policies" in profile_data:
            profile_data["insurance_policies"] = {
                filename: policy_data
                for filename, policy_data in profile_data["insurance_policies"].items()
                if filename not in deleted_filenames
            }
            with open(profile_path, "w") as f:
                json.dump(profile_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to update user profile for user {user.id} after file deletion: {e}")

# --- Internal Logic Functions ---

def _get_profile_logic(user: User):
    profile_path = _get_user_profile_path(user)
    if profile_path.exists():
        return send_file(profile_path, mimetype='application/json')
    else:
        return jsonify({})

def _save_profile_logic(user: User, data: dict[str, any]):
    if not data:
        return jsonify({"error": "No JSON data provided"}), 400
    profile_path = _get_user_profile_path(user)
    try:
        existing_profile = {}
        if profile_path.exists():
            with open(profile_path, "r") as f:
                existing_profile = json.load(f)
        merged_profile = {**existing_profile, **data}
        with open(profile_path, "w") as f:
            json.dump(merged_profile, f, indent=2)
        return jsonify({"message": "Profile saved successfully"}), 200
    except Exception as e:
        print(f"Error saving profile: {e}")
        return jsonify({"error": str(e)}), 500

def _list_files_logic(user: User):
    batch_id = user.get_batch_id()
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], batch_id)
    if not os.path.exists(user_folder):
        return jsonify({"files": []})
    files = [f for f in os.listdir(user_folder) if f != 'user_profile.json']
    return jsonify({"files": files})

def _get_history_logic(user: User, actor_role: str):
    messages = Message.query.filter_by(user_id=user.id).order_by(Message.timestamp.asc()).all()
    history = []
    for msg in messages:
        role_for_frontend = msg.role
        # Special case for insurer view
        if actor_role == 'insurer' and msg.role == 'insurer':
            role_for_frontend = 'user'
        history.append({"role": role_for_frontend, "content": msg.content})
    return jsonify(history), 200

def _clear_history_logic(user: User):
    try:
        num_deleted = Message.query.filter_by(user_id=user.id).delete()
        db.session.commit()
        return jsonify({"message": f"History cleared. {num_deleted} messages deleted."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

def _delete_files_logic(user: User, data: dict[str, any]):
    try:
        filenames = data.get("filenames")
        if not filenames or not isinstance(filenames, list):
            return jsonify({"error": "A list of 'filenames' is required"}), 400

        batch_id = user.get_batch_id()
        user_doc_dir = Path(app.config['UPLOAD_FOLDER']) / batch_id
        deleted_count = 0
        deleted_files_list = []

        for filename in filenames:
            safe_filename = secure_filename(filename)
            if safe_filename != filename: continue
            filepath = user_doc_dir / safe_filename
            if filepath.exists():
                os.remove(filepath)
                deleted_count += 1
                deleted_files_list.append(safe_filename)
        
        if deleted_count == 0:
            return jsonify({"error": "No valid files were found to delete"}), 404
        
        if deleted_files_list:
            _update_profile_on_delete(user, deleted_files_list)

        # Re-process the batch
        document_files = list(user_doc_dir.glob('*.pdf')) + \
                         list(user_doc_dir.glob('*.docx')) + \
                         list(user_doc_dir.glob('*.txt')) + \
                         list(user_doc_dir.glob('*.md'))

        if not document_files:
            batch_manager.delete_batch(batch_id)
            return jsonify({"message": f"Successfully deleted {deleted_count} files. All policies removed."})
        
        doc_processor.create_batch(
            batch_id=batch_id,
            document_paths=[str(doc) for doc in document_files],
            batch_name=f"{user.username}'s Policies",
            description=f"Personal policies for user {user.username}"
        )
        return jsonify({"message": f"Successfully deleted {deleted_count} files and re-processed policies."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _upload_files_logic(user: User, files_from_request):
    try:
        if not files_from_request:
             return jsonify({"error": "No files selected"}), 400

        batch_id = user.get_batch_id()
        user_doc_dir = Path(app.config['UPLOAD_FOLDER']) / batch_id
        saved_files = []
        processed_filenames = [] 
        
        for file in files_from_request:
            filename = secure_filename(file.filename)
            if not filename or filename.strip() == "": continue
            filepath = user_doc_dir / filename
            file.save(filepath)
            saved_files.append(str(filepath))
            processed_filenames.append(filename)
        
        if not saved_files:
            return jsonify({"error": "No valid files were saved. Check filenames."}), 400
        
        # --- Update user_profile.json ---
        profile_path = _get_user_profile_path(user)
        existing_profile = {}
        if profile_path.exists():
            try:
                with open(profile_path, "r") as f: existing_profile = json.load(f)
            except json.JSONDecodeError: pass
        
        insurance_policies = existing_profile.get("insurance_policies", {})
        new_policies_added = False
        for filename in processed_filenames:
            if filename not in insurance_policies:
                insurance_policies[filename] = {"policy_type": "", "insurer": "", "plan_name": "", "underwriting": {}}
                new_policies_added = True
        
        if new_policies_added:
            existing_profile["insurance_policies"] = insurance_policies
            with open(profile_path, "w") as f: json.dump(existing_profile, f, indent=2)

        # --- Trigger Batch Processing ---
        document_files = list(user_doc_dir.glob('*.pdf')) + \
                         list(user_doc_dir.glob('*.docx')) + \
                         list(user_doc_dir.glob('*.txt')) + \
                         list(user_doc_dir.glob('*.md'))
            
        if not document_files:
            return jsonify({"error": "No processable documents found after upload."}), 400

        doc_processor.create_batch(
            batch_id=batch_id,
            document_paths=[str(doc) for doc in document_files],
            batch_name=f"{user.username}'s Policies",
            description=f"Personal policies for user {user.username}"
        )
        return jsonify({"message": f"Successfully uploaded and processed: {', '.join(processed_filenames)}"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def _query_stream_logic(user: User, data: dict[str, any]):
    user_profile = None
    profile_path = _get_user_profile_path(user)
    if profile_path.exists():
        try:
            with open(profile_path, "r") as f: user_profile = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load profile for user {user.id}: {e}")

    batch_id = user.get_batch_id()
    q = data.get("query")
    if not q:
        return jsonify({"error": "Missing 'query' in request body"}), 400

    # Save the user's question
    user_message = Message(user_id=user.id, role="user", content=q)
    db.session.add(user_message)
    db.session.commit()

    if not batch_manager.get_batch_info(batch_id):
        response_text = "I can't answer that yet. Please upload your policy documents first."
        bot_message = Message(user_id=user.id, role="bot", content=response_text)
        db.session.add(bot_message)
        db.session.commit()
        def error_stream():
            yield "data: " + json.dumps({"content": response_text, "done": True}) + "\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    if not batch_manager.switch_batch(batch_id):
        def error_stream():
            yield "data: " + json.dumps({"error": f"Failed to switch to user batch '{batch_id}'"}) + "\n\n"
        return Response(stream_with_context(error_stream()), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

    def generate():
        full_response = []
        try:
            for chunk in query_processor.process_query_stream(q, batch_id=batch_id, user_profile=user_profile):
                yield chunk
                try:
                    chunk_data = json.loads(chunk.replace("data: ", "").strip())
                    content = chunk_data.get("content") or chunk_data.get("report") or chunk_data.get("answer")
                    if content:
                        full_response.append(content)
                except: pass
            
            complete_response = "".join(full_response)
            if complete_response:
                bot_message = Message(user_id=user.id, role="bot", content=complete_response)
                db.session.add(bot_message)
                db.session.commit()
        except Exception as e:
            print(f"Error during streaming: {str(e)}")
            yield "data: " + json.dumps({"error": str(e)}) + "\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

# --- Unified Data Endpoints

@app.route("/api/data/profile", methods=["GET"])
@app.route("/api/data/profile/<int:customer_id>", methods=["GET"])
@get_target_customer
def get_profile(target_customer, actor):
    return _get_profile_logic(target_customer)

@app.route("/api/data/profile", methods=["POST"])
@app.route("/api/data/profile/<int:customer_id>", methods=["POST"])
@get_target_customer
def save_profile(target_customer, actor):
    data = request.get_json()
    return _save_profile_logic(target_customer, data)

@app.route("/api/data/files", methods=["GET"])
@app.route("/api/data/files/<int:customer_id>", methods=["GET"])
@get_target_customer
def list_customer_files(target_customer, actor):
    return _list_files_logic(target_customer)

@app.route("/api/data/files/upload", methods=["POST"])
@app.route("/api/data/files/upload/<int:customer_id>", methods=["POST"])
@get_target_customer
def upload_customer_files(target_customer, actor):
    if 'files' not in request.files:
        return jsonify({"error": "No files part in request"}), 400
    files = request.files.getlist('files')
    return _upload_files_logic(target_customer, files)

@app.route("/api/data/files/delete", methods=["POST"])
@app.route("/api/data/files/delete/<int:customer_id>", methods=["POST"])
@get_target_customer
def delete_customer_files(target_customer, actor):
    data = request.get_json()
    return _delete_files_logic(target_customer, data)

@app.route("/api/data/history", methods=["GET"])
@app.route("/api/data/history/<int:customer_id>", methods=["GET"])
@get_target_customer
def get_customer_history(target_customer, actor):
    return _get_history_logic(target_customer, actor.role)

@app.route("/api/data/history", methods=["DELETE"])
@app.route("/api/data/history/<int:customer_id>", methods=["DELETE"])
@get_target_customer
def clear_customer_history(target_customer, actor):
    return _clear_history_logic(target_customer)

@app.route("/api/data/query/stream", methods=["POST"])
@app.route("/api/data/query/stream/<int:customer_id>", methods=["POST"])
@get_target_customer
def stream_customer_query(target_customer, actor):
    data = request.get_json()
    return _query_stream_logic(target_customer, data)

# --- File Serving ---

@app.route('/files/<filename>', methods=['GET'])
@jwt_required()
def serve_file(filename):
    """Serves a file from the authenticated user's document folder."""
    try:
        actor_id = int(get_jwt_identity())
        actor = db.session.get(User, actor_id)
        if not actor:
            return jsonify({"error": "User not found"}), 404
        
        safe_filename = secure_filename(filename)
        if not safe_filename or safe_filename != filename:
            return jsonify({"error": "Invalid filename"}), 400

        target_customer = None
        
        if actor.role == 'customer':
            target_customer = actor
        elif actor.role == 'insurer':
            # This is tricky. How do we know *which* customer's file it is?
            # We have to find the user based on the batch_id.
            # This is a flaw in the original design.
            # Let's assume for now the insurer *can't* download files
            # until we have a better way to map filename to user.
            # ...
            # A-HA! The file is in a *folder* named `user_1`, `user_2` etc.
            # We can't know which user it is from filename alone.
            # The ORIGINAL code had this flaw too.
            #
            # Let's fix this. We'll require the `customer_id` for insurers.
            # But... the citation links don't have that.
            #
            # FOR NOW: We will assume `/files/<filename>` is ONLY for customers
            # viewing their own files. This is a security patch.
            
            # --- SECURITY PATCH ---
            if actor.role == 'insurer':
                 return jsonify({"error": "Insurer file download not supported via this endpoint. Use customer-specific link."}), 403
            # --- END PATCH ---
            
            target_customer = actor # (This line is now only for customers)

        if not target_customer:
            return jsonify({"error": "Unauthorized"}), 403
            
        # Construct path to user's file
        batch_id = target_customer.get_batch_id()
        user_folder = Path(app.config['UPLOAD_FOLDER']) / batch_id
        file_path = user_folder / safe_filename

        if not file_path.resolve().is_relative_to(user_folder.resolve()):
            return jsonify({"error": "Unauthorized access"}), 403
        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404

        content_type = 'application/octet-stream'
        if '.pdf' in safe_filename.lower(): content_type = 'application/pdf'
        elif '.docx' in safe_filename.lower(): content_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif '.txt' in safe_filename.lower(): content_type = 'text/plain'
        
        return send_file(file_path, mimetype=content_type, as_attachment=False, download_name=safe_filename)
    except Exception as e:
        return jsonify({"error": "Failed to serve file"}), 500
    
# --- Insurer-Only Endpoints ---

@app.route("/api/insurer/customers", methods=["POST"])
@jwt_required()
def create_customer():
    actor_id = int(get_jwt_identity())
    actor = db.session.get(User, actor_id)
    if not actor or actor.role != 'insurer':
        return jsonify({"error": "Insurer access required"}), 403

    data = request.get_json()
    username = data.get("username")
    name = data.get("name")
    date_of_birth = data.get("date_of_birth")
    gender = data.get("gender")
    smoking_status = data.get("smoking_status")
    
    if not all([username, name, date_of_birth, gender, smoking_status]):
        return jsonify({"error": "All fields are required"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409

    password = secrets.token_urlsafe(16)
    new_customer = User(
        username=username,
        role='customer',
        created_by_insurer_id=actor_id
    )
    new_customer.set_password(password)
    db.session.add(new_customer)
    db.session.commit()
    
    profile_data = {"name": name, "date_of_birth": date_of_birth, "gender": gender, "smoking_status": smoking_status}
    _create_user_profile(new_customer, profile_data)
    (Path(app.config['UPLOAD_FOLDER']) / new_customer.get_batch_id()).mkdir(parents=True, exist_ok=True)
    
    return jsonify({
        "message": "Customer created successfully",
        "customer_id": new_customer.id,
        "username": new_customer.username,
        "password": password
    }), 201
    
@app.route("/api/insurer/customers", methods=["GET"])
@jwt_required()
def list_customers():
    actor_id = int(get_jwt_identity())
    actor = db.session.get(User, actor_id)
    if not actor or actor.role != 'insurer':
        return jsonify({"error": "Insurer access required"}), 403

    customers = User.query.filter_by(created_by_insurer_id=actor_id, role='customer').all()
    customer_list = [{"id": c.id, "username": c.username} for c in customers]
    return jsonify(customer_list), 200

# --- Main Server ---
def run_api_server(host="0.0.0.0", port=5000):
    with app.app_context():
        db.create_all()
    print(f"Starting API server at http://{host}:{port}")
    app.run(host=host, port=port)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    run_api_server(port=port)