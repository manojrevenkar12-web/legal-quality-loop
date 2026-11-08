// README screenshots from a running dashboard: node scripts/screenshots.mjs http://localhost:5174 docs/img
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE ?? "playwright");
const [base = "http://localhost:5174", out = "docs/img"] = process.argv.slice(2);
const browser = await chromium.launch();
const errors = [];
for (const [name, viewport, scale] of [["dashboard", { width: 1280, height: 900 }, 1], ["dashboard-mobile", { width: 390, height: 844 }, 2]]) {
  const page = await browser.newPage({ viewport, deviceScaleFactor: scale });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  await page.goto(base);
  await page.waitForTimeout(2200);
  await page.screenshot({ path: `${out}/${name}.png`, fullPage: true });
  if (name === "dashboard") {
    await page.screenshot({ path: `${out}/hero.png`, clip: { x: 0, y: 0, width: 1280, height: 760 } });
    await page.getByRole("tab", { name: "Scored by the calibrated judge and checks" }).click();
    await page.waitForTimeout(1800);
    const el = await page.locator("#searches").locator("..").boundingBox();
    await page.screenshot({ path: `${out}/search-trusted.png`, clip: { x: 0, y: el.y - 10, width: 1280, height: el.height + 20 } });
  }
  await page.close();
}
await browser.close();
if (errors.length) { console.error(errors.join("\n")); process.exit(1); }
