import { useEffect, useState } from "react";
import type { Strings } from "../i18n";
import { Check, X, Refresh } from "../components/icons";

interface Props {
  s: Strings;
  thumbnail: string | null;
  onCancel: () => void;
}

interface Step {
  key: string;
  label: string;
  state: "running" | "done" | "failed" | "skipped";
  note?: string;
}

export function CheckingScreen({ s, thumbnail, onCancel }: Props) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = window.setInterval(() => setElapsed((e) => e + 1), 1000);
    return () => window.clearInterval(id);
  }, []);

  const slow = elapsed >= 12;

  const steps: Step[] = [
    { key: "read", label: s.stepReading, state: "running" },
    { key: "greenbook", label: s.stepGreenbook, state: "running" },
    { key: "napams", label: s.stepNapams, state: "running" },
    { key: "compare", label: s.stepCompare, state: "running" },
  ];

  return (
    <div className="stack fade-in">
      <div className="card">
        <div style={{ display: "flex", gap: 14, alignItems: "center", marginBottom: 12 }}>
          {thumbnail ? <img className="thumb" src={thumbnail} alt="" /> : null}
          <div>
            <h2 className="card-title" style={{ margin: 0 }} aria-live="polite">{s.checkingTitle}</h2>
            {slow && <p className="step-note">{s.timedOut}</p>}
          </div>
        </div>

        <div className="steps">
          {steps.map((st) => (
            <div key={st.key} className="step">
              <span className="step-icon">
                {st.state === "running" && <span className="spinner" />}
                {st.state === "done" && <Check size={20} style={{ color: "var(--match-fg)" }} />}
                {st.state === "failed" && <X size={20} style={{ color: "var(--notfound-fg)" }} />}
              </span>
              <span className="step-label">{st.label}</span>
              {st.note && <span className="step-note">{st.note}</span>}
            </div>
          ))}
        </div>

        <p className="disclaimer" style={{ marginTop: 12 }}>
          {slow ? s.timedOut : null}
        </p>
      </div>

      <button type="button" className="btn btn-secondary btn-block" onClick={onCancel}>
        <Refresh size={20} /> {s.cancel}
      </button>
    </div>
  );
}
