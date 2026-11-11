"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "../../../../lib/api";

function Table({ title, cols, rows, fileLink }) {
  return (
    <>
      <h2>{title}</h2>
      <div className="panel">
        {rows.length === 0 ? <span className="muted">No data.</span> : (
          <table>
            <thead><tr>{cols.map(([, label]) => <th key={label}>{label}</th>)}</tr></thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i}>
                  {cols.map(([key]) => (
                    <td key={key}>
                      {key === "file_path" && fileLink && row.file_id
                        ? <Link href={`/files/${row.file_id}`}>{row.file_path}</Link>
                        : String(row[key] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

export default function AnalyticsPage() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getAnalytics(id).then(setData).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;
  const o = data.overview;

  return (
    <>
      <p><Link href={`/repositories/${id}`}>← Repository</Link></p>
      <h1>Analytics</h1>
      <div className="stats">
        {[["files", o.files], ["functions", o.functions], ["classes", o.classes], ["chunks", o.chunks],
          ["commits", o.commits], ["additions", o.additions], ["deletions", o.deletions]].map(([l, n]) => (
          <div className="stat" key={l}><b>{n}</b><span>{l}</span></div>
        ))}
      </div>
      <div className="muted">
        History: {o.first_commit ? o.first_commit.slice(0, 10) : "—"} → {o.last_commit ? o.last_commit.slice(0, 10) : "—"}
      </div>
      <Table title="Languages" rows={data.languages}
        cols={[["language", "Language"], ["file_count", "Files"], ["total_lines", "Lines"], ["pct_lines", "% of lines"]]} />
      <Table title="Largest files" fileLink rows={data.largest_files}
        cols={[["file_path", "File"], ["language", "Language"], ["line_count", "Lines"], ["function_count", "Functions"], ["class_count", "Classes"]]} />
      <Table title="Files with most functions" fileLink rows={data.files_by_functions}
        cols={[["file_path", "File"], ["function_count", "Functions"], ["class_count", "Classes"]]} />
      <Table title="Most changed files" fileLink rows={data.hot_files}
        cols={[["file_path", "File"], ["change_count", "Commits"], ["total_additions", "+"], ["total_deletions", "−"]]} />
      <Table title="Commit activity" rows={data.commit_activity}
        cols={[["commit_date", "Date"], ["commit_count", "Commits"], ["running_total", "Cumulative"]]} />
    </>
  );
}
