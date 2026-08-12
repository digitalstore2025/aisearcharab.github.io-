import { readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";

const dist = "dist";
const assets = join(dist, "assets");
const html = await readFile(join(dist, "index.html"), "utf8");
if (!html.includes("<div id=\"root\"></div>")) throw new Error("missing root mount in production HTML");
if (/http:\/\//i.test(html)) throw new Error("insecure http URL detected in production HTML");

const entries = await readdir(assets);
let jsBytes = 0;
let cssBytes = 0;
for (const name of entries) {
  const bytes = (await stat(join(assets, name))).size;
  if (name.endsWith(".js")) jsBytes += bytes;
  if (name.endsWith(".css")) cssBytes += bytes;
}

const limits = { js: 250_000, css: 80_000 };
if (jsBytes > limits.js) throw new Error(`JS bundle budget exceeded: ${jsBytes} > ${limits.js}`);
if (cssBytes > limits.css) throw new Error(`CSS bundle budget exceeded: ${cssBytes} > ${limits.css}`);
console.log(JSON.stringify({ jsBytes, cssBytes, limits }));