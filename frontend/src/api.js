const TOKEN_KEY = "studymunch_token";

export const getToken = () => localStorage.getItem(TOKEN_KEY);
export const setToken = (token) => localStorage.setItem(TOKEN_KEY, token);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

async function request(path, options = {}) {
  const headers = { ...options.headers };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  const res = await fetch(`/api${path}`, { ...options, headers });
  const data = await res.json().catch(() => null); // some responses have no body

  if (!res.ok) {
    // HTTPException  → { detail: "Username already taken" }
    // Pydantic (422) → { detail: [{ msg: "String should have at least 8 characters", ... }] }
    const detail = data?.detail;
    const message = Array.isArray(detail) ? detail[0]?.msg : detail;
    throw new Error(message || `Request failed (${res.status})`);
  }
  return data;
}

// JSON body, because register() takes a Pydantic UserCreate
export function register(username, password) {
  return request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
}

// FORM body, because login() takes OAuth2PasswordRequestForm
export async function login(username, password) {
  const data = await request("/auth/token", {
    method: "POST",
    body: new URLSearchParams({ username, password }),
  });
  setToken(data.access_token);
}

export const getMe = () => request("/auth/me");