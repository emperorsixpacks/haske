import { useMemo, useState } from "react";
import type { Strings } from "../i18n";
import type { CapturedPhoto, CheckInput, CheckResponse, RegistryStatus, VerdictTone } from "../types";
import { verdictPresentation, buildReasons, type VerdictIcon } from "../lib/verdict";
import { buildShareText, shareOnWhatsApp, sourceNames } from "../lib/share";
import { sourceHome, REPORT_URL } from "../lib/links";
import { isUnusualBatch } from "../lib/batch";
import { tick } from "../lib/vibrate";
import {
  Alert,
  Bookmark,
  BookmarkFilled,
  Camera,
  Check,
  ChevronDown,
  Copy,
  Flag,
  Question,
  Whatsapp,
  X,
} from "../components/icons";

interface Props {
  s: Strings;
  result: CheckResponse | null;
  error: string | null;
  input: CheckInput;
  photos: CapturedPhoto[];
  isSaved: boolean;
  onSave: () => void;
  onCheckAnother: () => void;
  onEdit: (input: CheckInput) => void;
  registryStatus: RegistryStatus | null;
  onOpenHow: () => void;
}

const TONE_CLASS: Record<VerdictTone, string> = {
  match: "v-match",
  differ: "v-differ",
  notfound: "v-notfound",
  unreadable: "v-unreadable",
};

function toneIcon(icon: VerdictIcon, size = 22) {
  switch (icon) {
    case "check": return <Check size={size} />;
    case "alert": return <Alert size={size} />;
    case "x": return <X size={size} />;
    case "question": return <Question size={size} />;
  }
}

function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" });
}

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso || "";
  return d.toLocaleDateString("en-NG", { day: "2-digit", month: "short", year: "numeric" });
}

interface CmpRow {
  field: string;
  label: string;
  labelValue: string | null;
  regValue: string | null;
  sim: number | null;
}

