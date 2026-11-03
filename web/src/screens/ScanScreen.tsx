import { useCallback, useEffect, useRef, useState } from "react";
import type { Strings } from "../i18n";
import type { CapturedPhoto, CheckInput, PhotoRole } from "../types";
import { formatBytes, processPhoto } from "../lib/image";
import { tick } from "../lib/vibrate";
import { Camera, Gallery, Plus, Torch, X, Back } from "../components/icons";

interface Props {
  s: Strings;
  active: boolean;
  onSubmit: (input: CheckInput) => void;
  prefill?: { nrn: string; product_name: string } | null;
  onClearPrefill?: () => void;
}

type CamState = "starting" | "ready" | "denied" | "unavailable";

export function ScanScreen({ s, active, onSubmit, prefill, onClearPrefill }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cam, setCam] = useState<CamState>("starting");
  const [mode, setMode] = useState<"camera" | "manual">("camera");
  const [torchOn, setTorchOn] = useState(false);
  const [photos, setPhotos] = useState<CapturedPhoto[]>([]);
  const [hint, setHint] = useState<string | null>(null);
  const [flash, setFlash] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // manual entry
  const [nrn, setNrn] = useState("");
  const [name, setName] = useState("");

  // Apply an "edit what we read" prefill.
  useEffect(() => {
    if (prefill) {
      setMode("manual");
      setNrn(prefill.nrn);
      setName(prefill.product_name);
      onClearPrefill?.();
    }
  }, [prefill, onClearPrefill]);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setCam("starting");
    setTorchOn(false);
  }, []);

  const start = useCallback(async () => {
    if (!active) return;
    setCam("starting");
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        setCam("unavailable");
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "environment" },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => {});
      }
      setCam("ready");
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      setCam(name === "NotAllowedError" ? "denied" : "unavailable");
    }
  }, [active]);

  useEffect(() => {
    if (!active) {
      stop();
    } else if (mode === "camera" && photos.length === 0) {
      void start();
    }
  }, [active, mode, photos.length, start, stop]);

  // Stop the camera when this screen unmounts (e.g. moving to checking).
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    };
  }, []);

  const toggleTorch = useCallback(async () => {
    const track = streamRef.current?.getVideoTracks()[0];
    if (!track || typeof track.getCapabilities !== "function") return;
    const caps = track.getCapabilities() as MediaTrackCapabilities & { torch?: boolean };
    if (!caps.torch) return;
    try {
      await track.applyConstraints({ advanced: [{ torch: !torchOn } as unknown as MediaTrackConstraintSet] });
      setTorchOn((v) => !v);
    } catch {
      /* torch unsupported on this device */
    }
  }, [torchOn]);

  const captureFrame = useCallback(async (role: PhotoRole) => {
    const video = videoRef.current;
    if (!video || video.videoWidth === 0) return;
    setBusy(true);
    try {
      const canvas = document.createElement("canvas");
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(video, 0, 0);
      canvas.toBlob(
        async (blob) => {
          if (!blob) return;
          const file = new File([blob], "capture.jpg", { type: "image/jpeg" });
          const photo = await processPhoto(file, role);
          setPhotos((prev) => (prev.length >= 3 ? prev : [...prev, photo]));
          stop();
          setFlash(true);
          tick();
          window.setTimeout(() => setFlash(false), 240);
          setBusy(false);
        },
        "image/jpeg",
        0.9
      );
    } catch {
      setBusy(false);
    }
  }, []);

  const onFile = useCallback(
    async (file: File | undefined) => {
      if (!file) return;
      setBusy(true);
      try {
        const role: PhotoRole = photos.length === 0 ? "front" : photos.length === 1 ? "batch" : "back";
        const photo = await processPhoto(file, role);
        setPhotos((prev) => (prev.length >= 3 ? prev : [...prev, photo]));
        stop();
        tick();
      } finally {
        setBusy(false);
      }
    },
    [photos.length]
  );

  // Live luminance hint, sampled every 500ms from a downscaled frame.
  useEffect(() => {
    if (cam !== "ready" || photos.length > 0) return;
    const id = window.setInterval(() => {
      const video = videoRef.current;
      if (!video || video.videoWidth === 0) return;
      try {
        const c = document.createElement("canvas");
        c.width = 16;
        c.height = 12;
        const ctx = c.getContext("2d");
        if (!ctx) return;
        ctx.drawImage(video, 0, 0, 16, 12);
        const data = ctx.getImageData(0, 0, 16, 12).data;
        let sum = 0;
        for (let i = 0; i < data.length; i += 4) sum += 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
        const avg = sum / (data.length / 4);
        setHint(avg < 60 ? s.hintDark : null);
      } catch {
        /* ignore sampling errors */
      }
    }, 500);
    return () => window.clearInterval(id);
  }, [cam, photos.length, s.hintDark]);

  const submit = useCallback(() => {
    if (photos.length === 0) return;
    onSubmit({ kind: "image", photos });
  }, [photos, onSubmit]);

  const submitManual = useCallback(() => {
    const trimmed = nrn.trim();
    if (!trimmed) return;
    onSubmit({ kind: "fields", nrn: trimmed, product_name: name.trim() });
  }, [nrn, name, onSubmit]);

  const removePhoto = useCallback((id: string) => {
    setPhotos((prev) => prev.filter((p) => p.id !== id));
  }, []);

  // --- manual entry mode ---
  if (mode === "manual") {
    return (
      <div className="stack fade-in">
        <div className="card">
          <div className="card-head">
            <h2 className="card-title">{s.manualTitle}</h2>
            <button type="button" className="btn-ghost icon-btn" onClick={() => setMode("camera")} aria-label={s.close}>
              <X size={22} />
            </button>
          </div>
          <div className="stack">
            <div className="field">
              <label className="label" htmlFor="nrn">{s.manualNrnLabel}</label>
              <input
                id="nrn"
                className="input mono"
                value={nrn}
                onChange={(e) => setNrn(e.target.value)}
                placeholder={s.manualNrnPlaceholder}
                autoCapitalize="characters"
                autoCorrect="off"
                spellCheck={false}
              />
              <p className="help">{s.manualExample}</p>
            </div>
            <div className="field">
              <label className="label" htmlFor="name">{s.manualNameLabel}</label>
              <input id="name" className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder={s.manualNamePlaceholder} />
            </div>
            <button type="button" className="btn btn-primary btn-block" disabled={!nrn.trim()} onClick={submitManual}>
              {s.submitManual}
            </button>
          </div>
        </div>
      </div>
    );
  }

  // --- review sheet after capture ---
  if (photos.length > 0) {
    const totalBytes = photos.reduce((sum, p) => sum + p.bytes, 0);
    return (
      <div className="stack fade-in">
        <div className="card">
          <p className="kicker">{photos.length} {s.photosCount}</p>
          <div className="photo-strip">
            {photos.map((p) => (
              <div key={p.id} style={{ position: "relative" }}>
                <img className="thumb" src={p.dataUrl} alt={p.role} />
                <button
                  type="button"
                  aria-label={s.retake}
                  onClick={() => removePhoto(p.id)}
                  style={{ position: "absolute", top: -6, right: -6, width: 24, height: 24, borderRadius: 12, background: "#334155", color: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center" }}
                >
                  <X size={14} />
                </button>
              </div>
            ))}
            {photos.length < 3 && (
              <button type="button" className="round-ctl" onClick={() => fileRef.current?.click()} aria-label={s.addBatchPhoto}>
                <Plus size={22} />
              </button>
            )}
          </div>
          <p className="help" style={{ marginTop: 8 }}>
            {photos.length < 3 ? s.addBatchPhoto : ""} · {formatBytes(totalBytes)} {s.sizeNote}
          </p>
          <input ref={fileRef} type="file" accept="image/*" className="sr-only" onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = ""; }} />
        </div>
        <div className="btn-row">
          <button type="button" className="btn btn-primary btn-block" onClick={submit} disabled={busy}>
            <Camera size={20} /> {s.checkProduct}
          </button>
          <button type="button" className="btn btn-secondary btn-block" onClick={() => setPhotos([])}>
            {s.retake}
          </button>
        </div>
      </div>
    );
  }

  // --- camera viewfinder ---
  return (
    <div className="stack">
      <div className="cam-wrap">
        <video ref={videoRef} playsInline muted autoPlay aria-label={s.fitLabel} />
        {cam === "ready" && <div className="cam-frame" />}
        {cam !== "ready" && (
          <div className="cam-hint" style={{ top: "50%", bottom: "auto", transform: "translateY(-50%)" }}>
            <div className="hint-pill">
              {cam === "starting" ? s.fitLabel : cam === "denied" ? s.cameraUnavailableTitle : s.cameraUnavailableTitle}
            </div>
          </div>
        )}
        {hint && cam === "ready" && (
          <div className="cam-hint">
            <span className="hint-pill">{hint}</span>
          </div>
        )}
        <div className={`flash${flash ? " go" : ""}`} />
      </div>

      {cam !== "ready" && (
        <div className="notice notice-slate">
          <Camera size={18} />
          <span>{s.cameraUnavailableBody}</span>
        </div>
      )}

      <div className="cam-controls">
        <button type="button" className="round-ctl" onClick={toggleTorch} aria-label={s.torch}>
          <Torch size={22} />
        </button>
        <button
          type="button"
          className="shutter"
          aria-label={s.checkProduct}
          disabled={cam !== "ready" || busy}
          onClick={() => void captureFrame("front")}
        >
          <span className="shutter-core" />
        </button>
        <button type="button" className="round-ctl" aria-label={s.gallery} onClick={() => fileRef.current?.click()}>
          <Gallery size={22} />
        </button>
      </div>
      <input ref={fileRef} type="file" accept="image/*" className="sr-only" onChange={(e) => { void onFile(e.target.files?.[0]); e.target.value = ""; }} />

      <button type="button" className="btn btn-ghost btn-block" onClick={() => setMode("manual")}>
        <Back size={18} style={{ transform: "rotate(90deg)" }} /> {s.typeInstead}
      </button>
    </div>
  );
}
