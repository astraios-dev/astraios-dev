import { cpSync, existsSync, mkdirSync } from "node:fs";
import { resolve } from "node:path";

const root = resolve(".");
const dist = resolve("dist");

if (!existsSync(dist)) {
  throw new Error("dist/ does not exist. Run vite build before publishing.");
}

for (const file of [
  "index.html",
  "astraios-logo-mask.png",
  "astraios-wordmark-mask.png",
  "favicon.ico",
  "favicon-16x16.png",
  "favicon-32x32.png",
  "favicon-48x48.png",
  "apple-touch-icon.png",
  "icon-192.png",
  "icon-512.png",
]) {
  cpSync(resolve(dist, file), resolve(root, file));
}

mkdirSync(resolve(root, "assets"), { recursive: true });
cpSync(resolve(dist, "assets"), resolve(root, "assets"), { recursive: true });

console.log("Published static React bundle to the site root.");
