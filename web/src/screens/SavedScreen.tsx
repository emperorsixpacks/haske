import type { Strings } from "../i18n";
import type { SavedResult } from "../types";
import { Bookmark, ChevronRight, Trash } from "../components/icons";

interface Props {
  s: Strings;
  saved: SavedResult[];
  keepPhotos: boolean;
  onToggleKeepPhotos: () => void;
  onOpen: (item: SavedResult) => void;
  onDelete: (id: string) => void;
  onDeleteAll: () => void;
}

function fmtSaved(iso: string): string {
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  return d.toLocaleDateString("en-NG", { day: "2-digit", month: "short" }) + " · " + d.toLocaleTimeString("en-NG", { hour: "2-digit", minute: "2-digit" });
}

export function SavedScreen({ s, saved, keepPhotos, onToggleKeepPhotos, onOpen, onDelete, onDeleteAll }: Props) {
  return (
    <div className="stack">
      <div className="notice notice-info"><Bookmark size={18} /><span>{s.savedLocalOnly}</span></div>

      <label className="switch">
        <input type="checkbox" checked={keepPhotos} onChange={onToggleKeepPhotos} />
        <span className="help">{s.keepPhotos}</span>
      </label>

      {saved.length === 0 && (
        <div className="empty card">
          <div className="empty-icon"><Bookmark size={48} /></div>
          <p>{s.savedEmpty}</p>
        </div>
      )}

      {saved.map((item) => {
        const title = item.outcome.verdict.title;
        const product = item.outcome.extraction.product_name || item.outcome.nrn.canonical || "—";
        return (
          <div key={item.id} className="card" style={{ padding: 12 }}>
            <button type="button" className="row" style={{ width: "100%", border: "none" }} onClick={() => onOpen(item)}>
              <div className="row-main">
                <div className="row-title">{title}</div>
                <div className="row-sub">{product} · {fmtSaved(item.savedAt)}</div>
              </div>
              <ChevronRight size={20} style={{ color: "var(--text-secondary)" }} />
            </button>
            <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
              <button type="button" className="btn-ghost" style={{ fontSize: 14, padding: "6px 10px" }} onClick={() => onDelete(item.id)}>
                <Trash size={16} /> {s.delete}
              </button>
            </div>
          </div>
        );
      })}

      {saved.length > 0 && (
        <button type="button" className="btn btn-danger btn-block" onClick={onDeleteAll}>
          <Trash size={20} /> {s.deleteAll}
        </button>
      )}
    </div>
  );
}
