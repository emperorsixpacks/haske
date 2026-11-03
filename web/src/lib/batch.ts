/* A tiny, clearly-labelled batch-code heuristic. Advisory only, never part of
   the verdict. Looks for repeated or sequential digit runs. */

export function isUnusualBatch(batch: string | null | undefined): boolean {
  if (!batch) return false;
  const digits = batch.replace(/[^0-9]/g, "");
  if (digits.length < 4) return false;

  // All same digit, e.g. 000000.
  if (/^(\d)\1+$/.test(digits)) return true;

  // A run of at least 5 consecutive ascending or descending digits.
  for (let i = 0; i + 5 <= digits.length; i++) {
    const win = digits.slice(i, i + 5).split("").map(Number);
    let asc = true;
    let desc = true;
    for (let j = 1; j < win.length; j++) {
      if (win[j] !== win[j - 1] + 1) asc = false;
      if (win[j] !== win[j - 1] - 1) desc = false;
    }
    if (asc || desc) return true;
  }
  return false;
}
