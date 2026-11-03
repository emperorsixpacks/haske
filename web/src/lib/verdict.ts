import type { CheckResponse, VerdictCode, VerdictTone } from "../types";

export type VerdictIcon = "check" | "alert" | "x" | "question";

export interface VerdictPresentation {
  tone: VerdictTone;
  icon: VerdictIcon;
  wordsKey:
    | "resultMatch"
    | "resultDiffers"
    | "resultNotFound"
    | "resultExpired"
    | "resultAlert"
    | "resultKnownTarget"
    | "resultUnreadable"
    | "resultOutage";
  isOutage: boolean;
}

const OUTAGE_HINTS = ["unavailable", "could not be checked", "did not respond", "recaptcha", "source unavailable", "not reachable"];

export function isRegistryOutage(code: VerdictCode, message: string): boolean {
  if (code !== "CANNOT_CONFIRM") return false;
  const m = message.toLowerCase();
  return OUTAGE_HINTS.some((h) => m.includes(h));
}

export function verdictPresentation(result: CheckResponse): VerdictPresentation {
  const { code, message } = result.verdict;

  switch (code) {
    case "CONSISTENT_WITH_REGISTRY":
      return { tone: "match", icon: "check", wordsKey: "resultMatch", isOutage: false };
    case "REGISTRY_MISMATCH":
      return { tone: "differ", icon: "alert", wordsKey: "resultDiffers", isOutage: false };
    case "NOT_FOUND_IN_REGISTRY":
      return { tone: "notfound", icon: "x", wordsKey: "resultNotFound", isOutage: false };
    case "EXPIRED_OR_INACTIVE":
      return { tone: "differ", icon: "alert", wordsKey: "resultExpired", isOutage: false };
    case "ALERT_MATCH":
      return { tone: "notfound", icon: "alert", wordsKey: "resultAlert", isOutage: false };
    case "KNOWN_TARGET":
      return { tone: "differ", icon: "alert", wordsKey: "resultKnownTarget", isOutage: false };
    case "CANNOT_CONFIRM":
      if (isRegistryOutage(code, message)) {
        return { tone: "unreadable", icon: "question", wordsKey: "resultOutage", isOutage: true };
      }
      return { tone: "unreadable", icon: "question", wordsKey: "resultUnreadable", isOutage: false };
    default:
      return { tone: "unreadable", icon: "question", wordsKey: "resultUnreadable", isOutage: false };
  }
}

/** Deterministic "why this result" reasons derived from the structured response. */
export function buildReasons(result: CheckResponse): string[] {
  const { verdict, nrn, match_outcome } = result;
  const reasons: string[] = [];

  if (nrn.is_barcode) {
    reasons.push("reasonBarcode");
  } else if (!nrn.valid) {
    reasons.push("reasonUnverifiable");
  }

  switch (verdict.code) {
    case "CONSISTENT_WITH_REGISTRY":
      reasons.push("reasonMatch");
      break;
    case "REGISTRY_MISMATCH":
      reasons.push("reasonMismatch");
      break;
    case "NOT_FOUND_IN_REGISTRY":
      reasons.push("reasonNrnNotFound");
      break;
    case "EXPIRED_OR_INACTIVE":
      reasons.push("reasonExpired");
      break;
    case "ALERT_MATCH":
    case "KNOWN_TARGET":
      reasons.push("reasonMismatch");
      break;
    case "CANNOT_CONFIRM":
      if (isRegistryOutage(verdict.code, verdict.message)) reasons.push("reasonUnavailable");
      else if (match_outcome === "AMBIGUOUS") reasons.push("reasonShared");
      else reasons.push("reasonUnverifiable");
      break;
  }

  if (nrn.ambiguous_o_zero) reasons.push("reasonUnverifiable");

  const unique = Array.from(new Set(reasons));
  return unique;
}
