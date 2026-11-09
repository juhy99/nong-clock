"""Official agricultural policy archive collector. Python 3.10+. No API key."""
import argparse,csv,hashlib,io,json,logging,re,sqlite3,sys,time,urllib.request,urllib.parse,urllib.error,zipfile,zlib
from pathlib import Path
from datetime import datetime,timezone,timedelta
from lxml import html,etree
BASE=Path(__file__).resolve().parent
KST=timezone(timedelta(hours=9))
POLICY=re.compile(r'수매|방출|비축|할당\s*관세|저율\s*관세|TRQ|국영\s*무역|수입권\s*공매',re.I)
ITEMS='배추 무 양파 마늘 대파 감자 고구마 당근 양배추 상추 시금치 깻잎 토마토 방울토마토 오이 호박 가지 고추 건고추 사과 배 감귤 포도 복숭아 수박 참외 딸기 멜론 쌀 콩 대두 팥 녹두 메밀 참깨 땅콩 밀 옥수수 바나나 오렌지 파인애플 망고 키위 버섯 느타리 팽이 새송이 양송이'.split()
def stamp():return datetime.now(KST).isoformat(timespec='seconds')
def clean(s):return re.sub(r'[ \t\xa0]+',' ',s).strip()
def text(el):
 for x in el.xpath('.//script|.//style|.//noscript'):x.drop_tree()
 return '\n'.join(clean(x) for x in el.itertext() if clean(x))
def parse_html(body):
 if isinstance(body,bytes):
  for enc in ['utf-8-sig','cp949','euc-kr']:
   try:body=body.decode(enc);break
   except UnicodeDecodeError:pass
  if isinstance(body,bytes):raise ValueError('HTML인코딩확인필요')
 return html.fromstring(body)
def canonical(u):
 p=urllib.parse.urlsplit(u);q=urllib.parse.parse_qs(p.query)
 if '/view.action' in p.path:q={k:v for k,v in q.items() if k=='articleId'}
 return urllib.parse.urlunsplit((p.scheme,p.netloc,p.path,urllib.parse.urlencode(q,doseq=True),''))
def document_links(source,body,url):
 root=parse_html(body);out={}
 for a in root.xpath('//a[@href]'):
  u=urllib.parse.urljoin(url,a.get('href'));title=clean(' '.join(a.itertext()))
  if source['kind']=='at':ok=('/article/'+source['board']+'/view.action') in u and 'articleId=' in u
  else:ok=bool(re.search('/bbs/home/'+source['board']+r'/\d+/artclView\.do',u))
  if ok and title:
   row=a
   for parent in a.iterancestors():
    if parent.tag in ('tr','li'):row=parent;break
   rt=' '.join(row.itertext());date=find_date(rt)
   out[canonical(u)]={'title':title,'date':date}
 return out
DATE=re.compile(r'(?<!\d)((?:19|20)\d{2})[.\-/년]\s*(\d{1,2})[.\-/월]\s*(\d{1,2})')
def find_date(s):
 m=DATE.search(s)
 if not m:return ''
 try:return datetime(*map(int,m.groups())).date().isoformat()
 except ValueError:return ''
def page_details(body,url,hint=''):
 root=parse_html(body);titles=root.xpath('//meta[@property="og:title"]/@content') or root.xpath('//title/text()');title=hint or (titles[0].split(' - ')[0] if titles else '')
 # Prefer article bodies; title boundary excludes the common site navigation.
 nodes=[]
 for sel in ['//*[contains(concat(" ",normalize-space(@class)," ")," artclView ")]','//*[contains(@class,"view_con")]','//*[contains(@class,"viewCont")]','//*[contains(@class,"board_view")]','//article','//main']:
  nodes=root.xpath(sel)
  if nodes:break
 whole=text(root);content=text(nodes[0]) if nodes else whole
 if title and title in content:content=content[content.index(title):]
 for tail in ['업무담당자 담당부서','이전글','다음글','COPYRIGHT']:
  i=content.find(tail)
  if i>20:content=content[:i]
 dt='';date_status='미확인'
 for pattern in [r'(?:작성일|등록일|게시일|보도시점|보도일시)[\s:]*([^\n]{0,100})']:
  for m in re.finditer(pattern,content):
   dt=find_date(m[1])
   if dt:date_status='게시일_본문표기_최초공개시각미확인';break
  if dt:break
 if not dt:
  for v in root.xpath('//meta[contains(@property,"published") or @name="pubdate"]/@content'):
   dt=find_date(v)
   if dt:date_status='게시일_메타데이터_최초공개시각미확인';break
 links=[]
 for a in root.xpath('//a[@href]'):
  u=urllib.parse.urljoin(url,a.get('href'));label=clean(' '.join(a.itertext()))
  if u.startswith(('http://','https://')) and (re.search(r'/download\.action|/download\.do|/fileDown|/FileDown|/fileDownload',u,re.I) or re.search(r'\.(pdf|hwp|hwpx|xlsx?|csv|zip)(?:\?|$)',u,re.I)):
   links.append((u,label))
 # Keep only same official domains; generic footer downloads are not attachments.
 links=list(dict.fromkeys((u,l) for u,l in links if urllib.parse.urlsplit(u).hostname in ('www.at.or.kr','at.or.kr','www.mafra.go.kr','mafra.go.kr')))
 return title,content,dt,date_status,links

