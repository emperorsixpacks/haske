import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { STRINGS, type Lang } from "./i18n";
import type { CapturedPhoto, CheckInput, CheckResponse, RegistryStatus, SavedResult } from "./types";
import { runCheck, fetchRegistryStatus } from "./api";
import { clearSaved, deleteSaved, enqueueCheck, listQueue, listSaved, removeFromQueue, saveResult } from "./lib/idb";
import { useOnline } from "./lib/net";
import { makeId } from "./lib/image";
import { tick } from "./lib/vibrate";
import { Header } from "./components/Header";
import { TabBar, type Tab } from "./components/TabBar";
import { SettingsSheet, type TextSize } from "./components/SettingsSheet";
import { ScanScreen } from "./screens/ScanScreen";
import { CheckingScreen } from "./screens/CheckingScreen";
import { ResultScreen } from "./screens/ResultScreen";
import { AlertsScreen } from "./screens/AlertsScreen";
import { ClaimsScreen } from "./screens/ClaimsScreen";
import { SavedScreen } from "./screens/SavedScreen";

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

interface ActiveCheck {
  input: CheckInput;
  photos: CapturedPhoto[];
  result: CheckResponse | null;
  error: string | null;
}

function loadJson<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

export default function App() {
  const [tab, setTab] = useState<Tab>("scan");
  const [lang, setLang] = useState<Lang>(() => loadJson<Lang>("lang", "en"));
  const [textSize, setTextSize] = useState<TextSize>(() => loadJson<TextSize>("textSize", 100));
  const [settings, setSettings] = useState<null | "settings" | "how">(null);
  const [phase, setPhase] = useState<"capture" | "checking" | "result">("capture");
  const [check, setCheck] = useState<ActiveCheck | null>(null);
  const [saved, setSaved] = useState<SavedResult[]>([]);
  const [keepPhotos, setKeepPhotos] = useState<boolean>(() => loadJson<boolean>("keepPhotos", false));
  const [queueCount, setQueueCount] = useState(0);
  const [registryStatus, setRegistryStatus] = useState<RegistryStatus | null>(null);
  const [isSavedCurrent, setIsSavedCurrent] = useState(false);
  const [installEvent, setInstallEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [showInstall, setShowInstall] = useState(false);
  const [prefill, setPrefill] = useState<{ nrn: string; product_name: string } | null>(null);
  const online = useOnline();

  const s = STRINGS[lang];

  // text size
  useEffect(() => {
    document.documentElement.style.fontSize = `${textSize}%`;
    localStorage.setItem("textSize", JSON.stringify(textSize));
  }, [textSize]);

  useEffect(() => {
    localStorage.setItem("lang", JSON.stringify(lang));
    document.documentElement.lang = lang === "pcm" ? "en" : lang;
  }, [lang]);

  useEffect(() => {
    localStorage.setItem("keepPhotos", JSON.stringify(keepPhotos));
  }, [keepPhotos]);

  // load saved + registry status + queue
  useEffect(() => {
    void listSaved().then(setSaved);
    void fetchRegistryStatus().then((r) => setRegistryStatus(r));
    void refreshQueue();
  }, []);

  const refreshQueue = useCallback(async () => {
    setQueueCount((await listQueue()).length);
  }, []);

  // install prompt
  useEffect(() => {
    const onPrompt = (e: Event) => {
      e.preventDefault();
      setInstallEvent(e as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", onPrompt);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  const completedChecks = useRef(loadJson<number>("checksCompleted", 0));

  const runCheckFlow = useCallback(
    async (input: CheckInput, photos: CapturedPhoto[]) => {
      if (!online) {
        await enqueueCheck(input);
        await refreshQueue();
        return;
      }
      setPhase("checking");
      setCheck({ input, photos, result: null, error: null });
      setIsSavedCurrent(false);
      try {
        const response = await runCheck(input);
        setCheck({ input, photos, result: response, error: null });
        setPhase("result");
        tick();
        // cache the last result in the service worker
        if ("serviceWorker" in navigator) {
          const reg = await navigator.serviceWorker.getRegistration();
          reg?.active?.postMessage({ type: "SAVE_RESULT", result: { id: makeId(), response } });
        }
        completedChecks.current += 1;
        localStorage.setItem("checksCompleted", JSON.stringify(completedChecks.current));
        const dismissed = localStorage.getItem("installDismissed");
        if (completedChecks.current >= 2 && installEvent && !dismissed) {
          setShowInstall(true);
        }
      } catch (err) {
        setCheck({ input, photos, result: null, error: err instanceof Error ? err.message : String(err) });
        setPhase("result");
      }
    },
    [online, installEvent, refreshQueue]
  );

  // drain queue when back online
  const draining = useRef(false);
  useEffect(() => {
    if (!online) return;
    if (draining.current) return;
    draining.current = true;
    void (async () => {
      const items = await listQueue();
      for (const item of items) {
        try {
          await runCheck(item.input);
        } catch {
          /* leave in queue; keep it */
        }
        await removeFromQueue(item.id);
      }
      await refreshQueue();
      draining.current = false;
    })();
  }, [online, refreshQueue]);

  const handleSubmit = useCallback(
    (input: CheckInput) => {
      const photos = input.kind === "image" ? input.photos : [];
      void runCheckFlow(input, photos);
    },
    [runCheckFlow]
  );

  const handleCheckAnother = useCallback(() => {
    setPhase("capture");
    setCheck(null);
    setIsSavedCurrent(false);
    setTab("scan");
  }, []);

  const handleEdit = useCallback(
    (input: CheckInput) => {
      const nrn = check?.result?.nrn.canonical || (input.kind === "fields" ? input.nrn : "") || "";
      const name = check?.result?.extraction.product_name || (input.kind === "fields" ? input.product_name : "") || "";
      setPrefill({ nrn, product_name: name });
      setPhase("capture");
      setCheck(null);
      setTab("scan");
    },
    [check]
  );

  const handleSave = useCallback(async () => {
    if (!check?.result) return;
    const photos = keepPhotos ? check.photos : [];
    const entry: SavedResult = {
      id: makeId(),
      savedAt: new Date().toISOString(),
      outcome: check.result,
      keepPhotos,
      photos,
    };
    await saveResult(entry);
    setSaved(await listSaved());
    setIsSavedCurrent(true);
    tick();
  }, [check, keepPhotos]);

  const handleDelete = useCallback(async (id: string) => {
    await deleteSaved(id);
    setSaved(await listSaved());
  }, []);

  const handleDeleteAll = useCallback(async () => {
    if (!window.confirm(STRINGS[lang].deleteConfirm)) return;
    await clearSaved();
    setSaved(await listSaved());
  }, [lang]);

  const handleClearData = useCallback(async () => {
    await clearSaved();
    setSaved([]);
    localStorage.removeItem("checksCompleted");
    setSettings(null);
  }, []);

  const handleInstall = useCallback(async () => {
    if (!installEvent) return;
    await installEvent.prompt();
    await installEvent.userChoice;
    setShowInstall(false);
    setInstallEvent(null);
  }, [installEvent]);

  const handleDismissInstall = useCallback(() => {
    localStorage.setItem("installDismissed", "1");
    setShowInstall(false);
  }, []);

  const handleOpenSaved = useCallback((item: SavedResult) => {
    setCheck({
      input: { kind: "fields", nrn: item.outcome.nrn.canonical || "", product_name: item.outcome.extraction.product_name || "" },
      photos: item.photos,
      result: item.outcome,
      error: null,
    });
    setIsSavedCurrent(true);
    setPhase("result");
    setTab("scan");
  }, []);

  const handleCheckLast = useCallback(() => {
    /* No alert feed yet; the Alerts tab already shows an honest empty state. */
  }, []);

  const frontThumb = useMemo(() => {
    if (check?.photos.length) return check.photos[0].dataUrl;
    return null;
  }, [check]);

  const showTabs = phase !== "checking";

  return (
    <div className="app">
      <div className="desktop-note">{s.desktopNote}</div>
      <div className="app-column">
        <Header s={s} onSettings={() => setSettings("settings")} />

        {online ? null : (
          <div className="notice notice-warn" style={{ margin: "8px 16px 0" }}>
            <span>{s.offline}</span>
          </div>
        )}
        {queueCount > 0 && online && (
          <div className="notice notice-info" style={{ margin: "8px 16px 0" }}>
            <span>{s.queuedSending}</span>
          </div>
        )}

        <main className="main">
          {tab === "scan" && phase === "capture" && (
            <ScanScreen s={s} active={tab === "scan"} onSubmit={handleSubmit} prefill={prefill} onClearPrefill={() => setPrefill(null)} />
          )}
          {tab === "scan" && phase === "checking" && <CheckingScreen s={s} thumbnail={frontThumb} onCancel={() => handleCheckAnother()} />}
          {tab === "scan" && phase === "result" && check && (
            <ResultScreen
              s={s}
              result={check.result}
              error={check.error}
              input={check.input}
              photos={check.photos}
              isSaved={isSavedCurrent}
              onSave={() => void handleSave()}
              onCheckAnother={handleCheckAnother}
              onEdit={handleEdit}
              registryStatus={registryStatus}
              onOpenHow={() => setSettings("how")}
            />
          )}
          {tab === "alerts" && <AlertsScreen s={s} onCheckLast={handleCheckLast} />}
          {tab === "claims" && <ClaimsScreen s={s} />}
          {tab === "saved" && (
            <SavedScreen
              s={s}
              saved={saved}
              keepPhotos={keepPhotos}
              onToggleKeepPhotos={() => setKeepPhotos((v) => !v)}
              onOpen={handleOpenSaved}
              onDelete={(id) => void handleDelete(id)}
              onDeleteAll={() => void handleDeleteAll()}
            />
          )}
        </main>

        {showTabs && <TabBar tab={tab} onChange={setTab} s={s} />}
      </div>

      {settings && (
        <SettingsSheet
          s={s}
          lang={lang}
          onLang={setLang}
          textSize={textSize}
          onTextSize={setTextSize}
          onClearData={() => void handleClearData()}
          onClose={() => setSettings(null)}
          initialHow={settings === "how"}
        />
      )}

      {showInstall && (
        <div className="sheet" role="dialog" aria-label={s.installPrompt}>
          <p className="help" style={{ marginBottom: 12 }}>{s.installPrompt}</p>
          <div className="btn-row">
            <button type="button" className="btn btn-primary btn-block" onClick={() => void handleInstall()}>
              {s.installNow}
            </button>
            <button type="button" className="btn btn-secondary btn-block" onClick={handleDismissInstall}>
              {s.installLater}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
