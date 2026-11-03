import type { CheckResponse } from "../types";

/** Build a WhatsApp share text for a completed check. */
export function buildShareText(result: CheckResponse, sources: string[], link: string): string {
  const v = result.verdict;
  const nrn = result.nrn.canonical || result.nrn.raw || "—";
  const product = result.extraction.product_name || "—";
  const lines = [
    `Haske check — ${v.title}`,
    `Product: ${product}`,
    `NAFDAC number: ${nrn}`,
    `Sources checked: ${sources.join(", ") || "registry"}`,
    v.message,
    link,
  ];
  return lines.join("\n");
}

export function shareOnWhatsApp(text: string): void {
  const url = `https://wa.me/?text=${encodeURIComponent(text)}`;
  window.open(url, "_blank", "noopener");
}

export function sourceNames(result: CheckResponse): string[] {
  const names = new Set<string>();
  for (const e of result.verdict.evidence) {
    if (e.source) names.add(e.source);
  }
  return Array.from(names);
}
