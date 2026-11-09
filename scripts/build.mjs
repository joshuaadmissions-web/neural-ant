import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = join(dirname(fileURLToPath(import.meta.url)), "..");
const sourceDirectory = join(projectRoot, "src");
const outputDirectory = join(projectRoot, "dist");

await rm(outputDirectory, { recursive: true, force: true });
await mkdir(outputDirectory, { recursive: true });
await cp(sourceDirectory, outputDirectory, { recursive: true });

const indexPath = join(outputDirectory, "index.html");
const cacheVersion = Date.now().toString(36);
const html = await readFile(indexPath, "utf8");
await writeFile(indexPath, html
  .replaceAll("./app.js", `./app.js?v=${cacheVersion}`)
  .replaceAll("./growth.js", `./growth.js?v=${cacheVersion}`)
  .replaceAll("./styles.css", `./styles.css?v=${cacheVersion}`));

console.log("Neural Ant built into dist/.");
