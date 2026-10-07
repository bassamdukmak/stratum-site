"""Generate public Markdown sidecars; --check fails when HTML and Markdown drift.
Run with Python3 and the existing BeautifulSoup installation.
"""
from pathlib import Path
from urllib.parse import urljoin
import re,sys
import xml.etree.ElementTree as ET
from urllib.parse import urlparse
from bs4 import BeautifulSoup,NavigableString,Comment
ROOT=Path(__file__).resolve().parents[1]
BASE='https://stratumwealth.ca/'
PAGES=tuple('index' if urlparse(loc.text).path=='/' else urlparse(loc.text).path.lstrip('/') for loc in ET.parse(ROOT/'sitemap.xml').findall('.//{*}loc'))
def render(node):
 if isinstance(node,Comment):return ''
 if isinstance(node,NavigableString):return re.sub(r'\s+',' ',str(node))
 tag=node.name
 if tag in ('script','style','nav','footer','form','button','svg','template') or node.has_attr('hidden') or node.get('aria-hidden')=='true':return ''
 if tag=='img':return '\n\n!['+node.get('alt','')+']('+urljoin(BASE,node.get('src',''))+')\n\n'
 if tag=='table' and (node.has_attr('cellpadding') or node.find('table')):
  return '\n\n'+''.join(render(child) for child in node.children)+'\n\n'
 if tag=='table':
  rows=[[render(cell).strip().replace('|',r'\|').replace('\n',' ') for cell in row.find_all(['th','td'],recursive=False)] for row in node.find_all('tr')]
  rows=[r for r in rows if r]
  if not rows:return ''
  assert all(len(r)==len(rows[0]) for r in rows),'Uneven table rows'
  rows.insert(1,['---']*len(rows[0]));caption=node.find('caption')
  return '\n\n'+(render(caption).strip()+'\n\n' if caption else '')+'\n'.join('| '+' | '.join(r)+' |' for r in rows)+'\n\n'
 text=''.join(render(child) for child in node.children)
 if tag=='a':return '['+text.strip()+']('+urljoin(BASE,node.get('href',''))+')'
 if tag in ('strong','b'):return '**'+text.strip()+'**'
 if tag in ('em','i'):return '*'+text.strip()+'*'
 if tag=='br':return '\n'
 if tag in ('h1','h2','h3','h4','h5','h6'):return '\n\n'+'#'*int(tag[1])+' '+text.strip()+'\n\n'
 if tag=='dt':return '\n\n### '+text.strip()+'\n\n'
 if tag in ('p','dd','figcaption'):return '\n\n'+text.strip()+'\n\n'
 if tag in ('div','section','header','tr','td') :return '\n\n'+text.strip()+'\n\n'
 if tag=='li':return '\n- '+text.strip()+'\n'
 return text
stale=[]
for slug in PAGES:
 soup=BeautifulSoup((ROOT/(slug+'.html')).read_text(),'html.parser');main=soup.find('main')
 if slug=='best-investing-newsletter':
  main=soup.body
  for ticker in main.select('.ticker-bar'):ticker.decompose()
 assert main
 content=''
 heading=soup.find('h1');assert heading
 if heading not in main.descendants:
  content+=render(heading)
  header=heading.find_parent('header')
  if header:content+=''.join(render(p) for p in header.find_all('p',recursive=True))
 content+=render(main)
 if slug=='index':
  content+='\n\n## Publisher and policies\n\nStratum Wealth · Ontario, Canada · [Contact](https://stratumwealth.ca/contact)\n\n[About](https://stratumwealth.ca/about) · [Terms](https://stratumwealth.ca/terms) · [Privacy](https://stratumwealth.ca/privacy) · [Editorial standards](https://stratumwealth.ca/editorial-policy)\n'
 content=re.sub(r'\n[ \t]+','\n',content);content=re.sub(r'\n{3,}','\n\n',content).strip()
 output='Source: '+(BASE if slug=='index' else BASE+slug)+'\n\n'+content+'\n';target=ROOT/(slug+'.md')
 if '--check' in sys.argv:
  if not target.exists() or target.read_text()!=output:stale.append(target.name)
 else:target.write_text(output)
if stale:raise SystemExit('Stale Markdown: '+', '.join(stale)+'; run scripts/build-markdown.py')
print(('Checked' if '--check' in sys.argv else 'Generated')+' '+str(len(PAGES))+' public Markdown versions.')