def kinds(s):
 return '|'.join(k for k,p in [('정부수매',r'수매'),('비축방출',r'방출|비축.*공급|비축.*판매'),('비축',r'비축'),('할당관세',r'할당\s*관세'),('WTO_TRQ',r'WTO.*TRQ|저율관세할당'),('FTA_TRQ',r'FTA.*TRQ|FTA.*수입권'),('TRQ_세부미확인',r'TRQ|저율\s*관세'),('수입권공매',r'수입권\s*공매')] if re.search(p,s,re.I))
def item_matches(s):
 # Short commodity names are ambiguous: exclude them unless bounded.
 return '|'.join(n for n in ITEMS if re.search(r'(?<![가-힣])'+re.escape(n)+r'(?![가-힣])',s))
def amount(v):
 v=v.replace(',','').replace(' ','')
 if not re.fullmatch(r'[\d.]+(?:만[\d.]*)?(?:천[\d.]*)?',v):return ''
 try:
  result=0
  for token,mult in [('만',10000),('천',1000)]:
   if token in v:a,v=v.split(token,1);result+=float(a or 1)*mult
  return result+float(v or 0)
 except ValueError:return ''
def evidence_rows(docid,title,content,url,origin,pub):
 out=[]
 for line in re.split(r'[\n]|(?<=[다요])\.\s+',content):
  if not POLICY.search(line):continue
  quantities=[{'원문':m[0],'수치':amount(m[1]),'단위':m[2]} for m in re.finditer(r'([\d,.]+\s*(?:만\s*[\d,.]*)?\s*(?:천\s*[\d,.]*)?)\s*(톤|ton|kg|㎏|t|포기|개|호|%)',line,re.I)]
  periods=[m[0] for m in DATE.finditer(line)]
  stage='계획표현' if re.search(r'예정|계획|추진|방침|예산|목표',line) else '실적표현_검토필요' if re.search(r'실적|낙찰|방출했|방출하였|공급했|공급하였|통관',line) else '미확정'
  out.append(dict(문서ID=docid,문서제목=title,게시일=pub,발표일시='',정책유형후보=kinds(line),품목후보=item_matches(line),계획실적구분후보=stage,물량세율후보JSON=json.dumps(quantities,ensure_ascii=False),시행일관련표현JSON=json.dumps(periods,ensure_ascii=False),근거문장=line,근거파일=origin,원문주소=url,검수상태='미검수_자동추출후보_학습미승인'))
 return out

