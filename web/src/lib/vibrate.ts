/** Haptic feedback via navigator.vibrate, guarded. */

export function vibrate(pattern: number | number[]): void {
  try {
    if (typeof navigator !== "undefined" && "vibrate" in navigator) {
      navigator.vibrate(pattern);
    }
  } catch {
    /* ignore */
  }
}

export function tick(): void {
  vibrate(12);
}
