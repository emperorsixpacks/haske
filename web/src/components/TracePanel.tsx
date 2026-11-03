import { useState } from "react";
import type { Strings } from "../i18n";
import type { TraceEvent } from "../types";
import { ChevronDown } from "./icons";

export function TracePanel({ trace, summary, s }: { trace: TraceEvent[]; summary: string | null; s: Strings }) {
  const [open, setOpen] = useState(false);
  if (!trace.length) return null;

  return (
    <details className="card accordion" open={open} onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary>
        <span>{s.traceTitle}</span>
        <span className="step-note">{summary}</span>
        <ChevronDown className="chev" size={18} />
      </summary>
      <div className="rows" style={{ marginTop: 8 }}>
        {trace.map((e, i) => (
          <div key={i} className="row">
            <div className="row-main">
              <div className="row-title">{e.tool}</div>
              <div className="row-sub">{e.summary}</div>
            </div>
            <div className="row-value step-note" style={{ fontSize: 12, textAlign: "right" }}>
              {e.effort} · {e.latency_ms}ms · {e.tokens}t
            </div>
          </div>
        ))}
      </div>
    </details>
  );
}
