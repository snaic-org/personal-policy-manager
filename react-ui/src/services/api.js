const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

// --- Auth Functions ---

export async function login(username, password) {
  const res = await fetch(`${BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  const data = await res.json();
  localStorage.setItem('token', data.access_token);
  return data.access_token;
}

export async function register(username, password, passwordConfirm) {
  const res = await fetch(`${BASE}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, passwordConfirm })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export function logout() {
  localStorage.removeItem('token');
}

// --- Helper to get Auth Header ---

function getAuthHeader() {
  const token = localStorage.getItem('token');
  if (!token) return {};
  return { 'Authorization': `Bearer ${token}` };
}

export async function getUserInfo() {
  const res = await fetch(`${BASE}/me`, {
    method: 'GET',
    headers: {
      ...getAuthHeader()
    }
  });
  
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  
  return res.json(); // returns { id: 1, username: 'testuser' }
}

// --- Chatbot Functions ---

export async function sendQuery(query) {
  const body = { query };
  
  const res = await fetch(`${BASE}/query`, {
    method: 'POST',
    headers: { 
      'Content-Type': 'application/json',
      ...getAuthHeader() // Add our token to the request
    },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  return res.json();
}

// --- Upload Function ---

export async function uploadPolicies(files) {
  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file);
  });

  const res = await fetch(`${BASE}/upload`, {
    method: 'POST',
    headers: {
      ...getAuthHeader() // Secure this endpoint with our token
    },
    body: formData // No Content-Type header, browser will set it for FormData
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  return res.json();
}

// --- Get uploaded files Function ---
export async function getUserFiles() {
  const res = await fetch(`${BASE}/list_files`, {
    method: 'GET',
    headers: {
      ...getAuthHeader()
    }
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  return res.json(); // will return { files: ["a.pdf", "b.docx"] }
}

// --- Delete file Function ---
export async function deletePolicy(filename) {
  const res = await fetch(`${BASE}/delete_file`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    },
    body: JSON.stringify({ filename })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  return res.json();
}