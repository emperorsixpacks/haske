import type { CheckResponse } from "./types";

export async function checkImage(file: File): Promise<CheckResponse> {
  const form = new FormData();
  form.append("image", file, file.name);
  const res = await fetch("/v1/check", { method: "POST", body: form });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`check failed (${res.status}): ${text}`);
  }
  return (await res.json()) as CheckResponse;
}
