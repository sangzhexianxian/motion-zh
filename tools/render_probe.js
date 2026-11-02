// 抽帧验证：加载 finance-cards 的 index.html，注入参数，按时间点截图
const path = require("path");
const { chromium } = require("/www/video-factory/science-web/node_modules/playwright");

const CHROME = "/root/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome";
const TPL = "/root/motion-zh/templates/finance-cards";
const OUT = "/root/motion-zh/probe";
const demo = require(path.join(TPL, "presets/demo.json"));

(async () => {
  const fs = require("fs");
  fs.mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({
    executablePath: CHROME,
    args: ["--no-sandbox", "--force-color-profile=srgb", "--font-render-hinting=none"],
  });
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => console.log("PAGEERROR:", e.message));
  await page.addInitScript((p) => { window.MP = p; }, demo);
  await page.goto("file://" + path.join(TPL, "src/index.html"));
  await page.waitForFunction("window.READY === true", { timeout: 15000 });

  const times = [1.2, 3.0, 5.2, 8.0, 10.5, 13.5, 17.0, 21.0, 23.2];
  for (const t of times) {
    await page.evaluate((tt) => window.SEEK(tt), t);
    await page.screenshot({ path: path.join(OUT, `f_${String(t).replace(".", "_")}.png`) });
    console.log("shot", t);
  }
  const dur = await page.evaluate(() => window.DURATION);
  console.log("DURATION", dur);
  await browser.close();
})();
