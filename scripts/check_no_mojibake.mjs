import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const files = [
  "frontend/index.html",
  "frontend/src/main.tsx",
  "frontend/src/styles.css",
  "scripts/check_no_mojibake.mjs",
];

const commonMojibakeFragments = [
  cp(0x59af, 0x2033, 0x7037),
  cp(0x93ba, 0x30e5, 0x53c6),
  cp(0x705e, 0x5ff3, 0x935a),
  cp(0x7459, 0x55da),
  cp(0x7487, 0xe195),
  cp(0x93b4, 0x6113),
  cp(0x6f76, 0x8fa8),
  cp(0x740e, 0xe082),
  cp(0x93c8, 0xe104),
  cp(0x934f, 0x62bd),
  cp(0x6d93, 0x5d84),
  cp(0x6d93, 0x5085),
  cp(0x9358, 0x5b2a),
  cp(0x935a, 0x60e7),
  cp(0x93c9, 0x51ae),
  cp(0x9435, 0x71b8),
  cp(0x95c3, 0x580d),
  cp(0x95c4, 0x6130),
  cp(0x93c3, 0x72b3),
  cp(0x5bb8, 0x53c9),
  cp(0x9357, 0x66df),
  cp(0x93be, 0x3089),
  cp(0x93cd, 0x51a8),
  cp(0x93bb, 0x8fa8),
  cp(0x7459, 0x5085),
  cp(0x93ad, 0x6b13),
  cp(0x9359, 0x5ea8),
  cp(0x935a, 0x719f),
  cp(0x934f, 0x60e7),
  cp(0x93a8, 0x3220),
  cp(0x748b, 0x55d7),
  cp(0x95b0, 0x52ec),
];

const patterns = [
  ["replacement character", /\uFFFD/g],
  ["latin-1 mojibake marker C3", /\u00c3/g],
  ["latin-1 mojibake marker C2", /\u00c2/g],
  ["cp1252 mojibake marker E2", /\u00e2/g],
  ["observed CJK mojibake fragment", /[\u59af\u5bb8\u93ba\u95b0\u704f\u6d93\u9359\u748b\u7459\u7487\u93c3\u6dc7\u6fb6\u93b6\u6769\u5bee]/g],
  ...commonMojibakeFragments.map((fragment) => [
    `common mojibake fragment ${fragment}`,
    new RegExp(escapeRegExp(fragment), "g"),
  ]),
];

const failures = [];

for (const file of files) {
  const text = readFileSync(resolve(root, file), "utf8");
  const lineStarts = [0];

  for (let i = 0; i < text.length; i += 1) {
    if (text[i] === "\n") {
      lineStarts.push(i + 1);
    }
  }

  for (const [name, pattern] of patterns) {
    pattern.lastIndex = 0;

    for (const match of text.matchAll(pattern)) {
      const index = match.index ?? 0;
      const lineIndex = upperBound(lineStarts, index) - 1;
      const line = lineIndex + 1;
      const column = index - lineStarts[lineIndex] + 1;
      failures.push(`${file}:${line}:${column} ${name} "${match[0]}"`);
    }
  }
}

if (failures.length > 0) {
  console.error("Potential mojibake detected:");
  for (const failure of failures) {
    console.error(`- ${failure}`);
  }
  process.exit(1);
}

console.log("encoding check ok");

function upperBound(values, target) {
  let low = 0;
  let high = values.length;

  while (low < high) {
    const mid = Math.floor((low + high) / 2);
    if (values[mid] <= target) {
      low = mid + 1;
    } else {
      high = mid;
    }
  }

  return low;
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function cp(...codes) {
  return String.fromCodePoint(...codes);
}