export function ResultScreen(props: Props) {
  const { s, result, error, input, photos, isSaved, onSave, onCheckAnother, onEdit, registryStatus, onOpenHow } = props;
  const [copied, setCopied] = useState(false);
  const [openWhy, setOpenWhy] = useState(false);

  const batchPhoto = photos.find((p) => p.role === "batch");
  const batch = result?.extraction.batch ?? null;
  const batchConf = result?.extraction.confidence.batch ?? 0;
  const showBatch = !!batchPhoto && !!batch && batchConf >= 0.4;

  const presentation = result ? verdictPresentation(result) : { tone: "unreadable" as VerdictTone, icon: "question" as VerdictIcon, wordsKey: "resultOutage" as const, isOutage: true };

  const registryValue = (field: string): string | null => {
    for (const e of result?.verdict.evidence ?? []) {
      for (const c of e.fields_compared) {
        if (c.field === field && c.registry_value) return c.registry_value;
      }
    }
    return null;
  };

  const comparisons = useMemo<CmpRow[]>(() => {
    if (!result) return [];
    const rows: CmpRow[] = [];
    const seen = new Set<string>();
    for (const e of result.verdict.evidence) {
      for (const c of e.fields_compared) {
        if (seen.has(c.field)) continue;
        seen.add(c.field);
        const labels: Record<string, string> = { product_name: s.nameField, manufacturer: s.makerField, strength: s.strengthField };
        rows.push({
          field: c.field,
          label: labels[c.field] ?? c.field,
          labelValue: c.label_value,
          regValue: c.registry_value,
          sim: c.similarity,
        });
      }
    }
    // Number row, derived from the lookup outcome.
    const found = result.verdict.code !== "NOT_FOUND_IN_REGISTRY" && result.nrn.valid;
    rows.unshift({
      field: "nrn",
      label: s.numberField,
      labelValue: result.nrn.raw,
      regValue: found ? result.nrn.canonical : null,
      sim: found ? 1 : null,
    });
    return rows;
  }, [result, s.nameField, s.makerField, s.batchField, s.numberField]);

  const sources = result ? sourceNames(result) : [];

  const handleCopy = async () => {
    const nrn = result?.nrn.canonical || result?.nrn.raw;
    if (!nrn) return;
    try {
      await navigator.clipboard.writeText(nrn);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked */
    }
  };

  const handleShare = () => {
    if (!result) return;
    shareOnWhatsApp(buildShareText(result, sources, typeof location !== "undefined" ? location.origin : ""));
    tick();
  };

  // --- outage / error state (never a negative verdict) ---
  if (!result || error) {
    return (
      <div className="stack fade-in">
        <div className="verdict">
          <div className={`verdict-banner ${TONE_CLASS.unreadable}`}>
            <span className="verdict-icon">{toneIcon("question", 24)}</span>
            <div>
              <div className="verdict-words">{s.resultOutage}</div>
              <div className="verdict-sub">{s.outageBody}</div>
            </div>
          </div>
        </div>
        <p className="disclaimer">{s.reasonUnavailable}</p>
        <div className="btn-row">
          <button type="button" className="btn btn-primary btn-block" onClick={onCheckAnother}>
            <Camera size={20} /> {s.checkAnother}
          </button>
        </div>
      </div>
    );
  }

  const v = result.verdict;

  return (
    <div className="stack fade-in">
      {/* Verdict banner */}
      <div className="verdict">
        <div className={`verdict-banner ${TONE_CLASS[presentation.tone]}`}>
          <span className="verdict-icon">{toneIcon(presentation.icon, 24)}</span>
          <div>
            <div className="verdict-words" role="status">{s[presentation.wordsKey]}</div>
            <div className="verdict-sub">{v.title}</div>
          </div>
        </div>
      </div>

      {/* Product card */}
      <div className="card">
        <h2 className="kicker">{s.product}</h2>
        <div className="rows">
          <div className="row">
            <div className="row-main"><div className="row-title">{s.product}</div></div>
            <div className="row-value">{result.extraction.product_name || "—"}</div>
          </div>
          <div className="row">
            <div className="row-main"><div className="row-title">{s.regNumber}</div></div>
            <div className="row-value mono" style={{ display: "flex", alignItems: "center", gap: 8 }}>
              {result.nrn.canonical || "—"}
              <button type="button" className="icon-btn" onClick={handleCopy} aria-label={s.copy} style={{ color: "var(--teal)", width: 36, height: 36, minWidth: 36, minHeight: 36 }}>
                {copied ? <Check size={18} /> : <Copy size={18} />}
              </button>
            </div>
          </div>
          <div className="row">
            <div className="row-main"><div className="row-title">{s.manufacturer}</div></div>
            <div className="row-value">{registryValue("manufacturer") || result.extraction.manufacturer || "—"}</div>
          </div>
          <div className="row">
            <div className="row-main"><div className="row-title">{s.category}</div></div>
            <div className="row-value">{result.extraction.category_guess || "—"}</div>
          </div>
          <div className="row">
            <div className="row-main"><div className="row-title">{s.status}</div></div>
            <div className="row-value">{result.verdict.code === "EXPIRED_OR_INACTIVE" ? s.resultExpired : "—"}</div>
          </div>
          <div className="row">
            <div className="row-main"><div className="row-title">{s.expiry}</div></div>
            <div className="row-value mono">{result.extraction.expiry_date || "—"}</div>
          </div>
        </div>
        <p className="disclaimer" style={{ marginTop: 8 }}>{v.message}</p>
      </div>

      {/* What we checked */}
      <div className="card">
        <h2 className="card-title">{s.whatChecked}</h2>
        <div className="rows">
          {(v.evidence.length ? v.evidence : [{ source: "registry", source_url: null, retrieved_at: null, fields_compared: [], note: null }]).map((e, i) => (
            <div key={i} className="row">
              <div className="row-main">
                <div className="row-title">{e.source}</div>
                <div className="row-sub">{e.retrieved_at ? `${s.alertsUpdated} ${fmtTime(e.retrieved_at)}` : e.note || ""}</div>
              </div>
              <a className="btn-ghost" style={{ fontSize: 14 }} href={e.source_url || sourceHome(e.source)} target="_blank" rel="noreferrer">{s.openSource}</a>
            </div>
          ))}
        </div>
      </div>

      {/* Label vs registry */}
      <div className="card">
        <h2 className="card-title">{s.labelVsRegistry}</h2>
        <div className="rows">
          {comparisons.map((c) => (
            <CmpRowView key={c.field} row={c} s={s} />
          ))}
        </div>
        <div className="btn-row" style={{ marginTop: 12 }}>
          <button type="button" className="btn btn-secondary btn-block" onClick={() => onEdit(input)}>
            {s.editWhatWeRead}
          </button>
        </div>
      </div>

      {/* Batch code card */}
      {showBatch && (
        <div className="card" style={{ borderColor: "var(--differ-bg)", background: "#FFFBEB" }}>
          <h2 className="card-title">{s.batchCardTitle}</h2>
          <div className="row-value mono" style={{ textAlign: "left" }}>{batch}</div>
          {isUnusualBatch(batch) && <p className="notice notice-warn" style={{ marginTop: 8 }}>{s.batchUnusual}</p>}
          <p className="disclaimer" style={{ marginTop: 8 }}>{s.batchNotProof}</p>
        </div>
      )}

      {/* Signals card: consistency flags + batch conflict */}
      <SignalsCard result={result} s={s} />

      {/* Why this result */}
      <details className="card accordion" open={openWhy} onToggle={(e) => setOpenWhy((e.target as HTMLDetailsElement).open)}>
        <summary>
          <span>{s.whyResult}</span>
          <ChevronDown className="chev" size={18} />
        </summary>
        <ul className="stack" style={{ margin: "12px 0 0", paddingLeft: 18 }}>
          {buildReasons(result).map((key) => (
            <li key={key} className="disclaimer">{(s[key as keyof Strings] as string) || key}</li>
          ))}
        </ul>
      </details>

      {/* Actions */}
      <div className="btn-row">
        <button type="button" className="btn btn-primary btn-block" onClick={handleShare}>
          <Whatsapp size={20} /> {s.shareWhatsApp}
        </button>
        <a className="btn btn-secondary btn-block" href={REPORT_URL} target="_blank" rel="noreferrer">
          <Flag size={20} /> {s.reportConcern}
        </a>
        <div style={{ display: "flex", gap: 8 }}>
          <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={onCheckAnother}>
            <Camera size={20} /> {s.checkAnother}
          </button>
          <button type="button" className="btn btn-secondary" style={{ flex: 1 }} onClick={onSave} aria-pressed={isSaved}>
            {isSaved ? <BookmarkFilled size={20} /> : <Bookmark size={20} />} {isSaved ? s.saved : s.save}
          </button>
        </div>
      </div>

      {/* Coverage + disclaimer */}
      <div className="card">
        <CoverageLine s={s} registryStatus={registryStatus} />
      </div>
      <p className="disclaimer">{s.disclaimerShort}</p>
      <button type="button" className="btn btn-ghost btn-block" onClick={onOpenHow}>{s.howHaskeWorks}</button>

      {/* Medicines footer */}
      {v.footer && <div className="notice notice-info"><Alert size={18} /><span>{v.footer}</span></div>}
    </div>
  );
}

