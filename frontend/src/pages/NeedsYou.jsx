import { useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { mockApplications } from "../mockData.js";
import useApiData from "../useApiData.js";

// Screen 4: one application waiting on the student (US7, US8, US9, US13).
export default function NeedsYou({ id }) {
  const { data: apps } = useApiData(api.listApplications, mockApplications);
  const app = apps.find((a) => a.id === id);
  const [answer, setAnswer] = useState("");
  const [saveToBank, setSaveToBank] = useState(true);
  const [message, setMessage] = useState("");

  if (!app) return <p>Loading...</p>;

  async function onSkip() {
    try {
      await api.skip(app.id);
    } catch {
      // sample data has no real id on the server; just go back
    }
    go("inbox");
  }

  function onSubmit() {
    // TODO(US7): send the answer back so the agent can finish the form.
    // TODO(US9): if saveToBank, POST it to /answers too.
    setMessage("Submitting from here isn't built yet. The answer was not sent.");
  }

  return (
    <>
      <a href="#/inbox" className="small">← Back to Inbox</a>
      <h1>{app.role || "Application"}, {app.company}</h1>
      <p className="muted">{app.reason}</p>

      <div className="row">
        <div className="card grow">
          <div className="label">Question</div>
          {/* TODO(US13): show the AI draft and the profile facts it used */}
          <p><b>The agent's question will show here.</b></p>
          <textarea rows="6" value={answer} onChange={(e) => setAnswer(e.target.value)}
            placeholder="Write your answer" />
          <label className="check">
            <input type="checkbox" checked={saveToBank} onChange={(e) => setSaveToBank(e.target.checked)} />
            Save to answer bank
          </label>
          {message && <p className="notice">{message}</p>}
        </div>

        <div className="side-col">
          <div className="card">
            <div className="label">Form preview</div>
            {/* TODO(US6): show app.screenshot_path once the API serves screenshots */}
            <div className="placeholder-img small-img">form screenshot</div>
          </div>
          <div className="card small">
            <b>Never filled by the agent:</b> passwords, SSNs and CAPTCHAs. We open the form for you instead.
          </div>
        </div>
      </div>

      <div className="actions">
        <button className="btn" onClick={onSkip}>Skip this job</button>
        <button className="btn btn-dark" onClick={onSubmit}>Submit application</button>
      </div>
    </>
  );
}
