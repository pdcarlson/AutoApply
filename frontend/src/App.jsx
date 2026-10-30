import Sidebar from "./components/Sidebar.jsx";

// App shell: sidebar + main area. Screens get added next.
export default function App() {
  return (
    <div className="app">
      <Sidebar current="inbox" />
      <main className="main">
        <h1>Auto Apply</h1>
        <p className="muted">Screens coming next.</p>
      </main>
    </div>
  );
}
