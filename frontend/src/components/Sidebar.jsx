import { useEffect, useState } from "react";
import { api } from "../api.js";

const links = [
  { key: "inbox", label: "Inbox" },
  { key: "applications", label: "Applications" },
  { key: "answers", label: "Answer bank" },
];

export default function Sidebar({ current }) {
  const [apiUp, setApiUp] = useState(null);

  useEffect(() => {
    api.health().then(() => setApiUp(true)).catch(() => setApiUp(false));
  }, []);

  return (
    <aside className="sidebar">
      <div className="logo"><span>AA</span> Auto Apply</div>
      <nav>
        {links.map((link) => (
          <a key={link.key} href={`#/${link.key}`} className={current === link.key ? "active" : ""}>
            {link.label}
          </a>
        ))}
        <a href="#/setup">Profile</a>
      </nav>
      <div className="sidebar-foot">
        {/* TODO(US1): show the signed-in Google account */}
        <div>Demo Student</div>
        <div className="muted small">
          API: {apiUp === null ? "checking..." : apiUp ? "connected" : "offline (sample data)"}
        </div>
        <a href="#/signin" className="small">Sign out</a>
      </div>
    </aside>
  );
}
