import { useState } from "react";
import type { Strings } from "../i18n";
import { Megaphone, Search } from "../components/icons";

interface Props {
  s: Strings;
  onCheckLast: () => void;
}

/* The alerts feed needs a backend source that does not exist yet (milestone 2).
   Until then we show an honest empty state and never invent alerts. */
export function AlertsScreen({ s, onCheckLast }: Props) {
  const [query, setQuery] = useState("");

  return (
    <div className="stack">
      <div className="search-wrap">
        <Search size={18} />
        <input className="search" value={query} onChange={(e) => setQuery(e.target.value)} placeholder={s.alertsSearch} aria-label={s.alertsSearch} />
      </div>

      <button type="button" className="btn btn-secondary btn-block" onClick={onCheckLast}>
        <Megaphone size={20} /> {s.alertsCheckLast}
      </button>

      <div className="empty card">
        <div className="empty-icon"><Megaphone size={48} /></div>
        <p>{s.alertsEmpty}</p>
      </div>
    </div>
  );
}