def extract_file(path):
 b=path.read_bytes()
 if b.startswith(b'%PDF'):
  from pypdf import PdfReader
  parts=[]
  for i,p in enumerate(PdfReader(io.BytesIO(b)).pages):parts.append(f'\n[PDF {i+1}쪽]\n'+(p.extract_text() or ''))
  t=''.join(parts)
  if len(re.sub(r'\s','',t))<30:raise ValueError('PDF문자없음_OCR필요')
  return t
 if zipfile.is_zipfile(path):
  z=zipfile.ZipFile(path);names=z.namelist()
  if any(n.startswith('Contents/section') and n.endswith('.xml') for n in names):
   return '\n'.join(' '.join(etree.fromstring(z.read(n)).itertext()) for n in names if n.startswith('Contents/section') and n.endswith('.xml'))
  if 'xl/workbook.xml' in names:
   ss=[]
   if 'xl/sharedStrings.xml' in names:ss=[''.join(x.itertext()) for x in etree.fromstring(z.read('xl/sharedStrings.xml'))]
   lines=[]
   for n in names:
    if re.match(r'xl/worksheets/sheet\d+\.xml$',n):
     for row in etree.fromstring(z.read(n)).xpath('//*[local-name()="row"]'):
      vals=[]
      for c in row:
       v=c.xpath('./*[local-name()="v"]/text()');val=v[0] if v else ''.join(c.xpath('.//*[local-name()="t"]/text()'))
       if c.get('t')=='s' and val:val=ss[int(val)]
       vals.append(val)
      lines.append('\t'.join(vals))
   return '\n'.join(lines)
  raise ValueError('ZIP원본보존_압축내첨부별도검수필요')
 if b.startswith(bytes.fromhex('D0CF11E0')):raise ValueError('HWP또는XLS_원본저장완료_텍스트변환필요')
 if path.suffix.lower() in ['.txt','.csv','.html','.htm']:
  for e in ['utf-8-sig','cp949','utf-16']:
   try:return b.decode(e)
   except UnicodeError:pass
 raise ValueError('지원외형식_원본저장완료')

