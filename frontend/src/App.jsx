import { useEffect, useState } from "react";

function useApi(url) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => active && setData(json))
      .catch((err) => active && setError(err.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [url]);

  return { data, error, loading };
}

function Card({ title, state }) {
  return (
    <div className="card">
      <h2>{title}</h2>
      {state.loading && <p className="muted">Loading…</p>}
      {state.error && <p className="error">Error: {state.error}</p>}
      {state.data && <pre>{JSON.stringify(state.data, null, 2)}</pre>}
    </div>
  );
}

export default function App() {
  const hello = useApi("/api/hello");
  const health = useApi("/api/health");

  return (
    <main>
      <h1>Full-Stack Template</h1>
      <p className="muted">React + Vite · Express · Sequelize</p>
      <Card title="/api/hello" state={hello} />
      <Card title="/api/health" state={health} />
    </main>
  );
}
