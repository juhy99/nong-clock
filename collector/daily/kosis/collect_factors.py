"""농산물 가격요인 수집기. Python 3.10+, 표준라이브러리만으로 날씨/환율/KOSIS 수집.
달력의 공휴일은 holidays 패키지를 설치하면 추가된다. 원자료는 출처별로 보존한다.
"""
import argparse, calendar, csv, datetime as dt, hashlib, json, os, re, sys, time
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qsl, unquote
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

ROOT=Path(__file__).resolve().parent
CFG=ROOT/'config.json'
KMA='https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList'
ECOS='https://ecos.bok.or.kr/api'
# 기상청 전국/지역 통계 산출 62개소 + 제주4개소. 전체 ASOS 지점은 아님.
STATIONS={108:'서울',112:'인천',119:'수원',201:'강화',202:'양평',203:'이천',90:'속초',105:'강릉',216:'태백',95:'철원',100:'대관령',101:'춘천',114:'원주',211:'인제',212:'홍천',127:'충주',131:'청주',135:'추풍령',221:'제천',226:'보은',129:'서산',133:'대전',232:'천안',235:'보령',236:'부여',238:'금산',130:'울진',136:'안동',138:'포항',143:'대구',271:'봉화',272:'영주',273:'문경',277:'영덕',278:'의성',279:'구미',281:'영천',152:'울산',155:'창원',159:'부산',162:'통영',192:'진주',284:'거창',285:'합천',288:'밀양',289:'산청',294:'거제',295:'남해',140:'군산',146:'전주',243:'부안',244:'임실',245:'정읍',247:'남원',248:'장수',156:'광주',165:'목포',168:'여수',170:'완도',260:'장흥',261:'해남',262:'고흥',184:'제주',185:'고산',188:'성산',189:'서귀포'}
QUERIES=['채소','식량작물','과실','재배면적','농가구입','농업노동','생산자물가','경유','골판지']
class DataError(Exception): pass
class StopService(DataError): pass

def atomic_json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(tmp,path)

def csvout(path,rows,fields=None):
 path.parent.mkdir(parents=True,exist_ok=True)
 if fields is None: fields=list(dict.fromkeys(k for r in rows for k in r))
 tmp=path.with_suffix(path.suffix+'.tmp')
 with tmp.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
 os.replace(tmp,path)

def parse_response(raw, kosis=False):
 try:return json.loads(raw)
 except json.JSONDecodeError:
  if not kosis:raise DataError('JSON이 아닌 응답. 활용승인·키·응답형식을 확인하세요.')
 # KOSIS 오류 응답의 마지막 쉼표만 문자열 바깥에서 제거한다.
 out=[];quoted=False;escaped=False
 for i,ch in enumerate(raw):
  if quoted:
   out.append(ch)
   if escaped:escaped=False
   elif ch=='\\':escaped=True
   elif ch=='"':quoted=False
  else:
   if ch=='"':quoted=True
   if ch==',':
    j=i+1
    while j<len(raw) and raw[j].isspace():j+=1
    if j<len(raw) and raw[j] in '}]':continue
   out.append(ch)
 try:return json.loads(''.join(out))
 except json.JSONDecodeError:raise DataError('KOSIS 응답을 JSON으로 해석할 수 없음. HTML/점검/접속제한 여부 확인 필요.') from None

def fetch(url,params=None):
 # 오류 메시지에 요청 URL과 인증키를 남기지 않는다.
 full=url+('?' + urlencode(params) if params else '')
 for attempt in range(4):
  try:
   with urlopen(Request(full,headers={'User-Agent':'AgriFactorCollector/1.0'}),timeout=60) as r:
    raw=r.read().decode('utf-8-sig')
   return parse_response(raw, urlsplit(url).hostname=='kosis.kr')
  except HTTPError as e:
   if e.code in (401,403):raise StopService('인증/권한 오류. 해당 서비스 활용신청과 키를 확인하세요.') from None
   msg=f'HTTP {e.code}'
  except (URLError,TimeoutError,OSError): msg='네트워크/타임아웃'
  if attempt<3:time.sleep(2**attempt)
 raise DataError(msg+' : 재시도 실패')

def safe_name(s):return re.sub(r'[^\w가-힣.-]+','_',s)[:90]
def stamp():return dt.datetime.now(dt.timezone.utc).isoformat()

