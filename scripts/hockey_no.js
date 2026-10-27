// Terminliste for EliteHockey Ligaen fra Norges Ishockeyforbund (live.hockey.no, Noah 2026-10-27).
// Siden bygges i nettleseren, så den åpnes i en vanlig (hodeløs) Chromium og den synlige teksten leses.
// Skriver data/hockey_no.json: {at, games: [[start ISO (Oslo-tid), hjemme, borte, hjemmemål|null, bortemål|null, ot]]}
// ot: 0 = avgjort på ordinær tid, 1 = forlengning eller straffer, null = ukjent. Leses fra kampsiden (en «OT»- eller «SO»-del
// etter 3. periode) og huskes mellom kjøringene, så bare nye kamper åpnes. Brukes til tabellen (3-2-1-0 poeng).
// Bruk: node scripts/hockey_no.js   (krever playwright)
const fs = require("fs"), path = require("path");
const { chromium } = require("playwright");
const OUT = path.join(__dirname, "..", "data", "hockey_no.json");
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
      games.push([`${m[3]}-${m[2]}-${m[1]}T${m[4]}`, h, a, sc(hs), sc(as), null]);
    }
    if (games.length < 20) throw new Error("for få kamper: " + games.length);
    // Forlengning: tidligere kjøringer huskes; nye spilte kamper åpnes (høyst 60 per kjøring)
    let prev = {};
    try { for (const g of JSON.parse(fs.readFileSync(OUT, "utf8")).games) if (g[5] != null) prev[g.slice(0, 5).join("|")] = g[5]; } catch (e) {}
    const dates = page.locator(".date p");
    let opened = 0;
    if (await dates.count() === games.length) {
      for (let i = 0; i < games.length; i++) {
        const g = games[i], key = g.slice(0, 5).join("|");
        if (g[3] == null) continue;
        if (key in prev) { g[5] = prev[key]; continue; }
        if (opened >= 60) continue;
        opened++;
        try {
          const before = page.url();
          await dates.nth(i).click();
          await page.waitForFunction(u => location.href !== u, before, { timeout: 8000 });
          await page.waitForTimeout(1200);
          await page.waitForFunction(() => /3\. PERIOD/.test(document.body.innerText), null, { timeout: 8000 });
          await page.waitForTimeout(400);
          const T = (await page.evaluate(() => document.body.innerText)).split("\n").map(s => s.trim());
          g[5] = T.some(l => /^(OT|SO|OVERTIME|SHOOTOUT|4\. PERIOD)$/i.test(l)) ? 1 : 0;
        } catch (e) { console.log("fant ikke kampsiden for", key); }
      }
    } else console.log("kampkortene stemte ikke med listen, hopper over forlengning");
    fs.writeFileSync(OUT, JSON.stringify({ at: new Date().toISOString(), games }));
    console.log(`EliteHockey Ligaen: ${games.length} kamper, ${opened} kampsider åpnet, ${games.filter(g => g[5] === 1).length} til forlengning`);
  } finally { await browser.close(); }
})().catch(e => { console.error("hockey_no feilet:", e.message); process.exit(1); });
