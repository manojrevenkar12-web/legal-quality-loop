// Copies the generated results into the app's public folder, so the dashboard shows exactly what the report says.
import { copyFileSync, existsSync, mkdirSync } from "node:fs";
const src = new URL("../../reports/results.json", import.meta.url);
const dst = new URL("../public/results.json", import.meta.url);
mkdirSync(new URL("../public/", import.meta.url), { recursive: true });
if (existsSync(src)) copyFileSync(src, dst);
else console.warn("reports/results.json not found: run `qloop report` first");
