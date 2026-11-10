"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { api } from "../../../lib/api";

const BUSY = ["pending", "cloning", "indexing"];

/** Build a nested folder tree from flat file paths. */
function buildTree(files) {
  const root = { dirs: {}, files: [] };
  for (const f of files) {
    const parts = f.file_path.split("/");
    let node = root;
    for (const part of parts.slice(0, -1)) {
      node.dirs[part] = node.dirs[part] || { dirs: {}, files: [] };
      node = node.dirs[part];
    }
    node.files.push({ ...f, name: parts[parts.length - 1] });
  }
  return root;
}

function Dir({ name, node, depth }) {
  const [open, setOpen] = useState(depth < 1);
  return (
    <li>
      <span className="dir" onClick={() => setOpen(!open)}>{open ? "▾" : "▸"} {name}/</span>
      {open && <Branch node={node} depth={depth + 1} />}
    </li>
  );
}

function Branch({ node, depth }) {
  return (
    <ul>
      {Object.keys(node.dirs).sort().map((d) => (
        <Dir key={d} name={d} node={node.dirs[d]} depth={depth} />
      ))}
      {node.files.map((f) => (
        <li key={f.file_id}>
          <Link href={`/files/${f.file_id}`}>{f.name}</Link>
          <span className="lang">{f.language} · {f.line_count} lines</span>
        </li>
      ))}
    </ul>
  );
}

export default function RepositoryPage() {
  const { id } = useParams();
  const router = useRouter();
  const [repo, setRepo] = useState(null);
  const [status, setStatus] = useState(null);
  const [files, setFiles] = useState([]);
  const [error, setError] = useState("");

  // poll status until the import finishes, then load the full overview
  useEffect(() => {
    let stop = false;
    let timer;
    async function tick() {
      try {
        const s = await api.getStatus(id);
        if (stop) return;
        setStatus(s);
        if (BUSY.includes(s.status)) {
          timer = setTimeout(tick, 1500);
        } else {
          const [r, f] = await Promise.all([api.getRepository(id), s.status === "ready" ? api.listFiles(id) : []]);
          if (!stop) { setRepo(r); setFiles(f); }
        }
      } catch (e) {
        if (!stop) setError(e.message);
      }
    }
    tick();
    return () => { stop = true; clearTimeout(timer); };
  }, [id]);

  const tree = useMemo(() => buildTree(files), [files]);

  async function onDelete() {
    if (!confirm("Delete this repository and all its indexed data?")) return;
    try {
      await api.deleteRepository(id);
      router.push("/");
    } catch (e) {
      setError(e.message);
    }
  }

  if (error && !status) return <p className="error">{error}</p>;
  if (!status) return <p className="muted">Loading…</p>;

  const busy = BUSY.includes(status.status);
  const pct = status.total ? Math.round((status.processed / status.total) * 100) : 0;

  return (
    <>
      <p><Link href="/">← Repositories</Link></p>
      <h1>
        {repo ? repo.name : `Repository ${id}`}{" "}
        <span className={`badge ${status.status}`}>{status.status}</span>
      </h1>
      {error && <div className="error">{error}</div>}

      {busy && (
        <div className="panel">
          <div>{status.stage === "cloning" ? "Cloning repository…" : "Indexing files…"}</div>
          {status.total > 0 && (
            <>
              <div className="progress"><div style={{ width: `${pct}%` }} /></div>
              <div className="muted">{status.processed} / {status.total} files</div>
            </>
          )}
        </div>
      )}

      {status.status === "failed" && <div className="panel error">Import failed: {status.error}</div>}

      {repo && status.status === "ready" && (
        <>
          <div className="muted mono">{repo.git_url}</div>
          <div className="stats">
            {[
              ["files", repo.counts.files],
              ["functions", repo.counts.functions],
              ["classes", repo.counts.classes],
              ["chunks", repo.counts.chunks],
              ["commits", repo.counts.commits],
            ].map(([label, n]) => (
              <div className="stat" key={label}><b>{n}</b><span>{label}</span></div>
            ))}
          </div>
          <div className="muted">
            Primary language: {repo.primary_language || "—"} · Branch: {repo.default_branch || "—"}
          </div>

          <h2>Files</h2>
          <div className="panel tree"><Branch node={tree} depth={0} /></div>
        </>
      )}

      {!busy && (
        <p style={{ marginTop: 24 }}>
          <button className="danger" onClick={onDelete}>Delete repository</button>
        </p>
      )}
    </>
  );
}
