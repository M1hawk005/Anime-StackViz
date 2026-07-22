import { useEffect, useState } from "react";
import { api, Franchise, HiddenGem, SequelPrediction } from "./api";

type Tab = "sequels" | "gems" | "buzz";

const TABS: { id: Tab; label: string; blurb: string }[] = [
  { id: "sequels", label: "Sequel odds", blurb: "Season-one titles most likely to continue." },
  { id: "gems", label: "Hidden gems", blurb: "Highly rated relative to their audience size." },
  { id: "buzz", label: "Buzz", blurb: "Franchises by community discussion volume." },
];

function useProduct<T>(loader: () => Promise<T[]>, deps: unknown[]) {
  const [data, setData] = useState<T[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    loader()
      .then((rows) => active && setData(rows))
      .catch((err: Error) => active && setError(err.message))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading };
}

const pct = (value: number) => `${Math.round(value * 100)}%`;
const num = (value: number | null) => (value == null ? "—" : value.toLocaleString());

function SequelsView() {
  const { data, error, loading } = useProduct<SequelPrediction>(() => api.sequels(50), []);
  return (
    <ProductTable
      loading={loading}
      error={error}
      empty={data.length === 0}
      head={["Title", "Year", "Score", "Sequel odds", "Actual"]}
      rows={data.map((r) => [
        r.title_romaji ?? "—",
        num(r.season_year),
        num(r.average_score),
        <strong key="p">{pct(r.sequel_probability)}</strong>,
        r.got_sequel ? "got a sequel" : "no sequel",
      ])}
    />
  );
}

function GemsView() {
  const { data, error, loading } = useProduct<HiddenGem>(() => api.gems(50), []);
  return (
    <ProductTable
      loading={loading}
      error={error}
      empty={data.length === 0}
      head={["Title", "Year", "Quality", "Popularity", "Gem score"]}
      rows={data.map((r) => [
        r.title_romaji ?? r.title_english ?? "—",
        num(r.season_year),
        r.quality == null ? "—" : r.quality.toFixed(0),
        num(r.popularity),
        <strong key="g">{r.gem_score == null ? "—" : pct(r.gem_score)}</strong>,
      ])}
    />
  );
}

function BuzzView() {
  const { data, error, loading } = useProduct<Franchise>(() => api.buzz(50), []);
  return (
    <ProductTable
      loading={loading}
      error={error}
      empty={data.length === 0}
      emptyNote="No Stack Exchange buzz data in this deployment."
      head={["Franchise", "Total questions", "Peak month", "Active months"]}
      rows={data.map((r) => [r.tag, num(r.total_questions), r.peak_period, num(r.active_months)])}
    />
  );
}

function ProductTable(props: {
  loading: boolean;
  error: string | null;
  empty: boolean;
  emptyNote?: string;
  head: string[];
  rows: React.ReactNode[][];
}) {
  if (props.loading) return <p className="state">Loading…</p>;
  if (props.error)
    return (
      <p className="state error">
        Could not reach the API ({props.error}). Is it running on the configured host?
      </p>
    );
  if (props.empty) return <p className="state">{props.emptyNote ?? "No results."}</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {props.head.map((h) => (
              <th key={h}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {props.rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function App() {
  const [tab, setTab] = useState<Tab>("sequels");
  const active = TABS.find((t) => t.id === tab)!;

  return (
    <div className="app">
      <header>
        <h1>Anime StackViz</h1>
        <p className="tagline">An anime intelligence platform — sequels, hidden gems, and buzz.</p>
      </header>

      <nav className="tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            className={t.id === tab ? "tab active" : "tab"}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <p className="blurb">{active.blurb}</p>

      {tab === "sequels" && <SequelsView />}
      {tab === "gems" && <GemsView />}
      {tab === "buzz" && <BuzzView />}

      <footer>
        Data: AniList · MyAnimeList · Anime &amp; Manga Stack Exchange. Predictions are model
        estimates, not forecasts.
      </footer>
    </div>
  );
}
