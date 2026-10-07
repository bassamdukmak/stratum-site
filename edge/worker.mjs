// Same-zone route: fetch reaches the existing GitHub Pages origin.
export function preferredType(header) {
  if (header === null) return 'text/html';
  const entries = header.split(/,(?=(?:[^"]*"[^"]*")*[^"]*$)/).map((raw, position) => {
    const [type, ...params] = raw.trim().toLowerCase().split(';').map(x => x.trim());
    let q = 1, specificity = type === '*/*' ? 0 : type === 'text/*' ? 1 : 2;
    let supported = true;
    for (const param of params) {
      const [name, value] = param.split('=').map(x => x.trim());
      if (name === 'q') { q = /^(0(?:\.\d{0,3})?|1(?:\.0{0,3})?)$/.test(value) ? Number(value) : 0; break; }
      if (name !== 'charset' || !/^"?utf-8"?$/.test(value)) supported = false;
      specificity += 1;
    }
    return { type, q, specificity, position, supported };
  });
  const ranked = ['text/html', 'text/markdown'].map(type => {
    const match = entries.filter(e => e.supported && [type, 'text/*', '*/*'].includes(e.type))
      .sort((a, b) => b.specificity - a.specificity || a.position - b.position)[0];
    return { type, q: match?.q ?? 0, position: match?.position ?? Infinity };
  }).sort((a, b) => b.q - a.q || a.position - b.position);
  return ranked[0].q > 0 ? ranked[0].type : null;
}

export function markdownPath(path) {
  return path === '/' || path === '/index.html' ? '/index.md' : path.replace(/\.html$/, '') + '.md';
}

function negotiated(response, request, type, transformed = false, alternate = null) {
  const headers = new Headers(response.headers);
  const vary = (headers.get('Vary') || '').split(',').map(x => x.trim()).filter(Boolean);
  if (!vary.some(x => ['accept', '*'].includes(x.toLowerCase()))) vary.push('Accept');
  headers.set('Vary', vary.join(', '));
  // ponytail: no shared cache for variants; add separate html/md cache keys if traffic warrants it.
  headers.set('Cache-Control', 'no-store');
  headers.set('Cloudflare-CDN-Cache-Control', 'no-store');
  headers.set('Link', [headers.get('Link'), '</llms.txt>; rel="describedby"',
    alternate && `<${alternate}>; rel="alternate"; type="text/markdown"`].filter(Boolean).join(', '));
  if (type) headers.set('Content-Type', type + '; charset=utf-8');
  if (transformed) {
    for (const key of ['content-length', 'content-encoding', 'etag', 'last-modified', 'content-range', 'accept-ranges']) headers.delete(key);
  }
  return new Response(request.method === 'HEAD' ? null : response.body, { status: response.status, statusText: response.statusText, headers });
}

export async function handle(request, origin = fetch) {
  if (!['GET', 'HEAD'].includes(request.method)) return origin(request);
  const url = new URL(request.url);
  if (['/trial', '/trial.html'].includes(url.pathname) || /^\/(api|admin|debug)(\/|$)/.test(url.pathname)) return origin(request);
  const headers = new Headers(request.headers);
  headers.set('Accept', 'text/html');
  // Validators and ranges for HTML must never produce a 304 or partial Markdown body.
  for (const key of ['if-none-match', 'if-modified-since', 'range', 'if-range']) headers.delete(key);
  const asset = /\.[^/]+$/.test(url.pathname) && !/\.(html|md)$/.test(url.pathname) && url.pathname !== '/llms.txt';
  const response = asset ? await origin(request) : await origin(new Request(request, { headers }), { cf: { cacheTtl: 0 } });
  if (response.status === 200 && (url.pathname.endsWith('.md') || url.pathname === '/llms.txt')) {
    return negotiated(response, request, 'text/markdown', true);
  }
  if (response.status !== 404 && !response.headers.get('Content-Type')?.includes('text/html')) return response;
  // Do not disguise upstream failures or redirects as successful agent content.
  if (response.status !== 200 && response.status !== 404) return negotiated(response, request);
  const type = preferredType(request.headers.get('Accept'));
  if (type === null) return negotiated(new Response('Not Acceptable. Available representations: text/html and text/markdown.\n', { status: 406 }), request, 'text/plain', true);
  if (response.status === 404) {
    if (type === 'text/html') return negotiated(response, request);
    return negotiated(new Response('# 404 — Page not found\n\nThe requested page does not exist on Stratum Wealth. Find available guides and research in [llms.txt](https://stratumwealth.ca/llms.txt) or the [sitemap](https://stratumwealth.ca/sitemap.xml).\n', { status: 404 }), request, type, true);
  }
  const alternate = markdownPath(url.pathname);
  if (type === 'text/html') return negotiated(response, request, null, false, alternate);
  const mdUrl = new URL(url);
  mdUrl.pathname = alternate;
  const md = await origin(new Request(mdUrl, { method: request.method, headers, redirect: 'manual' }), { cf: { cacheTtl: 0 } });
  if (md.status !== 200) return negotiated(new Response('# Markdown temporarily unavailable\n\nPlease retry later or consult [llms.txt](https://stratumwealth.ca/llms.txt).\n', { status: 503 }), request, type, true);
  return negotiated(new Response(md.body, { headers: response.headers }), request, type, true, alternate);
}

export default { fetch: request => handle(request) };
