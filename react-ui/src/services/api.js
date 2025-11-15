const BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000';

function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch (e) {
    return null;
  }
}

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

  const data = await res.json(); // data will be { access_token, role }
  localStorage.setItem('token', data.access_token);
  
  return data; // Returns { access_token, role }
}

// Customer Registration
export async function register(username, password, passwordConfirm, profileData) {
  const res = await fetch(`${BASE}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      password,
      passwordConfirm,
      name: profileData.name,
      date_of_birth: profileData.dob,
      gender: profileData.gender,
      smoking_status: profileData.smokingStatus
    })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function registerInsurer(username, password, passwordConfirm, inviteCode) {
  const res = await fetch(`${BASE}/register/insurer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password, passwordConfirm, inviteCode })
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

// --- Document Management Functions ---

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

export async function deletePolicies(filenames) {
  const res = await fetch(`${BASE}/delete_files`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    },
    body: JSON.stringify({ filenames })
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Unknown error' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  return res.json();
}

export function getFileUrl(filename) {
  // Returns the full URL for a file in the user's document folder
  // Used for opening files in new tabs via citation links
  return `${BASE}/files/${filename}`;
}

export async function downloadFile(filename) {
  // Downloads a file from the user's document folder
  try {
    const token = localStorage.getItem('token');
    if (!token) {
      throw new Error('Not authenticated');
    }

    const response = await fetch(`${BASE}/files/${filename}`, {
      headers: {
        'Authorization': `Bearer ${token}`
      }
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to download file' }));
      throw new Error(error.error || 'Failed to download file');
    }

    // Get the file as a blob
    const blob = await response.blob();
    
    // Create a blob URL
    const blobUrl = URL.createObjectURL(blob);
    
    // Create a temporary anchor element to trigger download
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = filename; // This triggers download instead of opening
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Clean up the blob URL
    setTimeout(() => URL.revokeObjectURL(blobUrl), 100);
  } catch (error) {
    console.error('Error downloading file:', error);
    throw error;
  }
}

  // --- Chatbot Functions ---
  
  export async function getHistory() {
    const res = await fetch(`${BASE}/history`, {
      method: 'GET',
      headers: {
        ...getAuthHeader()
      }
    });
  
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(err.error || `HTTP ${res.status}`);
    }
    
    return res.json(); // returns [{ role: 'user', content: '...' }, ...]
  }

  export async function clearHistory() {
    const res = await fetch(`${BASE}/history`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeader()
      }
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(err.error || `HTTP ${res.status}`);
    }

    return res.json();
  }
  
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
  
  export async function sendQueryStream(query, onChunk, onComplete, onError) {
    const body = { query };
  
    try {
      const res = await fetch(`${BASE}/query/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeader()
        },
        body: JSON.stringify(body)
      });
  
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(err.error || `HTTP ${res.status}`);
      }
  
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
  
      while (true) {
        const { done, value } = await reader.read();
  
        if (done) {
          break;
        }
  
        // Decode the chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });
  
        // Process complete SSE messages (separated by \n\n)
        const lines = buffer.split('\n\n');
        buffer = lines.pop(); // Keep incomplete message in buffer
  
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6)); // Remove 'data: ' prefix
  
              if (data.error) {
                onError(new Error(data.error));
                return;
              }

              let contentChunk = null;

              if (data.content) {
                // 1. Handle normal RAG content
                contentChunk = data.content;
              } else if (data.report) {
                // 2. Handle deep research 'report'
                contentChunk = data.report;
              } else if (data.answer) {
                // 3. Handle deep research 'answer'
                contentChunk = data.answer;
              }

              // Send the chunk if we found one
              if (contentChunk) {
                onChunk(contentChunk);
              }
              
              // Handle 'done' signal
              if (data.done) {
                onComplete();
                return;
              }
            } catch (e) {
              console.error('Error parsing SSE data:', e);
            }
          }
        }
      }
  
      onComplete();
    } catch (e) {
      onError(e);
    }
  }

// --- User Profile Functions ---

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

export async function getProfile() {
  const res = await fetch(`${BASE}/profile`, {
    method: 'GET',
    headers: {
      ...getAuthHeader()
    }
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Failed to fetch profile' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }
  
  return res.json(); // returns profile JSON
}

export async function saveProfile(profileData) {
  const res = await fetch(`${BASE}/profile`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    },
    body: JSON.stringify(profileData)
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: 'Failed to save profile' }));
    throw new Error(err.error || `HTTP ${res.status}`);
  }

  return res.json(); // returns { message: "..." }
}

// --- Insurer Functions ---
/**
 * (Insurer) Get all customers managed by this insurer.
 */
export async function getInsurerCustomers() {
  const res = await fetch(`${BASE}/api/insurer/customers`, {
    method: 'GET',
    headers: { ...getAuthHeader() }
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json(); // Returns [{ id: 1, username: 'customer_a' }, ...]
}

/**
 * (Insurer) Create a new customer.
 */
export async function createCustomer(profileData) {
  const res = await fetch(`${BASE}/api/insurer/customers`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    },
    body: JSON.stringify({
      username: profileData.username,
      name: profileData.name,
      date_of_birth: profileData.dob,
      gender: profileData.gender,
      smoking_status: profileData.smokingStatus
    })
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json(); // Returns { message, customer_id, username, password }
}

/**
 * (Insurer) Get the file list for a specific customer.
 */
export async function getInsurerCustomerFiles(customerId) {
  const res = await fetch(`${BASE}/api/insurer/list_files/${customerId}`, {
    // Note: This endpoint needs to be created in main.py
    // It should be an @insurer_required endpoint that proxies
    // the logic of /list_files for a specific user.
    method: 'GET',
    headers: { ...getAuthHeader() }
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json(); // Returns { files: ["a.pdf", "b.docx"] }
}

/**
 * (Insurer) Upload policies for a specific customer.
 */
export async function uploadForCustomer(customerId, files) {
  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file);
  });
  
  const res = await fetch(`${BASE}/api/insurer/upload/${customerId}`, {
    method: 'POST',
    headers: { ...getAuthHeader() },
    body: formData
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json();
}

/**
 * (Insurer) Delete policies for a specific customer.
 */
export async function deleteForCustomer(customerId, filenames) {
  const res = await fetch(`${BASE}/api/insurer/delete_files/${customerId}`, {
    // Note: This endpoint also needs to be created in main.py
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    },
    body: JSON.stringify({ filenames })
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json();
}

/**
 * (Insurer) Get chat history for a specific customer.
 */
export async function getInsurerHistory(customerId) {
  const res = await fetch(`${BASE}/api/insurer/history/${customerId}`, {
    // Note: This endpoint needs to be created in main.py
    method: 'GET',
    headers: { ...getAuthHeader() }
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json();
}

/**
 * (Insurer) Clear chat history for a specific customer.
 */
export async function clearInsurerHistory(customerId) {
  const res = await fetch(`${BASE}/api/insurer/history/${customerId}`, {
    method: 'DELETE',
    headers: { ...getAuthHeader() }
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json();
}

/**
 * (Insurer) Send a query as the insurer for a specific customer.
 */
export async function sendInsurerQueryStream(customerId, query, onChunk, onComplete, onError) {
  const body = { query };
  try {
    const res = await fetch(`${BASE}/api/insurer/query/stream/${customerId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeader()
      },
      body: JSON.stringify(body)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Unknown error' }));
      throw new Error(err.error || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop();
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.substring(6));
            if (data.error) {
              onError(new Error(data.error));
              return;
            }

            let contentChunk = null;

            if (data.content) {
              // 1. Handle normal RAG content
              contentChunk = data.content;
            } else if (data.report) {
              // 2. Handle deep research 'report'
              contentChunk = data.report;
            } else if (data.answer) {
              // 3. Handle deep research 'answer'
              contentChunk = data.answer;
            }

            // Send the chunk if we found one
            if (contentChunk) {
              onChunk(contentChunk);
            }
            
            // Handle 'done' signal
            if (data.done) {
              onComplete();
              return;
            }
          } catch (e) { console.error('Error parsing SSE data:', e); }
        }
      }
    }
    onComplete();
  } catch (e) {
    onError(e);
  }
}

/**
 * (Insurer) Get the profile for a specific customer.
 */
export async function getInsurerProfile(customerId) {
  const res = await fetch(`${BASE}/api/insurer/profile/${customerId}`, {
    method: 'GET',
    headers: { ...getAuthHeader() }
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json();
}

/**
 * (Insurer) Save the profile for a specific customer.
 */
export async function saveInsurerProfile(customerId, profileData) {
  const res = await fetch(`${BASE}/api/insurer/profile/${customerId}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader()
    },
    body: JSON.stringify(profileData)
  });
  if (!res.ok) throw new Error((await res.json()).error);
  return res.json();
}