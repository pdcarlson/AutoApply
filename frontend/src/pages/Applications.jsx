import { useState } from "react";
import { api } from "../api.js";
import StatusPill from "../components/StatusPill.jsx";
import { mockApplications } from "../mockData.js";
import useApiData from "../useApiData.js";

// Screen 5: the tracker (US11, US12).
export default function Applications() {
  const { data: apps } = useApiData(api.listApplications, mockApplications);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [source, setSource] = useState("all");

  const shown = apps.filter((a) =>
    (status === "all" || a.status === status) &&
    (source === "all" || a.ats === source) &&
    `${a.company} ${a.role}`.toLowerCase().includes(search.toLowerCase())
  );

  const count = (s) => apps.filter((a) => a.status === s).length;

  function exportCsv() {
    const header = "Company,Role,Source,Status,Submitted";
    const rows = shown.map((a) =>
      [a.company, a.role, a.ats, a.status, a.submitted_at || ""].map((v) => `"${v || ""}"`).join(",")
    );
    const blob = new Blob([[header, ...rows].join("\n")], { type: "text/csv" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "applications.csv";
    link.click();
  }

  return (
    <>
      <h1>Applications</h1>
      <p className="muted">
        {count("submitted")} submitted · {count("needs_you")} waiting on you · {count("failed")} failed
      </p>

      <div className="row filters">
        <input placeholder="Search company or role" value={search} onChange={(e) => setSearch(e.target.value)} />
        <select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="all">Status: All</option>
          <option value="submitted">Submitted</option>
          <option value="needs_you">Needs you</option>
          <option value="in_progress">In progress</option>
          <option value="failed">Failed</option>
        </select>
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="all">Source: All</option>
          <option value="greenhouse">Greenhouse</option>
          <option value="lever">Lever</option>
          <option value="ashby">Ashby</option>
        </select>
        <button className="btn" onClick={exportCsv}>Export CSV</button>
      </div>

      <div className="card flush">
        <table>
          <thead>
            <tr><th>Company</th><th>Role</th><th>Source</th><th>Status</th><th>Submitted</th><th>Record</th></tr>
          </thead>
          <tbody>
            {shown.map((a) => (
              <tr key={a.id}>
                <td>{a.company}</td>
                <td>{a.role}</td>
                <td className="cap">{a.ats}</td>
                <td><StatusPill status={a.status} /></td>
                <td>{a.submitted_at ? a.submitted_at.slice(0, 10) : "—"}</td>
                {/* TODO(US12): link to the real screenshot file */}
                <td>{a.status === "submitted" ? <a href="#/applications">Screenshot</a> : <span className="small muted">{a.status === "failed" ? a.reason : ""}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small muted">Showing {shown.length} of {apps.length}</p>
    </>
  );
}