class Job:
 def __init__(self,cfg):
  self.c=cfg;self.active_files=set();self.out=ROOT/'data';self.statefile=self.out/'progress.json'
  self.state=json.loads(self.statefile.read_text(encoding='utf-8')) if self.statefile.exists() else {}
  self.start=dt.date.fromisoformat(cfg['start']);self.end=min(dt.date.fromisoformat(cfg['end']) if cfg.get('end') else dt.date.today()-dt.timedelta(days=1),dt.date.today()-dt.timedelta(days=1))
  if self.start>self.end:raise ValueError('시작일이 종료일보다 늦습니다.')
 def rununit(self,key,path,fn):
  self.active_files.add(str(path.relative_to(self.out)))
  old=self.state.get(key,{})
  if old.get('status')=='ok' and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==old.get('sha256'):
   print('  건너뜀:',key,flush=True);return
  try:
   rows=fn()
   if not rows:raise DataError('자료없음: 정상 완료로 처리하지 않음. 기간/분류/지점 확인 필요.')
   if not isinstance(rows,list) or not all(isinstance(x,dict) for x in rows):raise DataError('응답 행 형식 오류')
   atomic_json(path,rows)
   self.state[key]={'status':'ok','rows':len(rows),'file':str(path.relative_to(self.out)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'collected_at':stamp()}
   print('  저장:',key,len(rows),'행',flush=True)
  except StopService as e:
   self.state[key]={'status':'error','message':str(e),'at':stamp()};atomic_json(self.statefile,self.state);raise
  except DataError as e:
   self.state[key]={'status':'error','message':str(e),'at':stamp()};print('  실패:',key,str(e),flush=True)
  atomic_json(self.statefile,self.state);time.sleep(0.35)
 def merged(self,folder,name):
  # 과거 다른 범위의 파일을 몰래 합치지 않음. 현재 실행에서 등록한 key만 사용.
  files={s['file'] for s in self.state.values() if s.get('status')=='ok' and s.get('file','').startswith(folder+'/') and s['file'] in self.active_files}
  rows=[]
  for p in sorted(files):
   f=self.out/p
   if f.exists():rows.extend(json.loads(f.read_text(encoding='utf-8')))
  if rows:csvout(self.out/(name+'.csv'),rows)
 def weather(self):
  key=self.c.get('data_go_kr_key','').strip()
  if not key:print('날씨: config.json의 data_go_kr_key 입력 필요');return
  key=unquote(key) if re.search(r'%[0-9a-fA-F]{2}',key) else key
  ids=self.c.get('weather_station_ids') or list(STATIONS)
  csvout(self.out/'weather_stations.csv',[{'station_id':i,'station_name':STATIONS.get(int(i),'사용자추가'),'scope':'66개 기본지점; 전체 ASOS 아님'} for i in ids])
  for station in ids:
   for year in range(self.start.year,self.end.year+1):
    a=max(self.start,dt.date(year,1,1));b=min(self.end,dt.date(year,12,31))
    tag=f'weather_{station}_{a:%Y%m%d}_{b:%Y%m%d}'
    def get(st=station,a=a,b=b):
     rows=[];page=1
     while True:
      data=fetch(KMA,{'serviceKey':key,'dataType':'JSON','dataCd':'ASOS','dateCd':'DAY','startDt':a.strftime('%Y%m%d'),'endDt':b.strftime('%Y%m%d'),'stnIds':str(st),'numOfRows':999,'pageNo':page})
      resp=data.get('response',{});h=resp.get('header',{});code=str(h.get('resultCode',''))
      if code!='00':
       if code in ('20','22','29','30','31'):raise StopService('날씨 API 인증/권한/호출량 제한. 코드 '+code)
       raise DataError('날씨 API 오류 코드 '+code)
      body=resp.get('body',{});total=int(body.get('totalCount',0));items=body.get('items') or {};batch=items.get('item',[]) if isinstance(items,dict) else []
      if isinstance(batch,dict):batch=[batch]
      if total and not batch:raise DataError('페이지 누락')
      for row in batch:
       if str(row.get('stnId'))!=str(st):raise DataError('지점 응답 불일치')
       row=dict(row);row['_source']='KMA_ASOS';row['_collected_at']=stamp();rows.append(row)
      if len(rows)>=total:break
      page+=1
     if len(rows)!=total:raise DataError('응답 totalCount 불일치')
     dates=[x.get('tm') for x in rows]
     if len(dates)!=len(set(dates)):raise DataError('지점 일자 중복')
     return rows
    self.rununit(tag,self.out/'weather'/f'{tag}.json',get)
  self.merged('weather','weather_daily')
  print('날씨 원자료의 빈 강수/일조 값은 0으로 바꾸지 않았습니다.')
 def fx(self):
  key=self.c.get('ecos_key','').strip()
  if not key:print('환율: config.json의 ecos_key 입력 필요 (KAMIS 키와 다름)');return
  # 통화 코드는 공식 메타데이터에서 이름으로 확인한다.
  meta=fetch(f'{ECOS}/StatisticItemList/{key}/json/kr/1/1000/731Y001')
  rows=meta.get('StatisticItemList',{}).get('row',[])
  if not rows:raise StopService('ECOS 환율 메타데이터 조회 실패. 키/권한 확인 필요.')
  atomic_json(self.out/'fx_items.json',rows)
  wanted=self.c.get('fx_name_contains',['미국달러','위안','일본엔'])
  selected=[r for r in rows if r.get('CYCLE')=='D' and ('매매기준율' in r.get('ITEM_NAME','') or r.get('ITEM_NAME')=='원/일본엔(100엔)') and any(s in r.get('ITEM_NAME','') for s in wanted)]
  if not selected:raise DataError('요청한 환율 항목 없음. data/fx_items.json 확인')
  for item in selected:
   for year in range(self.start.year,self.end.year+1):
    a=max(self.start,dt.date(year,1,1));b=min(self.end,dt.date(year,12,31));code=item['ITEM_CODE']
    tag=f'fx_{code}_{a:%Y%m%d}_{b:%Y%m%d}'
    def get(code=code,a=a,b=b):
     result=[];first=1
     while True:
      data=fetch(f'{ECOS}/StatisticSearch/{key}/json/kr/{first}/{first+999}/731Y001/D/{a:%Y%m%d}/{b:%Y%m%d}/{code}')
      block=data.get('StatisticSearch')
      if not block:
       err=data.get('RESULT',{}).get('CODE','unknown')
       if err in ('INFO-200',):return []
       raise StopService('ECOS 응답 오류 '+err)
      result.extend(block.get('row',[]));total=int(block['list_total_count'])
      if len(result)>=total:break
      if not block.get('row'):raise DataError('환율 페이지 누락')
      first+=1000
     if len(result)!=total:raise DataError('환율 건수 불일치')
     return result
    self.rununit(tag,self.out/'fx'/f'{tag}.json',get)
  self.merged('fx','exchange_daily')
 def calendar(self):
  try:import holidays
  except ImportError:
   print('명절 달력: py -m pip install holidays 실행 필요. 명절을 누락한 달력을 만들지 않습니다.');return
  # 민간 라이브러리 생성값. 공식 공휴일과 최종 대조 필요.
  years=range(self.start.year,self.end.year+2);h=holidays.KR(years=years,language='ko')
  holiday_dates=sorted(h);fest=[d for d in holiday_dates if any(k in h[d] for k in ['설날','추석','Seollal','Chuseok'])]
  rows=[];d=self.start
  while d<=self.end:
   future=[(x-d).days for x in fest if 0<=(x-d).days<=60]
   rows.append({'date':d.isoformat(),'weekday':d.weekday(),'month':d.month,'is_weekend':int(d.weekday()>=5),'is_holiday':int(d in h),'holiday_name':h.get(d,''),'days_to_lunar_festival_within60':min(future) if future else '', 'festival_within7':int(any(0<=x<=7 for x in future)),'source':'python-holidays KR; 공식 달력 대조 필요','library_version':holidays.__version__})
   d+=dt.timedelta(days=1)
  csvout(self.out/'calendar_daily.csv',rows);print('달력:',len(rows),'행 저장. 휴장일과 공휴일은 다릅니다.')
 def search(self):
  key=self.c.get('kosis_key','').strip()
  if not key:print('KOSIS 검색: config.json의 kosis_key 입력 필요');return
  allrows=[];status=[]
  for term in QUERIES:
   data=fetch('https://kosis.kr/openapi/statisticsSearch.do',{'method':'getList','apiKey':key,'searchNm':term,'sort':'RANK','startCount':1,'resultCount':20,'format':'json','jsonVD':'Y'})
   errors=[data] if isinstance(data,dict) else [r for r in data if isinstance(r,dict) and 'err' in r] if isinstance(data,list) else []
   if errors:
    code=str(errors[0].get('err','unknown'))
    if code=='30':
     print('  검색결과 없음:',term,flush=True);status.append({'query':term,'status':'no_data','code':code});continue
    raise StopService('KOSIS 오류 코드 '+code+' : 인증/승인/호출제한 확인 필요')
   if not isinstance(data,list):raise DataError('KOSIS 검색 응답 형식 오류')
   valid=[r for r in data if isinstance(r,dict) and r.get('TBL_ID')]
   for row in valid:allrows.append({'search_term':term,**row})
   status.append({'query':term,'status':'ok' if valid else 'no_data','rows':len(valid)})
   print('  통계표 후보:',term,len(valid),flush=True);time.sleep(.4)
  csvout(self.out/'kosis_table_candidates.csv',allrows,fields=list(dict.fromkeys(['search_term','ORG_ID','ORG_NM','TBL_ID','TBL_NM','STAT_NM','STRT_PRD_DE','END_PRD_DE','LINK_URL']+[k for r in allrows for k in r])))
  atomic_json(self.out/'kosis_search_status.json',status)
  print('후보 목록 저장:',len(allrows),'건. 수치 자료는 URL 지정 후 kosis 명령으로 받습니다.')
 def kosis(self):
  key=self.c.get('kosis_key','').strip();p=ROOT/'kosis_urls.txt'
  urls=[line.strip() for line in p.read_text(encoding='utf-8-sig').splitlines() if line.strip() and not line.lstrip().startswith('#')]
  if not urls:print('KOSIS: kosis_urls.txt에 공식 URL 생성 결과를 한 줄에 하나씩 넣어주세요. 아직 통계 수치를 받은 상태가 아닙니다.');return
  for i,url in enumerate(urls,1):
   u=urlsplit(url)
   if u.scheme!='https' or u.hostname!='kosis.kr' or u.path not in ('/openapi/Param/statisticsParameterData.do','/openapi/statisticsData.do'):raise DataError('공식 KOSIS JSON 통계자료 URL만 허용합니다.')
   params=dict(parse_qsl(u.query,keep_blank_values=True))
   if key:params['apiKey']=key
   if not params.get('apiKey'):raise StopService('KOSIS 키 필요')
   if params.get('prdSe') not in ('Y','M'):raise DataError('이 수집기는 연/월 통계만 지원합니다.')
   params.update(format='json',jsonVD='Y');params.pop('newEstPrdCnt',None)
   for year in range(self.start.year,self.end.year+1):
    q=dict(params);monthly=q['prdSe']=='M'
    q['startPrdDe']=max(self.start.strftime('%Y%m') if monthly else str(self.start.year),str(year)+'01' if monthly else str(year))
    q['endPrdDe']=min(self.end.strftime('%Y%m') if monthly else str(self.end.year),str(year)+'12' if monthly else str(year))
    ident={k:v for k,v in q.items() if k!='apiKey'};digest=hashlib.sha256(json.dumps(ident,sort_keys=True).encode()).hexdigest()[:12]
    tag=f'kosis_{safe_name(params.get("tblId","registered"))}_{year}_{digest}'
    def get(q=q):
     data=fetch('https://kosis.kr'+u.path,q)
     if not isinstance(data,list):raise DataError('KOSIS API 오류 또는 응답 형식 오류')
     if any(not isinstance(r,dict) or 'DT' not in r or 'PRD_DE' not in r for r in data):raise DataError('KOSIS 오류/잘못된 표. 분류·항목 범위를 줄여 URL 재생성 필요.')
     return data
    self.rununit(tag,self.out/'kosis'/f'{tag}.json',get)
  self.merged('kosis','kosis_long')
 def summary(self):
  counts={}
  for x in self.state.values():counts[x['status']]=counts.get(x['status'],0)+1
  atomic_json(self.out/'run_summary.json',{'updated_at':stamp(),'requested_start':str(self.start),'requested_end':str(self.end),'units':counts,'note':'ok는 API 건별 저장 성공. 전체 품목/지점/기간의 완전성이나 예측 활용 가능성을 보증하지 않음.'})
  print('상태:',counts,'| data/progress.json 확인')

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['all','weather','fx','calendar','search','kosis']);a=p.parse_args()
 c=json.loads(CFG.read_text(encoding='utf-8-sig'));j=Job(c)
 # KOSIS 우선, 날씨는 마지막
 modes=['search','kosis','fx','calendar','weather'] if a.mode=='all' else [a.mode]
 for mode in modes:
  print('\n===',mode,'시작 ===',flush=True)
  try:getattr(j,mode)()
  except (DataError,ValueError) as e:print('중지:',mode,str(e),flush=True)
  finally:j.summary()
 print('\n실행 종료. 누락·실패·미설정은 완료가 아닙니다. 출력 메시지와 요약을 확인하세요.')
if __name__=='__main__':
 try:main()
 except KeyboardInterrupt:print('\n사용자 중단. 같은 명령으로 다시 실행하면 저장 완료 파일은 건너뜁니다.')
 except (ValueError,OSError) as e:print('설정/파일 오류:',type(e).__name__,'config.json과 읽기/쓰기 권한 확인');sys.exit(1)
