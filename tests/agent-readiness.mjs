import assert from 'node:assert/strict';
import { handle, preferredType, markdownPath } from '../edge/worker.mjs';

const cases = [
  [null, 'text/html'], ['', null], ['*/*', 'text/html'], ['text/*', 'text/html'],
  ['text/markdown', 'text/markdown'], ['text/html', 'text/html'],
  ['text/markdown, text/html;q=0.8', 'text/markdown'],
  ['text/html;q=0.9, text/markdown;q=0.2', 'text/html'],
  ['text/markdown;q=0, text/html', 'text/html'],
  ['text/markdown;q=0, */*;q=1', 'text/html'],
  ['text/html;q=0, */*;q=1', 'text/markdown'],
  ['text/markdown;q=0, text/html;q=0', null], ['application/json', null],
  ['text/markdown, text/html', 'text/markdown'],
  ['TEXT/MARKDOWN; CHARSET="UTF-8"; Q=1', 'text/markdown'],
  ['text/markdown;variant=unavailable', null],
  ['text/markdown;q=bad', null], ['text/markdown;q=2', null],
  ['text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8', 'text/html'],
];
for (const [header, expected] of cases) assert.equal(preferredType(header), expected, header);
assert.equal(markdownPath('/'), '/index.md');
assert.equal(markdownPath('/index.html'), '/index.md');
assert.equal(markdownPath('/about.html'), '/about.md');

const html = '<!DOCTYPE html><html><body><h1>Stratum</h1></body></html>';
const md = '# Stratum\n\nAI-assisted market intelligence for retail investors.\n';
let calls = [];
const origin = async request => {
  calls.push(request);
  const path = new URL(request.url).pathname;
  if (path.startsWith('/missing')) return new Response(html, { status: 404, headers: { 'Content-Type': 'text/html' } });
  if (path === '/unavailable.md') return new Response('missing', { status: 404 });
  if (path.endsWith('.md') || path === '/llms.txt') return new Response(request.method === 'HEAD' ? null : md, { headers: { 'Content-Type': 'text/plain', ETag: 'md', 'Content-Encoding': 'gzip' } });
  if (path === '/favicon.png') return new Response('image', { headers: { 'Content-Type': 'image/png', 'Cache-Control': 'max-age=600' } });
  if (path === '/redirect') return new Response(null, { status: 301, headers: { Location: '/about' } });
  if (path === '/upstream-error') return new Response('upstream failure', { status: 500, headers: { 'Content-Type': 'text/html' } });
  return new Response(request.method === 'HEAD' ? null : html, { status: path.startsWith('/missing') ? 404 : 200, headers: { 'Content-Type': 'text/html', Vary: 'Accept-Encoding', ETag: 'html', 'Cache-Control': 'max-age=600' } });
};
const get = (path, accept, method = 'GET', extra = {}) => handle(new Request('https://stratumwealth.ca' + path, { method, headers: { Accept: accept, ...extra } }), origin);
for (const accept of ['text/markdown', 'text/html', 'text/markdown', '*/*', 'text/html']) {
  const r = await get('/', accept);
  assert.equal(r.status, 200);
  assert.match(r.headers.get('Vary'), /Accept-Encoding, Accept/);
  assert.equal(r.headers.get('Cache-Control'), 'no-store');
  assert.match(r.headers.get('Link'), /index.md.*alternate/);
  assert.equal(await r.text(), accept === 'text/markdown' ? md : html);
}
for (const path of ['/missing', '/missing.json', '/missing.md']) {
  const r = await get(path, 'text/markdown');
  assert.equal(r.status, 404);
  assert.match(r.headers.get('Content-Type'), /^text\/markdown/);
  const body = await r.text();
  assert.ok(body.length >= 20);
  assert.match(body, /\[llms.txt\]\(https:\/\/stratumwealth.ca\/llms.txt\)/);
  assert.equal(r.headers.get('ETag'), null);
}
assert.equal((await get('/missing', 'text/html')).status, 404);
assert.equal(await (await get('/missing', 'text/html')).text(), html);
assert.equal((await get('/', 'application/json')).status, 406);
assert.equal((await get('/upstream-error', 'text/markdown')).status, 500);
assert.equal((await get('/redirect', 'text/markdown')).headers.get('Location'), '/about');
const asset = await get('/favicon.png', 'text/markdown');
assert.equal(asset.headers.get('Content-Type'), 'image/png');
assert.equal(asset.headers.get('Cache-Control'), 'max-age=600');
for (const path of ['/index.md', '/llms.txt']) assert.match((await get(path, '*/*')).headers.get('Content-Type'), /^text\/markdown/);
const conditional = await get('/', 'text/markdown', 'GET', { 'If-None-Match': 'html', 'If-Modified-Since': 'yesterday', Range: 'bytes=0-1' });
assert.equal(conditional.status, 200);
for (const key of ['If-None-Match', 'If-Modified-Since', 'Range']) assert.equal(calls.at(-1).headers.get(key), null);
assert.equal(conditional.headers.get('ETag'), null);
assert.equal(conditional.headers.get('Content-Encoding'), null);
const head = await get('/', 'text/markdown', 'HEAD');
assert.equal(head.status, 200);
assert.equal(await head.text(), '');
assert.match(head.headers.get('Content-Type'), /^text\/markdown/);
assert.equal((await get('/unavailable', 'text/markdown')).status, 503);
calls = [];
await get('/api/subscribe', 'application/json', 'POST');
assert.equal(calls.length, 1);
assert.equal(calls[0].headers.get('Accept'), 'application/json');
calls = [];
await get('/trial', '*/*');
assert.equal(calls[0].headers.get('Accept'), '*/*');
calls = [];
await get('/favicon.png', '*/*', 'GET', { Range: 'bytes=0-1', 'If-None-Match': 'image' });
assert.equal(calls[0].headers.get('Range'), 'bytes=0-1');
assert.equal(calls[0].headers.get('If-None-Match'), 'image');
calls = [];
await get('/admin/missing', 'text/markdown');
assert.equal(calls[0].headers.get('Accept'), 'text/markdown');
console.log('PASS: negotiation, quality values, 404 bodies, cache isolation, HEAD, validators, assets, redirects, failures and write passthrough.');
