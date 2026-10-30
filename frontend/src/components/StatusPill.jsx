const labels = {
  queued: "Queued",
  in_progress: "In progress",
  needs_you: "Needs you",
  submitted: "Submitted",
  failed: "Failed",
  skipped: "Skipped",
};

export default function StatusPill({ status }) {
  return <span className={`pill pill-${status}`}>{labels[status] || status}</span>;
}
