// Small wrapper around fetch for our FastAPI backend.
// Every call returns parsed JSON or throws an Error with the API's message.

async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: options.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      if (data.detail) message = data.detail;
    } catch {
      // response wasn't JSON, keep the default message
    }
    throw new Error(message);
  }
  return res.status === 204 ? null : res.json();
}

export const api = {
  health: () => request("/health"),
  me: () => request("/me"),

  getProfile: () => request("/profile"),
  saveProfile: (profile) => request("/profile", { method: "PUT", body: JSON.stringify(profile) }),
  uploadResume: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/profile/resume", { method: "POST", body: form });
  },

  listApplications: () => request("/applications"),
  needsYou: () => request("/applications/needs-you"),
  applyFromLink: (url) => request("/applications", { method: "POST", body: JSON.stringify({ url }) }),
  skip: (id) => request(`/applications/${id}/skip`, { method: "POST" }),

  listAnswers: () => request("/answers"),
  addAnswer: (question, answer) =>
    request("/answers", { method: "POST", body: JSON.stringify({ question, answer }) }),
  updateAnswer: (id, question, answer) =>
    request(`/answers/${id}`, { method: "PUT", body: JSON.stringify({ question, answer }) }),
  deleteAnswer: (id) => request(`/answers/${id}`, { method: "DELETE" }),
};
