"""Run: python3 tests/content-readiness.py [--live https://stratumwealth.ca]."""
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import json,re,subprocess,sys,xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,str(ROOT/'scripts/build-markdown.py'),'--check'],check=True)

def schema(html):
 s=BeautifulSoup(html,'html.parser')
 return [json.loads(x.string) for x in s.find_all('script',type='application/ld+json')]

def content(html):
 s=BeautifulSoup(html,'html.parser')
 for x in s(['script','style','nav','footer']):x.decompose()
 return s.get_text(' ',strip=True)

home=(ROOT/'index.html').read_text()
org=next(x for d in schema(home) for x in d.get('@graph',[]) if x.get('@type')=='Organization')
assert org['contactPoint']['email']=='stratumwealth@stratumwealth.ca'
assert org['contactPoint']['contactType']=='customer support'
assert org['address']=={'@type':'PostalAddress','addressRegion':'Ontario','addressCountry':'CA'}
base=subprocess.check_output(['git','show','578fd66:index.html'],cwd=ROOT,text=True)
a,b=[BeautifulSoup(x,'html.parser') for x in (home,base)]
assert str(a.main)==str(b.main),'Homepage content changed'
assert [x.string for x in a.find_all('style')]==[x.string for x in b.find_all('style')]
assert [x.string for x in a.find_all('script') if x.get('type')!='application/ld+json']==[x.string for x in b.find_all('script') if x.get('type')!='application/ld+json']
for name,kind in [('about','AboutPage'),('contact','ContactPage')]:
 page=(ROOT/(name+'.html')).read_text()
 assert len(content(page))>=500
 assert schema(page)[0]['@type']==kind
 assert f'href="https://stratumwealth.ca/{name}"' in page
 assert 'mailto:stratumwealth@stratumwealth.ca' in page
 assert BeautifulSoup(page,'html.parser').style.string==BeautifulSoup((ROOT/'editorial-policy.html').read_text(),'html.parser').style.string
assert len(content((ROOT/'privacy.html').read_text()))>=500
llms=(ROOT/'llms.txt').read_text()
assert llms.startswith('# Stratum Wealth\n\n> ')
assert llms.count('\n# ')==0
assert '## When to use this' in llms
assert 'Accept: text/markdown' in llms
for section in llms.split('\n## ')[1:]:
 for line in section.splitlines()[1:]:
  assert not line.strip() or re.match(r'- \[[^]]+\]\(https://[^)]+\)(: .+)?$',line),line
for target in re.findall(r'\]\(https://stratumwealth.ca/([^)]*)\)',llms):assert (ROOT/target).is_file(),target
sitemap=ET.parse(ROOT/'sitemap.xml')
urls=[loc.text for loc in sitemap.findall('.//{*}loc')]
assert len(urls)==13 and len(set(urls))==13
for url in urls:
 slug=urlparse(url).path.lstrip('/') or 'index'
 assert (ROOT/(slug+'.html')).is_file()
 md=(ROOT/(slug+'.md')).read_text()
 assert len(md)>100 and re.search(r'^# ',md,re.M)
 assert '<script' not in md and '<style' not in md
 assert 'application/json' not in md
 assert url in md
assert 'not indicative of future results' in (ROOT/'index.md').read_text()
assert 'historical' in (ROOT/'sample-report.md').read_text().lower()
# Exercise the existing renderer on headings, links, tables and presentation tables.
import runpy
old_argv=sys.argv;sys.argv=[str(ROOT/'scripts/build-markdown.py'),'--check']
r=runpy.run_path(str(ROOT/'scripts/build-markdown.py'))['render']
sys.argv=old_argv
assert r(BeautifulSoup('<a href="/privacy">Privacy</a>','html.parser').a)=='[Privacy](https://stratumwealth.ca/privacy)'
assert '| A | B |' in r(BeautifulSoup('<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>','html.parser').table)
assert 'first' in r(BeautifulSoup('<table cellpadding="0"><tr><td>first</td></tr><tr><td>second</td><td>third</td></tr></table>','html.parser').table)
assert r(BeautifulSoup('<form>hidden field</form>','html.parser').form)==''
assert r(BeautifulSoup('<p hidden>hidden text</p>','html.parser').p)==''
print('PASS: schema, trust-page length, llms.txt format and links, sitemap, Markdown fidelity, renderer and unchanged homepage scripts/styles/content.')

