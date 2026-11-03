#!/usr/bin/env node
/* Copy lint: fail the build if banned words appear outside the centralized
   string dictionary (src/i18n.ts). The words "fake", "counterfeit", and
   "genuine" are only allowed in the centralized disclaimer copy and
   alert-source quotes. */

import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const ROOT = new URL("../src", import.meta.url).pathname;
const ALLOWED = new Set(["i18n.ts"]);
const BANNED = /\b(fake|counterfeit|genuine)\b/i;

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.(ts|tsx)$/.test(name)) out.push(full);
  }
  return out;
}

const violations = [];
for (const file of walk(ROOT)) {
  if (ALLOWED.has(relative(ROOT, file).replace(/\\/g, "/"))) continue;
  const lines = readFileSync(file, "utf8").split("\n");
  lines.forEach((line, i) => {
    if (BANNED.test(line)) {
      violations.push(`${relative(ROOT, file)}:${i + 1}: ${line.trim()}`);
    }
  });
}

if (violations.length) {
  console.error("Copy lint failed. Banned words found outside src/i18n.ts:");
  for (const v of violations) console.error("  " + v);
  process.exit(1);
}

console.log("Copy lint passed.");