class Collector:
 def __init__(self,cfg,out):
  self.cfg=cfg;self.out=out;out.mkdir(parents=True,exist_ok=True)
  for n in ['html','attachments','text','diagnostics']: (out/n).mkdir(exist_ok=True)
  self.db=sqlite3.connect(out/'progress.sqlite');self.db.executescript('''CREATE TABLE IF NOT EXISTS docs(url TEXT PRIMARY KEY,source TEXT,title TEXT,pub TEXT,body TEXT,status TEXT,err TEXT,hash TEXT,at TEXT);CREATE TABLE IF NOT EXISTS pages(source TEXT,page INTEGER,signature TEXT,status TEXT,PRIMARY KEY(source,page));CREATE TABLE IF NOT EXISTS files(url TEXT PRIMARY KEY,doc TEXT,path TEXT,status TEXT,err TEXT,at TEXT);''');self.db.commit();self.last=0
 def get(self,u):
  for i in range(self.cfg['retries']):
   time.sleep(max(0,self.cfg['delay_seconds']-(time.monotonic()-self.last)));self.last=time.monotonic()
   try:
    req=urllib.request.Request(u,headers={'User-Agent':'NongClock-Research-Collector/1.0','Accept':'*/*'})
    with urllib.request.urlopen(req,timeout=self.cfg['timeout_seconds']) as r:b=r.read();headers=dict(r.headers)
    if not b:raise ValueError('응답본문없음')
    if b'<html' in b[:1000].lower() and any(x in b[:100000].lower() for x in [b'access denied',b'captcha',b'just a moment']):raise ValueError('접근차단_응답')
    return b,headers
   except Exception:
    if i+1==self.cfg['retries']:raise
    time.sleep(min(2**i,10))
 def commit(self):self.db.commit()
 def scan(self,s,probe=False,refresh=False):
  page=1;previous=set();limit=self.cfg.get('max_pages',0)
  while True:
   old=self.db.execute('select signature,status from pages where source=? and page=?',(s['id'],page)).fetchone()
   if old and old[1]=='done' and not refresh and not probe:previous.add(old[0]);page+=1;continue
   if old and old[1]=='end' and not refresh and not probe:return
   u=s['list_url']+('&' if '?' in s['list_url'] else '?')+urllib.parse.urlencode({s['page_param']:page})
   try:
    b,_=self.get(u);links=document_links(s,b,u)
    (self.out/'diagnostics'/f'{s["id"]}_page{page}.html').write_bytes(b) if page<=2 else None
    if not links:raise ValueError('게시글링크0_종료로간주하지않음_페이지구조확인필요')
    sig=hashlib.sha256('\n'.join(sorted(links)).encode()).hexdigest()
    if sig in previous:raise ValueError('이전페이지반복_페이지이동실패또는끝페이지_완료판정안함')
    previous.add(sig)
    for url,v in links.items():self.db.execute('insert or ignore into docs values(?,?,?,?,?,?,?,?,?)',(url,s['id'],v['title'],v['date'],'','queued','','',''))
    # Count pagination bounds only when explicitly exposed by the site.
    root=parse_html(b)
    if page==1:
     inputs=root.xpath('//input/@name')
     for field in ['page','_page','pageIndex','currentPage','at.condition.currentPage']:
      if field in inputs and s['page_param'] not in inputs:s['page_param']=field;break
    txt=clean(' '.join(root.itertext()));last=re.search(r'Page\s*\d+\s*/\s*([\d,]+)',txt,re.I)
    last_page=int(last[1].replace(',','')) if last else None
    if not last_page:
     nums=[]
     for a in root.xpath('//a[@href or @onclick]'):
      code=a.get('href','')+' '+a.get('onclick','');m=re.search(r'(?:page_link|jf_artclList|goPage|fn_page|fnPage)\s*\(\s*[\'\"]?(\d+)',code)
      if m:nums.append(int(m[1]))
     # Last-page control must be explicitly labelled as the end.
      if m and re.search('끝|마지막|last',(' '.join(a.itertext())+' '+a.get('title','')+' '+a.get('class','')),re.I):last_page=int(m[1])
    self.db.execute('insert or replace into pages values(?,?,?,?)',(s['id'],page,sig,'done'));self.commit();print(f'[목록] {s["id"]} {page}페이지 / {len(links)}개',flush=True)
    if last_page and page>=last_page:
     self.db.execute('insert or replace into pages values(?,?,?,?)',(s['id'],page+1,'','end'));self.commit();return
    if probe and page>=2:return
    if limit and page>=limit:print('[부분수집] 설정한 max_pages 도달');return
    page+=1
   except Exception as e:
    self.db.execute('insert or replace into pages values(?,?,?,?)',(s['id'],page,'','error:'+str(e)));self.commit();print('[목록오류]',s['id'],page,e,flush=True);return
 def detail(self,url,source,title,pub):
  try:
   b,_=self.get(url);did=hashlib.sha256(url.encode()).hexdigest()[:20];(self.out/'html'/f'{did}.html').write_bytes(b)
   title,body,dt,_,links=page_details(b,url,title);pub=dt or pub
   if len(body)<40:raise ValueError('본문부족_페이지구조확인필요')
   # All details inspected; attachments downloaded only for relevant documents.
   relevant=bool(POLICY.search(title+'\n'+body));state='relevant' if relevant else 'excluded'
   self.db.execute('update docs set title=?,pub=?,body=?,status=?,err=?,hash=?,at=? where url=?',(title,pub,body,state,'',hashlib.sha256(body.encode()).hexdigest(),stamp(),url));self.commit()
   if relevant:
    (self.out/'text'/f'{did}.txt').write_text(body,encoding='utf-8-sig')
    for u,label in links:self.db.execute('insert or ignore into files values(?,?,?,?,?,?)',(u,url,'','queued','',''))
    self.commit()
   print('[본문]',source,state,title[:70],flush=True)
  except Exception as e:
   self.db.execute('update docs set status=?,err=? where url=?',('error',str(e),url));self.commit();print('[본문오류]',title,str(e),flush=True)
 def attachment(self,u,doc):
  try:
   b,h=self.get(u)
   if b'<html' in b[:500].lower() or b'<!doctype html' in b[:500].lower():raise ValueError('첨부대신HTML반환')
   name=urllib.parse.parse_qs(urllib.parse.urlsplit(u).query).get('fileName',[''])[0]
   disp=h.get('Content-Disposition',h.get('content-disposition',''));m=re.search(r"filename\*=UTF-8''([^;]+)|filename=\"?([^\";]+)",disp,re.I)
   if m:name=urllib.parse.unquote(m[1] or m[2])
   name=name or Path(urllib.parse.urlsplit(u).path).name
   if b.startswith(b'%PDF') and not name.lower().endswith('.pdf'):name+='.pdf'
   name=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',name)[:150];key=hashlib.sha256(u.encode()).hexdigest()[:16];p=self.out/'attachments'/(key+'_'+name);p.write_bytes(b)
   self.db.execute('update files set path=?,status=?,err=?,at=? where url=?',(str(p.resolve()),'downloaded','',stamp(),u));self.commit();print('[첨부]',p.name,flush=True)
  except Exception as e:
   self.db.execute('update files set status=?,err=? where url=?',('error',str(e),u));self.commit();print('[첨부오류]',str(e),flush=True)
 def export(self):
  docs=list(self.db.execute('select * from docs'));files=list(self.db.execute('select * from files'));events=[];catalog=[];facts=[];fs=[]
  def save(name,rows,fields):
   with (self.out/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
  for url,source,title,pub,body,status,err,hs,at in docs:
   did=hashlib.sha256(url.encode()).hexdigest()[:20]
   catalog.append(dict(문서ID=did,출처=source,제목=title,게시일=pub,발표일시='',발표일시검증='미검증_게시일은최초발표시각과다를수있음',수집일시=at,원문주소=url,본문상태=status,오류=err,본문SHA256=hs))
   if status=='relevant':
    events.append(dict(문서ID=did,제목=title,게시일=pub,정책유형후보=kinds(title+'\n'+body),품목후보=item_matches(title+'\n'+body),원문주소=url,본문SHA256=hs,중복주의='문서단위중복제거_동일정책재발표는미병합_물량합산금지',검수상태='미검수_사건확정표아님'))
    facts+=evidence_rows(did,title,body,url,'HTML본문',pub)
  docmap={r[0]:r for r in docs}
  for u,doc,path,status,err,at in files:
   extraction='미실행';txt=''
   if status=='downloaded' and Path(path).exists():
    try:txt=extract_file(Path(path));extraction='추출완료'
    except Exception as e:extraction=str(e)
   if txt:
    tp=self.out/'text'/(Path(path).name+'.txt');tp.write_text(txt,encoding='utf-8-sig');r=docmap[doc];facts+=evidence_rows(hashlib.sha256(doc.encode()).hexdigest()[:20],r[2],txt,doc,Path(path).name,r[3])
   fs.append(dict(첨부주소=u,문서주소=doc,저장경로=path,다운로드상태=status,추출상태=extraction,오류=err,수집일시=at))
  save('01_전체문서_수집목록.csv',catalog,['문서ID','출처','제목','게시일','발표일시','발표일시검증','수집일시','원문주소','본문상태','오류','본문SHA256'])
  save('02_정책문서_후보목록.csv',events,['문서ID','제목','게시일','정책유형후보','품목후보','원문주소','본문SHA256','중복주의','검수상태'])
  save('03_물량세율_원문근거_검토용.csv',facts,['문서ID','문서제목','게시일','발표일시','정책유형후보','품목후보','계획실적구분후보','물량세율후보JSON','시행일관련표현JSON','근거문장','근거파일','원문주소','검수상태'])
  save('04_첨부파일_수집상태.csv',fs,['첨부주소','문서주소','저장경로','다운로드상태','추출상태','오류','수집일시'])
  pages=list(self.db.execute('select source,page,status from pages'));states={s['id']:('목록끝확인' if any(x[0]==s['id'] and x[2]=='end' for x in pages) else '미완료_오류또는부분수집') for s in self.cfg['sources']}
  summary={'작성시각':stamp(),'대상기간':'사이트가공개하는전체기간_날짜제한없음','출처목록상태':states,'문서수':len(docs),'정책후보문서수':len(events),'검토용근거문장수':len(facts),'목록오류수':sum(x[2].startswith('error') for x in pages),'문서오류수':sum(r[5]=='error' for r in docs),'첨부오류수':sum(r[3]=='error' for r in files),'대기문서수':sum(r[5]=='queued' for r in docs),'대기첨부수':sum(r[3]=='queued' for r in files),'주의':'전체정부기록완전성보장없음_발표시각및시행기간및실적물량은원문검수필요_자동추출학습미승인'}
  (self.out/'검증요약.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8-sig');print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True);return summary
 def run(self,args):
  try:
   if args.mode!='export':
    for s in self.cfg['sources']:self.scan(s,args.mode=='probe',args.refresh)
    for seed in self.cfg.get('seed_urls',[]):self.db.execute('insert or ignore into docs values(?,?,?,?,?,?,?,?,?)',(seed,'추가공식URL','','','','queued','','',''))
    self.commit()
    if args.mode!='probe':
     for r in list(self.db.execute("select url,source,title,pub from docs where status in ('queued','error')")):self.detail(*r)
     for r in list(self.db.execute("select url,doc from files where status in ('queued','error')")):self.attachment(*r)
  finally:result=self.export();self.db.close()
  return result
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['run','probe','export'],default='run');p.add_argument('--config',default=str(BASE/'config.json'));p.add_argument('--refresh',action='store_true');args=p.parse_args();cfg=json.loads(Path(args.config).read_text(encoding='utf-8-sig'));result=Collector(cfg,BASE/cfg['output_dir']).run(args)
 if result['목록오류수'] or result['문서오류수'] or result['첨부오류수']:sys.exit(2)
if __name__=='__main__':main()
