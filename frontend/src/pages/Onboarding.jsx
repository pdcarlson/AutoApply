import { useState } from "react";
import { api } from "../api.js";
import { go } from "../nav.js";
import { mockProfile } from "../mockData.js";
import useApiData from "../useApiData.js";

// Screen 2: check the profile pulled from the resume (US2, US3).
export default function Onboarding() {
  const { data: profile, setData: setProfile } = useApiData(api.getProfile, mockProfile);
  const [message, setMessage] = useState("");

  const flagged = (field) => (profile.flagged_fields || []).includes(field);
  const update = (field, value) => setProfile({ ...profile, [field]: value });

  function updateJob(index, field, value) {
    const experience = profile.experience.map((job, i) =>
      i === index ? { ...job, [field]: value } : job
    );
    setProfile({ ...profile, experience });
  }

  async function onResume(event) {
    const file = event.target.files[0];
    if (!file) return;
    try {
      const updated = await api.uploadResume(file);
      setProfile({ ...profile, resume_path: updated.resume_path });
      setMessage(`Uploaded ${file.name}. Parsing isn't built yet, so fill the fields in below.`);
    } catch (err) {
      setMessage(err.message);
    }
  }

  async function onContinue() {
    try {
      await api.saveProfile({ ...profile, confirmed: true });
      go("inbox");
    } catch (err) {
      setMessage(`Couldn't save: ${err.message}`);
    }
  }

  return (
    <div className="setup">
      <p className="small muted">Step 2 of 3 · Resume → <b>Check your profile</b> → A few questions</p>
      <h1>Check your profile</h1>
      <p className="muted">Fix anything that looks off. Dashed fields were a guess.</p>
      {message && <p className="notice">{message}</p>}

      <div className="row">
        <div className="card grow">
          <div className="row">
            <Field label="First name" value={profile.first_name} onChange={(v) => update("first_name", v)} />
            <Field label="Last name" value={profile.last_name} onChange={(v) => update("last_name", v)} />
          </div>
          <div className="row">
            <Field label="Email" value={profile.email} onChange={(v) => update("email", v)} />
            <Field label="Phone" value={profile.phone} guess={flagged("phone")} onChange={(v) => update("phone", v)} />
          </div>
          <div className="row">
            <Field label="School" value={profile.school} onChange={(v) => update("school", v)} />
            <Field label="Degree" value={profile.degree} onChange={(v) => update("degree", v)} />
            <Field label="Graduation" value={profile.grad_date} onChange={(v) => update("grad_date", v)} />
          </div>

          <div className="label">Experience</div>
          {profile.experience.map((job, i) => (
            <div className="row" key={i}>
              <Field value={job.title} guess={flagged(`experience.${i}`)} onChange={(v) => updateJob(i, "title", v)} />
              <Field value={job.company} guess={flagged(`experience.${i}`)} onChange={(v) => updateJob(i, "company", v)} />
              <Field value={job.dates} guess={flagged(`experience.${i}`)} onChange={(v) => updateJob(i, "dates", v)} />
            </div>
          ))}
          <button className="link-btn" onClick={() =>
            setProfile({ ...profile, experience: [...profile.experience, { title: "", company: "", dates: "" }] })}>
            + add another
          </button>

          <div className="label">Skills (comma separated)</div>
          <input
            value={profile.skills.join(", ")}
            onChange={(e) => update("skills", e.target.value.split(",").map((s) => s.trim()).filter(Boolean))}
          />
        </div>

        <div className="side-col">
          <div className="card">
            <div className="label">Resume</div>
            <input type="file" accept=".pdf,.docx" onChange={onResume} />
            <p className="small muted">PDF or DOCX, under 5 MB.</p>
          </div>
          <div className="card">
            <div className="label">What happens next</div>
            <p className="small">
              We only fill forms with facts on this page or answers you give us. If a question
              isn't covered, we ask you first.
            </p>
          </div>
        </div>
      </div>

      {/* TODO(US4): step 3, the onboarding questions, saved to the answer bank */}
      <div className="actions">
        <button className="btn" onClick={() => go("signin")}>Back</button>
        <button className="btn btn-dark" onClick={onContinue}>Looks right, continue</button>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, guess = false }) {
  return (
    <label className="field">
      {label && <span className="label">{label}{guess ? " ?" : ""}</span>}
      <input className={guess ? "guess" : ""} value={value || ""} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
