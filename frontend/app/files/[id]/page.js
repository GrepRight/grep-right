"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../../../lib/api";

export default function FilePage() {
  const { id } = useParams();
  const [file, setFile] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getFile(id).then(setFile).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!file) return <p className="muted">Loading…</p>;

  return (
    <>
      <p><Link href={`/repositories/${file.repo_id}`}>← {file.repo_name}</Link></p>
      <h1 className="mono">{file.file_path}</h1>
      <div className="muted">
        {file.language} · {file.line_count} lines · {file.size_bytes} bytes
      </div>

      <h2>Classes ({file.classes.length})</h2>
      {file.classes.length === 0 ? <p className="muted">None</p> : (
        <table>
          <tbody>
            {file.classes.map((c) => (
              <tr key={c.class_id}>
                <td className="mono">{c.name}</td>
                <td className="muted">lines {c.start_line}–{c.end_line}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Functions ({file.functions.length})</h2>
      {file.functions.length === 0 ? <p className="muted">None</p> : (
        <table>
          <tbody>
            {file.functions.map((f) => (
              <tr key={f.func_id}>
                <td className="mono">{f.signature || f.name}</td>
                <td className="muted">lines {f.start_line}–{f.end_line}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Code chunks ({file.chunks.length})</h2>
      {file.chunks.length === 0 && <p className="muted">This file type is recorded but not chunked.</p>}
      {file.chunks.map((c) => (
        <div key={c.chunk_id}>
          <div className="chunk-head">
            <span className="badge">{c.chunk_type}</span>
            <span className="muted">lines {c.start_line}–{c.end_line}</span>
          </div>
          <pre className="code">{c.content}</pre>
        </div>
      ))}
    </>
  );
}