if '--live' in sys.argv:
 base_url=sys.argv[sys.argv.index('--live')+1].rstrip('/')
 failures=[];count=0
 def fetch(path,accept):
  global count
  request=Request(base_url+path,headers={'Accept':accept,'User-Agent':'Stratum-Readiness-Verification/1.0'})
  try:response=urlopen(request,timeout=30)
  except HTTPError as e:response=e
  count+=1
  return response.status,response.headers,response.read().decode()
 def check(label,test):
  try:test();print('PASS:',label)
  except Exception as e:failures.append(label+': '+str(e));print('FAIL:',label,str(e))
 def page_check(path,accept,expected_status=200):
  status,headers,body=fetch(path,accept)
  assert status==expected_status,f'status {status}'
  assert len(body.strip())>=20,'empty body'
  assert headers.get('Content-Type','').startswith(accept),headers.get('Content-Type')
  assert 'accept' in [x.strip().lower() for x in headers.get('Vary','').split(',')],headers.get('Vary')
  if expected_status==404 and accept=='text/markdown':assert re.search(r'\[[^]]+\]\(https://stratumwealth.ca/(llms.txt|sitemap.xml)',body),'missing recovery link'
  if accept=='text/markdown':assert '<!DOCTYPE' not in body,'HTML in Markdown response'
  return body
 for url in urls:
  path=urlparse(url).path
  for accept in ['text/markdown','text/html']:
   check(path+' '+accept,lambda p=path,a=accept:page_check(p,a))
 for path in ['/', '/', '/']:
  check('alternating homepage variants',lambda: (page_check(path,'text/markdown'),page_check(path,'text/html')))
 for path in ['/__ora-404-probe-xrovhl1g','/__stratum-readiness-missing.json']:
  for accept in ['text/markdown','text/html']:check(path+' '+accept,lambda p=path,a=accept:page_check(p,a,404))
 for path in ['/llms.txt']+[urlparse(u).path.rstrip('/')+'.md' if urlparse(u).path!='/' else '/index.md' for u in urls]:
  def static(p=path):
   status,headers,body=fetch(p,'*/*');assert status==200 and len(body)>20
   assert headers.get('Content-Type','').startswith('text/markdown'),headers.get('Content-Type')
   assert body==(ROOT/p.lstrip('/')).read_text(),'published content differs'
  check(path,static)
 def xml_check():
  status,headers,body=fetch('/sitemap.xml','application/xml');assert status==200
  assert body==(ROOT/'sitemap.xml').read_text()
  ET.fromstring(body)
 check('/sitemap.xml',xml_check)
 def robots_check():
  status,headers,body=fetch('/robots.txt','text/plain');assert status==200
  assert (ROOT/'robots.txt').read_text().strip() in body,'crawler policy changed'
 check('/robots.txt',robots_check)
 for name in ['about','contact','privacy']:
  def trust(n=name):
   status,headers,body=fetch('/'+n,'text/html');assert status==200 and len(content(body))>=500
  check('/'+name+' visible trust content',trust)
 def org_check():
  _,_,body=fetch('/','text/html')
  live=next(x for d in schema(body) for x in d.get('@graph',[]) if x.get('@type')=='Organization')
  assert live==org
 check('live Organization',org_check)
 print(f'Public verification: {count} responses, {len(failures)} failures.')
 (ROOT/'verification-results.json').write_text(json.dumps({'base_url':base_url,'responses':count,'failures':failures},indent=2)+'\n')
 if failures:sys.exit(1)
