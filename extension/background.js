// Talks to the local AutoApply server for the page. Requests go from here, not from the page's
// script, because only the extension itself is allowed to reach http://localhost:8080.
const API = 'http://localhost:8080/api';

async function getJson(path, options) {
  let response;
  try {
    response = await fetch(API + path, options);
  } catch {
    return { ok: false, message: "AutoApply isn't running. Start it, then try again." };
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    return {
      ok: false,
      code: body.code,
      message: body.message || "AutoApply couldn't help with this page.",
    };
  }
  return { ok: true, body };
}

// The resume goes to the page as base64 text, since messages can't carry a file.
async function getResume(path) {
  let response;
  try {
    response = await fetch('http://localhost:8080' + path);
  } catch {
    return { ok: false, message: "AutoApply isn't running. Start it, then try again." };
  }
  if (!response.ok) return { ok: false, message: "Couldn't get your resume from AutoApply." };
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = '';
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return { ok: true, base64: btoa(binary), type: response.headers.get('content-type') || '' };
}

chrome.runtime.onMessage.addListener((message, _sender, reply) => {
  if (message.type === 'plan') {
    getJson(`/extension/plan?url=${encodeURIComponent(message.url)}`).then(reply);
  } else if (message.type === 'resume') {
    getResume(message.url).then(reply);
  } else if (message.type === 'submitted') {
    getJson(`/extension/jobs/${encodeURIComponent(message.jobId)}/submitted`, {
      method: 'POST',
    }).then(reply);
  } else {
    return false;
  }
  return true; // the reply comes later
});
