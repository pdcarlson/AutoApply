import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import SignIn from "./pages/SignIn.jsx";
import Onboarding from "./pages/Onboarding.jsx";
import Inbox from "./pages/Inbox.jsx";
import NeedsYou from "./pages/NeedsYou.jsx";
import Applications from "./pages/Applications.jsx";
import AnswerBank from "./pages/AnswerBank.jsx";

// Very small hash router: #/inbox, #/needs-you/3, etc.
// Good enough for six screens; we can switch to react-router later if we need it.
function useHashRoute() {
  const read = () => window.location.hash.replace(/^#\/?/, "") || "signin";
  const [route, setRoute] = useState(read());
  useEffect(() => {
    const onChange = () => setRoute(read());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route.split("/");
}

export default function App() {
  const [page, param] = useHashRoute();

  // Screens without the sidebar
  if (page === "signin") return <SignIn />;
  if (page === "setup") return <Onboarding />;

  let content;
  if (page === "inbox") content = <Inbox />;
  else if (page === "needs-you") content = <NeedsYou id={Number(param)} />;
  else if (page === "applications") content = <Applications />;
  else if (page === "answers") content = <AnswerBank />;
  else content = <p>Page not found.</p>;

  return (
    <div className="app">
      <Sidebar current={page === "needs-you" ? "inbox" : page} />
      <main className="main">{content}</main>
    </div>
  );
}
