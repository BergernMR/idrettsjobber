# Weekly hero photos for Aurora (runs Sunday evening, shows from Monday 06:00)

Noah wants new photos in the big photo at the top of the front page every Monday at 06:00 Norwegian time
(decided 2026-10-24). The page does the switch itself: every row in `HERO_PHOTOS` in `index.html` carries
the Monday of the week it belongs to, and the page shows the newest week that has started (the week starts
Monday 06:00 in Europe/Oslo). So this task only has to add next week's photos before Monday 06:00.

## Steps
1. Work in the repo `BergernMR/idrettsjobber`, branch `main`. Run `git pull --rebase` first, because a bot
   commits match data every hour.
2. Work out next Monday's date (YYYY-MM-DD). If `HERO_PHOTOS` already has rows for that date, stop.
3. Find 15–20 NEW photos on Unsplash that are not already in `HERO_PHOTOS` (compare the photo ids):
   - Search pages such as `https://unsplash.com/s/photos/<query>` with WebFetch (curl hits a bot wall).
     Vary the queries each week: football/fotball, handball, ice hockey, bandy, cross-country skiing,
     biathlon, ski jumping, alpine, running/marathon, orienteering, cycling, sailing, rowing, kayak,
     swimming, stadium, plus city or country names (Oslo, Bergen, Trondheim, Stockholm, Göteborg, Malmö,
     København, Aarhus, Helsinki, Tampere, Reykjavík, Norway, Sweden, Denmark, Finland, Iceland).
   - Open each candidate's photo page with WebFetch and check:
     - the location on the page is in Norway, Sweden, Denmark, Finland or Iceland (Noah requires this);
     - it is free under the Unsplash License, not Unsplash+;
     - it shows sport or people being active (not just landscapes, flags, animals or city views).
   - Download a small copy (`https://images.unsplash.com/photo-<id>?w=400`) and look at it. Prefer
     landscape photos that work full-width behind white text. Skip blurry, dark, or very busy photos.
   - Mix sports, seasons and all five countries across the week.
4. Add one row per photo at the end of `HERO_PHOTOS`:
   `["<id without photo->", "<photographer>", "<photo page url>", "center 50%", "<next Monday>"], // <Place>, <CC>`
   Tune the second-last field (object-position) so faces and the action are not cropped.
5. Run `node --check` on the page script (extract it with
   `awk '/<script>/{f=1;next}/<\/script>/{f=0}f' index.html > /tmp/chk.js`).
6. Commit ("Toppbilder for uka <date>") and push to `main` (pull, rebase and retry if rejected).
7. To keep the file small, delete rows whose week is more than 8 weeks old.

Do not message Noah unless something failed. If too few good photos were found (under 10), add what you
have; the page keeps the previous week's photos when a week has none.
