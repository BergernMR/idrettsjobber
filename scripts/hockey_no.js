// Terminliste for EliteHockey Ligaen fra Norges Ishockeyforbund (live.hockey.no, Noah 2026-10-27).
// Siden bygges i nettleseren, så den åpnes i en vanlig (hodeløs) Chromium og den synlige teksten leses.
// Skriver data/hockey_no.json: {at, games: [[start ISO (Oslo-tid), hjemme, borte, hjemmemål|null, bortemål|null]]}
// Bruk: node scripts/hockey_no.js   (krever playwright)
const fs = require("fs"), path = require("path");
const { chromium } = require("playwright");
(async () => {
  const browser = await chromium.launch();
  try {
    const page = await browser.newPage();
    await page.goto("https://live.hockey.no/", { waitUntil: "networkidle", timeout: 60000 });
    await page.waitForTimeout(2000);
    const L = (await page.evaluate(() => document.body.innerText)).split("\n").map(s => s.trim()).filter(Boolean);
    const games = [];
    for (let i = 4; i < L.length; i++) {
      const m = L[i].match(/^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}:\d{2})$/);
      if (!m) continue;
      const [h, hs, a, as] = L.slice(i - 4, i);
      const sc = x => /^\d+$/.test(x) ? +x : null;
      if (!/^(\d+|-)$/.test(hs) || !/^(\d+|-)$/.test(as)) continue;
      games.push([`${m[3]}-${m[2]}-${m[1]}T${m[4]}`, h, a, sc(hs), sc(as)]);
    }
    if (games.length < 20) throw new Error("for få kamper: " + games.length);
    const out = path.join(__dirname, "..", "data", "hockey_no.json");
    fs.writeFileSync(out, JSON.stringify({ at: new Date().toISOString(), games }));
    console.log(`EliteHockey Ligaen: ${games.length} kamper`);
  } finally { await browser.close(); }
})().catch(e => { console.error("hockey_no feilet:", e.message); process.exit(1); });
