"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";

export default function HomePage() {
  const [repos, setRepos] = useState(null);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setRepos(await api.listRepositories());
    } catch (e) {
      setError(e.message);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // keep refreshing while any import is running
  const importing = repos && repos.some((r) => ["pending", "cloning", "indexing"].includes(r.status));
  useEffect(() => {
    if (!importing) return;
    const t = setInterval(load, 2000);
    return () => clearInterval(t);
  }, [importing, load]);

  async function onSubmit(e) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      await api.importRepository(url.trim());
      setUrl("");
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Repositories</h1>
      <form className="panel" onSubmit={onSubmit}>
        <div className="row">
          <input
            type="text"
            placeholder="https://github.com/owner/repo"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            aria-label="GitHub repository URL"
          />
          <button type="submit" disabled={busy || !url.trim()}>
            {busy ? "Importing…" : "Import"}
          </button>
        </div>
        <div className="muted" style={{ marginTop: 6, fontSize: 13 }}>
          Public GitHub repositories only.
        </div>
        {error && <div className="error">{error}</div>}
      </form>

      <h2>Imported</h2>
      {repos === null ? (
        <p className="muted">Loading…</p>
      ) : repos.length === 0 ? (
        <p className="muted">No repositories yet. Import one above.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Name</th><th>Language</th><th>Status</th><th>Last synced</th></tr>
          </thead>
          <tbody>
            {repos.map((r) => (
              <tr key={r.repo_id}>
                <td><Link href={`/repositories/${r.repo_id}`}>{r.name}</Link></td>
                <td>{r.primary_language || "—"}</td>
                <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                <td className="muted">{r.last_synced_at ? new Date(r.last_synced_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
