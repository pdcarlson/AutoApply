import { useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { mockApplications } from "../mockData.js";
import useApiData from "../useApiData.js";

// Screen 3: paste a link, see what needs you (US5, US7, US8, US16).
export default function Inbox() {
  const { data: apps, usingSample, reload } = useApiData(api.listApplications, mockApplications);
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const needsYou = apps.filter((a) => a.status === "needs_you");
  const running = apps.filter((a) => a.status === "queued" || a.status === "in_progress");

  async function onApply(event) {
    event.preventDefault();
    if (!url.trim()) return;
    setBusy(true);
    setError("");
    try {
      await api.applyFromLink(url);
      setUrl("");
      await reload();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Inbox</h1>
      {/* TODO(US16): show "4 of 25 applications used today" from the API */}
      <p className="muted">Paste a Greenhouse, Lever or Ashby job link to apply.</p>

      <form className="row apply-row" onSubmit={onApply}>
        <input
          className="grow"
          placeholder="https://boards.greenhouse.io/company/jobs/123"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button className="btn btn-dark" disabled={busy}>{busy ? "Adding..." : "Apply"}</button>
      </form>
      {error && <p className="error">{error}</p>}
      {usingSample && <p className="small muted">Showing sample data until the API has applications.</p>}

      <h2>Needs you ({needsYou.length})</h2>
      <div className="card flush">
        <table>
          <thead>
            <tr><th>Job</th><th>What we need</th><th></th></tr>
          </thead>
          <tbody>
            {needsYou.length === 0 && (
              <tr><td colSpan="3" className="muted">Nothing waiting on you.</td></tr>
            )}
            {needsYou.map((a) => (
              <tr key={a.id}>
                <td><b>{a.role || "Untitled role"}</b><div className="small muted">{a.company} · <span className="cap">{a.ats}</span></div></td>
                <td>{a.reason}</td>
                <td className="right"><button className="btn" onClick={() => go(`needs-you/${a.id}`)}>Review</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>In progress</h2>
      <div className="card flush">
        <table>
          <tbody>
            {running.length === 0 && <tr><td className="muted">No applications running.</td></tr>}
            {running.map((a) => (
              <tr key={a.id}>
                <td><b>{a.role || a.url}</b><div className="small muted">{a.company} · <span className="cap">{a.ats}</span></div></td>
                <td className="muted">{a.status === "queued" ? "Waiting for the agent" : "Agent is filling the form"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
