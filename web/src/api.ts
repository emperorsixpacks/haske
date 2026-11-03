import type { CheckInput, CheckResponse, RegistryStatus } from "./types";

const BASE = "/v1";

const REQUEST_TIMEOUT_MS = 45000;
const RETRY_ATTEMPTS = 2;
const RETRY_BACKOFF_MS = [600, 1600];

async function request(
  path: string,
  init: RequestInit,
  opts: { timeoutMs?: number; retries?: number } = {}
): Promise<Response> {
  const timeoutMs = opts.timeoutMs ?? REQUEST_TIMEOUT_MS;
  const retries = opts.retries ?? RETRY_ATTEMPTS;

  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const res = await fetch(`${BASE}${path}`, { ...init, signal: controller.signal });
      if (!res.ok && res.status >= 500 && attempt < retries) {
        await sleep(RETRY_BACKOFF_MS[attempt] ?? 1600);
        continue;
      }
      return res;
    } catch (err) {
      clearTimeout(timer);
      const isAbort = err instanceof DOMException && err.name === "AbortError";
      const isNetwork = !isAbort;
      if ((isAbort || isNetwork) && attempt < retries) {
        await sleep(RETRY_BACKOFF_MS[attempt] ?? 1600);
        continue;
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export class CheckError extends Error {
  status?: number;
  kind: "timeout" | "network" | "server" | "http";
  constructor(kind: "timeout" | "network" | "server" | "http", message: string, status?: number) {
    super(message);
    this.kind = kind;
    this.status = status;
  }
}

async function readError(res: Response): Promise<CheckError> {
  const text = await res.text().catch(() => "");
  const kind = res.status >= 500 ? "server" : "http";
  return new CheckError(kind, `check failed (${res.status}): ${text}`, res.status);
}

function frontPhoto(input: CheckInput): CapturedImage | null {
  if (input.kind !== "image") return null;
  const front = input.photos.find((p) => p.role === "front") ?? input.photos[0];
  return front ?? null;
}

interface CapturedImage {
  dataUrl: string;
}

export async function runCheck(input: CheckInput): Promise<CheckResponse> {
  if (input.kind === "fields") {
    const res = await request("/check/fields", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nrn: input.nrn, product_name: input.product_name || null }),
    });
    if (!res.ok) throw await readError(res);
    return (await res.json()) as CheckResponse;
  }

  const photo = frontPhoto(input);
  if (!photo) throw new CheckError("http", "no photo to send");

  const blob = await (await fetch(photo.dataUrl)).blob();
  const form = new FormData();
  form.append("image", blob, "label.jpg");
  const res = await request("/check", { method: "POST", body: form });
  if (!res.ok) throw await readError(res);
  return (await res.json()) as CheckResponse;
}

export async function fetchRegistryStatus(): Promise<RegistryStatus | null> {
  try {
    const res = await request("/registry/status", { method: "GET" }, { retries: 0 });
    if (!res.ok) return null;
    return (await res.json()) as RegistryStatus;
  } catch {
    return null;
  }
}

export function isOnline(): boolean {
  return typeof navigator === "undefined" || navigator.onLine !== false;
}
