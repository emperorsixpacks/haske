/* External links. The NAFDAC reporting URL is the domain root until the exact
   official reporting channel is verified; do not ship a specific contact number
   that has not been confirmed against an official NAFDAC source. */

export const NAFDAC_HOME = "https://www.nafdac.gov.ng";
export const REPORT_URL = NAFDAC_HOME;

export function sourceHome(source: string): string {
  const s = source.toLowerCase();
  if (s.includes("napams")) return "https://registration.nafdac.gov.ng";
  if (s.includes("greenbook")) return "https://greenbook.nafdac.gov.ng";
  return NAFDAC_HOME;
}
