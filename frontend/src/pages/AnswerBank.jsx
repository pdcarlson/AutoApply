import { useState } from "react";
import { api } from "../api.js";
import { mockAnswers } from "../mockData.js";
import useApiData from "../useApiData.js";

// Screen 6: saved answers (US9, US10) and the confidence threshold (US7).
export default function AnswerBank() {
  const { data: answers, setData: setAnswers, reload } = useApiData(api.listAnswers, mockAnswers);
  const [editingId, setEditingId] = useState(null);
  const [draft, setDraft] = useState("");
  const [newQ, setNewQ] = useState("");
  const [newA, setNewA] = useState("");
  const [search, setSearch] = useState("");

  async function saveEdit(item) {
    try {
      await api.updateAnswer(item.id, item.question, draft);
      await reload();
    } catch {
      // offline: just update what's on screen
      setAnswers(answers.map((a) => (a.id === item.id ? { ...a, answer: draft } : a)));
    }
    setEditingId(null);
  }

  async function addAnswer(event) {
    event.preventDefault();
    if (!newQ.trim() || !newA.trim()) return;
    try {
      await api.addAnswer(newQ, newA);
      await reload();
    } catch {
      setAnswers([...answers, { id: Date.now(), question: newQ, answer: newA, times_used: 0 }]);
    }
    setNewQ("");
    setNewA("");
  }

  async function remove(item) {
    try {
      await api.deleteAnswer(item.id);
    } catch {
      // offline
    }
    setAnswers(answers.filter((a) => a.id !== item.id));
  }

  const shown = answers.filter((a) => a.question.toLowerCase().includes(search.toLowerCase()));

  return (
    <>
      <h1>Answer bank</h1>
      <p className="muted">Answers we reuse on every form.</p>
      <input className="search" placeholder="Search questions" value={search} onChange={(e) => setSearch(e.target.value)} />

      <div className="card flush">
        <table>
          <thead>
            <tr><th>Question</th><th>Your answer</th><th>Used</th><th></th></tr>
          </thead>
          <tbody>
            {shown.map((item) => (
              <tr key={item.id}>
                <td className="q-col">{item.question}</td>
                <td>
                  {editingId === item.id
                    ? <input value={draft} onChange={(e) => setDraft(e.target.value)} autoFocus />
                    : item.answer}
                </td>
                <td>{item.times_used}x</td>
                <td className="right nowrap">
                  {editingId === item.id ? (
                    <button className="link-btn" onClick={() => saveEdit(item)}>Save</button>
                  ) : (
                    <button className="link-btn" onClick={() => { setEditingId(item.id); setDraft(item.answer); }}>Edit</button>
                  )}
                  <button className="link-btn" onClick={() => remove(item)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <form className="row add-row" onSubmit={addAnswer}>
        <input className="grow" placeholder="Question" value={newQ} onChange={(e) => setNewQ(e.target.value)} />
        <input className="grow" placeholder="Answer" value={newA} onChange={(e) => setNewA(e.target.value)} />
        <button className="btn">+ Add answer</button>
      </form>

      <div className="card threshold">
        <div className="label">Confidence threshold</div>
        {/* TODO(US7): load and save this with PUT /api/me/settings */}
        <div className="row center"><div className="bar grow"><i style={{ width: "90%" }} /></div><b>90%</b></div>
        <p className="small muted">Below this we ask you instead of filling.</p>
      </div>
    </>
  );
}
