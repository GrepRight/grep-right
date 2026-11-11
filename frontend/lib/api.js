const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function request(path, options) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options && options.headers) },
    });
  } catch {
    throw new Error("Cannot reach the API. Is the backend running?");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error((data && data.error && data.error.message) || `Request failed (${res.status})`);
  }
  return data;
}

export const api = {
  listRepositories: () => request("/api/repositories"),
  importRepository: (git_url) =>
    request("/api/repositories", { method: "POST", body: JSON.stringify({ git_url }) }),
  getRepository: (id) => request(`/api/repositories/${id}`),
  getStatus: (id) => request(`/api/repositories/${id}/status`),
  deleteRepository: (id) => request(`/api/repositories/${id}`, { method: "DELETE" }),
  listFiles: (id, path = "") =>
    request(`/api/repositories/${id}/files${path ? `?path=${encodeURIComponent(path)}` : ""}`),
  getAnalytics: (id) => request(`/api/repositories/${id}/analytics`),
  getAnalytics: (id) => request(`/api/repositories/${id}/analytics`),
  getFile: (id) => request(`/api/files/${id}`),
  search: ({ query, repo_id, language, limit = 10 }) =>
    request("/api/search", {
      method: "POST",
      body: JSON.stringify({
        query,
        limit,
        ...(repo_id ? { repo_id: Number(repo_id) } : {}),
        ...(language ? { language } : {}),
      }),
    }),
};
