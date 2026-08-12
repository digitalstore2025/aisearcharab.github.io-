import { readdir, readFile } from "node:fs/promises";
import { extname, join } from "node:path";

const roots = ["src"];
const blocked = [
  ["dangerouslySetInnerHTML", /dangerouslySetInnerHTML/],
  ["innerHTML", /\.innerHTML\s*=/],
  ["outerHTML", /\.outerHTML\s*=/],
  ["insertAdjacentHTML", /insertAdjacentHTML\s*\(/],
  ["document.write", /document\.write\s*\(/],
  ["eval", /\beval\s*\(/],
  ["Function constructor", /new\s+Function\s*\(/],
  ["localStorage", /\blocalStorage\b/],
  ["sessionStorage", /\bsessionStorage\b/],
  ["ts-ignore", /@ts-ignore/],
  ["ts-nocheck", /@ts-nocheck/],
];

async function files(path) {
  const entries = await readdir(path, { withFileTypes: true });
  const output = [];
  for (const entry of entries) {
    const full = join(path, entry.name);
    if (entry.isDirectory()) output.push(...await files(full));
    else if ([".ts", ".tsx", ".js", ".jsx"].includes(extname(entry.name))) output.push(full);
  }
  return output;
}

const failures = [];
for (const root of roots) {
  for (const file of await files(root)) {
    const source = await readFile(file, "utf8");
    for (const [name, pattern] of blocked) {
      if (pattern.test(source)) failures.push(`${file}: blocked ${name}`);
    }
    if (/console\.log\s*\(/.test(source)) failures.push(`${file}: console.log is forbidden`);
  }
}

if (failures.length) {
  console.error(failures.join("\n"));
  process.exit(1);
}
console.log("frontend source lint passed");