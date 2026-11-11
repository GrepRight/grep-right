"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { api } from "../../lib/api";

const LANGUAGES = ["python", "javascript", "typescript"];

function SearchInner() {
  const router = useRouter();
  const params = useSearchParams();
  const q = params.get("q") || "";
  const repo = params.get("repo") || "";
  const lang = params.get("lang") || "";

  const [text, setText] = useState(q);
  const [repos, setRepos] = useState([]);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listRepositories().then((r) => setRepos(r.filter((x) => x.status === "ready"))).catch(() => {});
  }, []);

  useEffect(() => {
    setText(q);
    if (!q) {
      setResults(null);
      setError("");
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    api.search({ query: q, repo_id: repo, language: lang })
      .then((r) => !cancelled && setResults(r))
      .catch((e) => {
        if (!cancelled) {
          setResults(null);
          setError(e.message);
        }
      })
      .finally(() => !cancelled && setLoading(false));
    return () => { cancelled = true; };
  }, [q, repo, lang]);

  function go(next) {
    const sp = new URLSearchParams();
    const v = { q: text.trim(), repo, lang, ...next };
    Object.entries(v).forEach(([k, val]) => val && sp.set(k, val));
    router.push(`/search?${sp.toString()}`);
  }

  return (
    <>
      <h1>Semantic search</h1>
      <form className="panel" onSubmit={(e) => { e.preventDefault(); if (text.trim()) go({}); }}>
        <div className="row">
          <input
            type="text"
            placeholder="Describe what the code does, e.g. “parse command line arguments”"
            value={text}
            maxLength={500}
            onChange={(e) => setText(e.target.value)}
            aria-label="Search query"
            autoFocus
          />
          <button type="submit" disabled={loading || !text.trim()}>{loading ? "Searching…" : "Search"}</button>
        </div>
        <div className="filters">
          <select value={repo} onChange={(e) => go({ repo: e.target.value })} aria-label="Repository">
            <option value="">All repositories</option>
            {repos.map((r) => <option key={r.repo_id} value={r.repo_id}>{r.name}</option>)}
          </select>
          <select value={lang} onChange={(e) => go({ lang: e.target.value })} aria-label="Language">
            <option value="">All languages</option>
            {LANGUAGES.map((l) => <option key={l} value={l}>{l}</option>)}
          </select>
        </div>
      </form>

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Searching…</p>}
      {!loading && results && results.length === 0 && (
        <p className="muted">No results. Try different wording or remove filters.</p>
      )}
      {results && results.map((h) => (
        <div className="result" key={h.chunk_id}>
          <div className="result-head">
            <span className="mono"><b>{h.name || "(module)"}</b></span>
            <span className="badge">{h.chunk_type}</span>
            <span className="badge">{h.language}</span>
            <span className="score">{(h.score * 100).toFixed(1)}% match</span>
          </div>
          <div className="muted" style={{ fontSize: 13 }}>
            {h.repo_name} ·{" "}
            <Link href={`/files/${h.file_id}?chunk=${h.chunk_id}`} className="mono">{h.file_path}</Link>
            {" "}· lines {h.start_line}–{h.end_line}
          </div>
          <pre className="code">{h.snippet}</pre>
        </div>
      ))}
    </>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="muted">Loading…</p>}>
      <SearchInner />
    </Suspense>
  );
}
