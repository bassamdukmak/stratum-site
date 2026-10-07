# Agent readiness edge route

GitHub Pages remains the HTML origin. This Cloudflare Worker runs on a same-zone
route (`stratumwealth.ca/*`); `fetch(request)` reaches that existing origin.
It negotiates public HTML and generated Markdown without moving the site or
changing subscription scripts. Private paths, write methods and the trial
redirect pass through. No paid conversion service or new dependency is required.

Protocols: https://acceptmarkdown.com/reference and https://llmstxt.org/.
Cloudflare routing: https://developers.cloudflare.com/workers/configuration/routing/routes/.
Organization address records only the already published Ontario, Canada region
and country. Add a street address, city, postal code or phone only after the
publisher approves verified public details.

## Build and check

From the repository root, with the existing Python BeautifulSoup installation,
Node.js 22+ and Wrangler available:

```sh
python3 scripts/build-markdown.py
python3 tests/content-readiness.py
node tests/agent-readiness.mjs
wrangler deploy --config edge/wrangler.jsonc --dry-run
```

The build reads sitemap.xml; add canonical pages there before regenerating.
The trial redirect is intentionally excluded. Run the --check build option in
any future site check to catch HTML/Markdown drift. Commit generated .md files.

## Release

1. Publish the checked HTML/Markdown files through the existing GitHub Pages
   main branch. Confirm Pages built that commit before enabling negotiation.
2. Authenticate Wrangler to the account owning stratumwealth.ca. Inspect current
   Worker routes first; do not replace an existing route without reconciling it.
   Confirm the hostname is proxied and the account's Worker plan/quota permits
   this small route without a paid upgrade.
3. Deploy `wrangler deploy --config edge/wrangler.jsonc`. The config attaches the
   route, enables logs/traces and disables workers.dev. No secret is embedded.
4. Run `python3 tests/content-readiness.py --live https://stratumwealth.ca`.
   It checks every sitemap page in HTML/Markdown, Markdown files, instructions,
   sitemap, robots policy, trust-page content, schema and 404 recovery bodies.
   Also inspect GET bodies, HEAD, 406, q-values and repeated alternating variants.

Negotiated responses use `Vary: Accept` and no-store. Origin asset caching is
preserved. If traffic warrants shared caching, introduce bounded html/md cache
keys and repeat alternating-variant checks; do not rely on Vary alone.

## Rollback

Remove only this Worker's stratumwealth.ca route to restore direct GitHub Pages
responses. The static About/Contact pages and Markdown links remain usable.
Revert the site commit separately if needed. Do not alter DNS or crawler policy.

Readiness scores are external measurements; rerun the Ora/Is Agentic audit after
live verification. Passing local checks does not establish a new score.