function CmpRowView({ row, s }: { row: CmpRow; s: Strings }) {
  const [open, setOpen] = useState(false);
  let pill: "pill-match" | "pill-differ" | "pill-unreadable" = "pill-unreadable";
  let word = s.notAvailable;
  if (row.regValue == null || row.labelValue == null) {
    pill = "pill-unreadable";
    word = s.notAvailable;
  } else if (row.sim != null && row.sim >= 0.8) {
    pill = "pill-match";
    word = s.match;
  } else if (row.sim != null && row.sim < 0.5) {
    pill = "pill-differ";
    word = s.differs;
  } else {
    pill = "pill-unreadable";
    word = s.differs;
  }
  return (
    <div style={{ borderBottom: "1px solid var(--border)" }}>
      <button type="button" className="row" style={{ width: "100%" }} onClick={() => setOpen((v) => !v)} aria-expanded={open}>
        <div className="row-main"><div className="row-title">{row.label}</div></div>
        <span className={`pill ${pill}`}>{word}</span>
      </button>
      {open && (
        <div style={{ padding: "0 2px 12px", display: "flex", flexDirection: "column", gap: 4 }}>
          <div className="step-note">Label: <span className="mono">{row.labelValue || "—"}</span></div>
          <div className="step-note">Registry: <span className="mono">{row.regValue || "—"}</span></div>
          {row.sim != null && <div className="step-note">{s.ocrConfidence}: {Math.round(row.sim * 100)}%</div>}
        </div>
      )}
    </div>
  );
}

