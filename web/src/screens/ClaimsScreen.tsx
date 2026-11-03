import { useState } from "react";
import type { Strings } from "../i18n";
import { Search, Send } from "../components/icons";

interface Props {
  s: Strings;
}

type ClaimResult = "official" | "notfound" | "cantverify";

/* Claim checking is manual/verbatim in this milestone: there is no backend source
   to search official notices against, so we always report "can't verify" and list
   the sources a real check would use. We never call something false ourselves. */
export function ClaimsScreen({ s }: Props) {
  const [text, setText] = useState("");
  const [result, setResult] = useState<ClaimResult | null>(null);

  const check = () => {
    if (!text.trim()) return;
    setResult("cantverify");
  };

  return (
    <div className="stack">
      <div className="card">
        <h2 className="card-title">{s.claimsTitle}</h2>
        <div className="field">
          <label className="label" htmlFor="claim-text">{s.claimsPaste}</label>
          <textarea
            id="claim-text"
            className="input"
            rows={5}
            value={text}
            onChange={(e) => setText(e.target.value)}
            style={{ minHeight: 96, resize: "vertical" }}
          />
        </div>
        <div className="btn-row" style={{ marginTop: 12 }}>
          <button type="button" className="btn btn-primary btn-block" disabled={!text.trim()} onClick={check}>
            <Send size={20} /> {s.claimsCheck}
          </button>
        </div>
      </div>

      {result === null && (
        <div className="empty card">
          <div className="empty-icon"><Search size={48} /></div>
          <p>{s.claimsEmpty}</p>
        </div>
      )}

      {result === "official" && (
        <div className="notice notice-info"><Search size={18} /><span>{s.claimsOfficial}</span></div>
      )}
      {result === "notfound" && (
        <div className="notice notice-warn"><Search size={18} /><span>{s.claimsNotFound}</span></div>
      )}
      {result === "cantverify" && (
        <div className="card">
          <div className="notice notice-slate"><Search size={18} /><span>{s.claimsCantVerify}</span></div>
          <p className="kicker" style={{ marginTop: 12 }}>{s.claimsSources}</p>
          <p className="disclaimer">NAFDAC Greenbook · NAPAMS portal · NAFDAC public alerts</p>
        </div>
      )}
    </div>
  );
}
