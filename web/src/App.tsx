import { useCallback, useRef, useState } from "react";
import { checkImage } from "./api";
import type { CheckResponse } from "./types";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "done"; result: CheckResponse }
  | { kind: "error"; message: string };

const VERDICT_STYLES: Record<string, string> = {
  CONSISTENT_WITH_REGISTRY: "bg-teal-50 border-teal-600 text-teal-900",
  REGISTRY_MISMATCH: "bg-amber-50 border-amber-600 text-amber-900",
  NOT_FOUND_IN_REGISTRY: "bg-orange-50 border-orange-600 text-orange-900",
  EXPIRED_OR_INACTIVE: "bg-amber-50 border-amber-600 text-amber-900",
  ALERT_MATCH: "bg-red-50 border-red-600 text-red-900",
  CANNOT_CONFIRM: "bg-slate-50 border-slate-500 text-slate-800",
};

const VERDICT_BADGE: Record<string, string> = {
  CONSISTENT_WITH_REGISTRY: "bg-teal-600",
  REGISTRY_MISMATCH: "bg-amber-600",
  NOT_FOUND_IN_REGISTRY: "bg-orange-600",
  EXPIRED_OR_INACTIVE: "bg-amber-600",
  ALERT_MATCH: "bg-red-600",
  CANNOT_CONFIRM: "bg-slate-500",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "unknown";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toUTCString();
}

export default function App() {
  const [state, setState] = useState<State>({ kind: "idle" });
  const [preview, setPreview] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const onFile = useCallback(async (file: File | undefined) => {
    if (!file) return;
    setPreview(URL.createObjectURL(file));
    setState({ kind: "loading" });
    try {
      const result = await checkImage(file);
      setState({ kind: "done", result });
    } catch (err) {
      setState({ kind: "error", message: err instanceof Error ? err.message : String(err) });
    }
  }, []);

  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      <header className="bg-teal-700 text-white px-4 py-4">
        <h1 className="text-2xl font-bold tracking-tight">Haske</h1>
        <p className="text-teal-100 text-sm">Check a product against the NAFDAC registry</p>
      </header>

      <main className="max-w-md mx-auto p-4 space-y-4">
        <section className="bg-white rounded-xl shadow-sm p-4 space-y-3">
          <input
            ref={fileRef}
            type="file"
            accept="image/*"
            capture="environment"
            className="hidden"
            onChange={(e) => onFile(e.target.files?.[0])}
          />
          <button
            onClick={() => fileRef.current?.click()}
            className="w-full py-3 bg-teal-600 text-white font-semibold rounded-lg active:bg-teal-700"
          >
            Take or choose a photo
          </button>
          {preview && (
            <img src={preview} alt="product" className="w-full rounded-lg border border-slate-200" />
          )}
        </section>

        {state.kind === "loading" && (
          <div className="bg-white rounded-xl shadow-sm p-6 text-center text-slate-500">
            <div className="animate-spin h-8 w-8 border-4 border-teal-600 border-t-transparent rounded-full mx-auto mb-2" />
            Checking the registry...
          </div>
        )}

        {state.kind === "error" && (
          <div className="bg-red-50 border border-red-300 text-red-800 rounded-xl p-4">
            Something went wrong: {state.message}
          </div>
        )}

        {state.kind === "done" && <VerdictCard result={state.result} />}
      </main>
    </div>
  );
}

function VerdictCard({ result }: { result: CheckResponse }) {
  const { verdict, extraction, nrn } = result;
  const style = VERDICT_STYLES[verdict.code] ?? VERDICT_STYLES.CANNOT_CONFIRM;
  const badge = VERDICT_BADGE[verdict.code] ?? VERDICT_BADGE.CANNOT_CONFIRM;
  const asOf = verdict.evidence[0]?.retrieved_at ?? null;

  return (
    <section className={`rounded-xl shadow-sm border-2 ${style} overflow-hidden`}>
      <div className={`${badge} text-white px-4 py-2 font-semibold`}>{verdict.title}</div>
      <div className="p-4 space-y-3">
        <p className="text-sm">{verdict.message}</p>

        <dl className="text-sm space-y-1 border-t border-black/10 pt-2">
          <div className="flex justify-between">
            <dt className="text-black/60">Product</dt>
            <dd className="font-medium">{extraction.product_name ?? "unreadable"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-black/60">Registration no.</dt>
            <dd className="font-medium">{nrn.canonical ?? "unreadable"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-black/60">Checked</dt>
            <dd className="font-medium">{fmtDate(asOf)}</dd>
          </div>
        </dl>

        {verdict.evidence.length > 0 && (
          <div className="text-sm border-t border-black/10 pt-2">
            <p className="font-semibold mb-1">Evidence</p>
            <ul className="space-y-1">
              {verdict.evidence.map((e, i) => (
                <li key={i}>
                  {e.source_url ? (
                    <a href={e.source_url} target="_blank" rel="noreferrer" className="underline">
                      {e.source}
                    </a>
                  ) : (
                    <span>{e.source}</span>
                  )}
                  {e.note ? <span className="text-black/60"> - {e.note}</span> : null}
                </li>
              ))}
            </ul>
          </div>
        )}

        {verdict.footer && (
          <p className="text-xs text-black/70 border-t border-black/10 pt-2">{verdict.footer}</p>
        )}
      </div>
    </section>
  );
}