// Map backend flag codes to i18n string keys.
const FLAG_LABEL_MAP: Record<string, keyof import("../i18n").Strings> = {
  EXPIRY_PAST: "signalExpiryPast",
  EXPIRY_FAR_FUTURE: "signalExpiryFarFuture",
  MFG_IN_FUTURE: "signalMfgFuture",
  SHELF_LIFE_MISMATCH: "signalShelfLifeMismatch",
  BATCH_PATTERN_UNUSUAL: "signalBatchUnusual",
  BATCH_DATE_CONFLICT: "signalBatchConflict",
};

function SignalsCard({ result, s }: { result: CheckResponse; s: Strings }) {
  // Gather signals from the evidence notes.
  const signalFlags: string[] = [];
  for (const e of result.verdict.evidence) {
    const note = e.note || "";
    // Parse "signals=FLAG1,FLAG2,..." from the evidence note.
    const sigMatch = note.match(/signals=([^;]+)/);
    if (sigMatch) {
      sigMatch[1].split(",").forEach((f) => signalFlags.push(f.trim()));
    }
    // Batch conflict is a separate section in the note.
    if (note.includes("batch_conflict:")) {
      if (!signalFlags.includes("BATCH_DATE_CONFLICT")) {
        signalFlags.push("BATCH_DATE_CONFLICT");
      }
    }
  }

  if (signalFlags.length === 0) return null;

  return (
    <div className="card" style={{ borderColor: "var(--differ-bg)", background: "#FFFBEB" }}>
      <h2 className="card-title">{s.signalsCardTitle}</h2>
      <ul style={{ margin: "8px 0 0", paddingLeft: 18 }}>
        {signalFlags.map((flag) => {
          const key = FLAG_LABEL_MAP[flag];
          if (key) {
            return (
              <li key={flag} className="disclaimer" style={{ marginBottom: 4 }}>
                {s[key] as string}
              </li>
            );
          }
          // Layout flags: "LAYOUT:SPELLING_ERROR:word" -> show the payload
          if (flag.startsWith("LAYOUT:")) {
            return (
              <li key={flag} className="disclaimer" style={{ marginBottom: 4 }}>
                {s.signalLayoutPrefix}: {flag.replace("LAYOUT:", "")}
              </li>
            );
          }
          return null;
        })}
      </ul>
      <p className="disclaimer" style={{ marginTop: 8 }}>{s.signalsNotProof}</p>
    </div>
  );
}

function CoverageLine({ s, registryStatus }: { s: Strings; registryStatus: RegistryStatus | null }) {
  if (!registryStatus || !registryStatus.record_count) {
    return <p className="disclaimer">{s.coverageUnavailable}</p>;
  }
  return (
    <p className="disclaimer">
      {s.coverageLine.replace("{n}", String(registryStatus.record_count))}
      {registryStatus.snapshot_date ? ` · ${s.alertsUpdated} ${fmtDate(registryStatus.snapshot_date)}` : ""}
      {` · ${s.coverageNapams}`}
    </p>
  );
}
