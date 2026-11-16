"""선별한 농산물 관련 14개 통계표 수집(2026-10-22 DT_1ET0026 서류생산량(생서) 추가). 기존 config.json의 kosis_key 사용.
분류/항목 메타데이터를 먼저 받고, 연/분기/월 단위로 쪼개 저장한다.
수집 실패는 완료로 처리하지 않는다. 서로 다른 표를 임의로 결합하지 않는다.
"""
import argparse, csv, datetime as dt, hashlib, itertools, json, os, re, time
from pathlib import Path
from urllib.parse import urlencode
import collect_factors as core
ROOT=Path(__file__).resolve().parent
TABLES=[
 ('101','DT_1ET0291','채소생산량(조미채소)','Y',1980,2026),
 ('101','DT_1ET0028','채소생산량(엽채류)','Y',1980,2025),
 ('101','DT_1ET0029','채소생산량(근채류)','Y',1980,2025),
 ('101','DT_1ET0027','채소생산량(과채류)','Y',1980,2024),
 ('101','DT_1ET0021','식량작물 생산량(정곡)','Y',1998,2026),
 ('101','DT_1ET0026','서류생산량(생서) - 감자·고구마 작형별(2026-10-22 추가)','Y',1991,2026),
 ('101','DT_1ET0292','과실생산량(성과수+미과수)','Y',1980,2025),
 ('101','DT_1ET0013','노지 채소 재배면적','Y',1975,2026),
 ('101','DT_1ET0012','노지 식량작물 재배면적','Y',1975,2026),
 ('101','DT_1ET0014','노지 과수 재배면적','Y',1975,2026),
 ('101','DT_1ET0017','시설작물 재배면적','Y',1979,2026),
 ('101','DT_1J62','농가구입가격지수(2020=100,분기)','Q',2005,2026),
 ('318','TX_31802_A000','주유소 제품별 평균 판매가격','M',2000,2026),
 ('301','DT_404Y016','생산자물가지수(품목별)','M',1965,2026),
 ('114','DT_114_015_B142','유지작물 생산량(참깨·들깨·땅콩 등, 농식품부) - 10-28 추가','Y',1998,2026),
 ('114','DT_114_2012_S0095','특용작물 생산현황(버섯 등, 농식품부) - 10-28 추가','Y',1998,2026),
 ('101','DT_1ET0293','특용작물생산량(유채·참깨·들깨·땅콩 면적·단수·생산, 통계청 농작물생산조사, 시도) - 10-28 우회','Y',1980,2025),
]
class APIError(core.DataError):
 def __init__(self,code):self.code=str(code);super().__init__('KOSIS 오류 코드 '+self.code)

def api(key,url,params):
 q=dict(params,apiKey=key,format='json',jsonVD='Y',content='json')
 data=core.fetch(url,q)
 err=next((r for r in data if isinstance(r,dict) and 'err' in r),None) if isinstance(data,list) else data if isinstance(data,dict) and 'err' in data else None
 if err:raise APIError(err['err'])
 if not isinstance(data,list) or not all(isinstance(x,dict) for x in data):raise core.DataError('예상하지 못한 KOSIS 응답 형식')
 return [{str(k).upper():v for k,v in x.items()} for x in data]

def axes_from_meta(rows):
 # OBJ_ID는 축 이름이며 순서가 아니다. KOSIS가 제공한 OBJ_ID_SN을 사용.
 groups={};orders={}
 for r in rows:
  obj=str(r.get('OBJ_ID','')).upper();code=str(r.get('ITM_ID','')).strip()
  if not obj or not code:continue
  groups.setdefault(obj,[])
  if code not in groups[obj]:groups[obj].append(code)
  sn=r.get('OBJ_ID_SN')
  if obj not in ('ITEM','ITM') and sn is not None and str(sn).strip():
   try:number=int(str(sn).strip())
   except ValueError:raise core.DataError('분류축 순번 형식 오류: '+obj)
   if not 1<=number<=8:raise core.DataError('분류축 순번 범위 오류: '+obj)
   if obj in orders and orders[obj]!=number:raise core.DataError('분류축 순번 불일치: '+obj)
   orders[obj]=number
 item=next((x for x in ('ITEM','ITM') if x in groups),None)
 if item is None:raise core.DataError('항목축(ITEM/ITM)을 식별하지 못함. meta 파일 확인 필요')
 dims={}
 for obj,vals in groups.items():
  if obj==item:continue
  if obj in orders:number=orders[obj]
  else:raise core.DataError('분류축 순번(OBJ_ID_SN) 없음: '+obj)
  if number in dims:raise core.DataError('분류축 순번 중복: '+str(number))
  dims[number]=vals
 if not dims or sorted(dims)!=list(range(1,len(dims)+1)):raise core.DataError('분류축 순서를 확정할 수 없음')
 return groups[item],dims

def blocks(items,dims,maxcells=10000,maxquery=1500):
 # 표의 명시적 항목/분류 코드만 요청. 전체 분류의 조합을 셀수 상한 이하로 분할.
 axes=[('itmId',items)]+[(f'objL{k}',v) for k,v in sorted(dims.items())]
 def rec(xs):
  count=1
  for _,v in xs:count*=len(v)
  part={k:'+'.join(v) for k,v in xs}
  # 항목 코드가 길면 셀 수가 적어도 HTTP 414 발생. URL 인코딩 후 길이로 분할.
  if count<=maxcells and len(urlencode(part))<=maxquery:yield part;return
  candidates=[i for i in range(len(xs)) if len(xs[i][1])>1]
  if not candidates:raise core.DataError('단일 분류 코드가 요청 길이 제한 초과')
  i=max(candidates,key=lambda i:len(urlencode({xs[i][0]:'+'.join(xs[i][1])})));name,vals=xs[i]
  if len(vals)<2:raise core.DataError('분류 분할 불가')
  mid=len(vals)//2
  for part in (vals[:mid],vals[mid:]):yield from rec(xs[:i]+[(name,part)]+xs[i+1:])
 yield from rec(axes)

def periods(start,end,cycle,first,last):
 for y in range(max(start.year,first),min(end.year,last)+1):
  if cycle=='Y':yield str(y);continue
  for n in range(1,13 if cycle=='M' else 5):
   month=n if cycle=='M' else (n-1)*3+1
   a=dt.date(y,month,1)
   if a>end:continue
   lastmonth=month if cycle=='M' else month+2
   import calendar
   b=dt.date(y,lastmonth,calendar.monthrange(y,lastmonth)[1])
   if b<start:continue
   yield f'{y}{n:02d}'

def write_table_csv(folder,outfile):
 files=sorted(folder.glob('*.json'));fields=[]
 for p in files:
  for r in json.loads(p.read_text(encoding='utf-8')):
   for k in r:
    if k not in fields:fields.append(k)
 if not fields:return
 tmp=outfile.with_suffix('.tmp')
 with tmp.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();seen=set()
  for p in files:
   for r in json.loads(p.read_text(encoding='utf-8')):
    ident=tuple(str(r.get(k,'')) for k in ['ORG_ID','TBL_ID','PRD_SE','PRD_DE','ITM_ID']+[f'C{i}' for i in range(1,9)])
    if ident in seen:continue
    seen.add(ident);w.writerow(r)
 os.replace(tmp,outfile)


def main():
 arg=argparse.ArgumentParser();arg.add_argument('--only',help='특정 tblId만 다시 실행');arg.add_argument('--start',help='시작일 덮어쓰기 예: 1998-01-01 (config.json은 그대로)');a=arg.parse_args()
 cfg=json.loads((ROOT/'config.json').read_text(encoding='utf-8-sig')) if (ROOT/'config.json').exists() else {};key=os.getenv('KOSIS_API_KEY','').strip() or cfg.get('kosis_key','').strip()   # v4: 키는 수집기 .env 의 KOSIS_API_KEY
 if not key:print('.env 에 KOSIS_API_KEY= 를 넣으세요 (kosis.kr 공유서비스 OpenAPI 인증키)');raise SystemExit(2)
 start=dt.date.fromisoformat(a.start or cfg.get('start','2015-01-01'));end=dt.date.fromisoformat(cfg['end']) if cfg.get('end') else dt.date.today()-dt.timedelta(days=1)
 out=Path(os.getenv('KOSIS_OUT') or ROOT/'data'/'kosis_auto');out.mkdir(parents=True,exist_ok=True)
 statusfile=out/'progress.json';state=json.loads(statusfile.read_text(encoding='utf-8')) if statusfile.exists() else {}
 tables=TABLES if not a.only else [t for t in TABLES if t[1]==a.only]
 if not tables:raise core.DataError('등록되지 않은 통계표 ID')
 report=[]
 for idx,(org,tbl,name,cycle,first,last) in enumerate(tables,1):
  print(f'\n[{idx}/{len(tables)}] {name} ({tbl})',flush=True)
  td=out/tbl;td.mkdir(exist_ok=True);rawdir=td/'raw';rawdir.mkdir(exist_ok=True)
  counts={'saved':0,'skipped':0,'no_data':0,'failed':0};table_error=''
  try:
   # 분류 메타데이터 자체가 없는 표는 임의 가정으로 수집하지 않는다.
   m=api(key,'https://kosis.kr/openapi/statisticsData.do',{'method':'getMeta','type':'ITM','orgId':org,'tblId':tbl})
   core.atomic_json(td/'meta_items.json',m)
   items,dims=axes_from_meta(m)
   parts=list(blocks(items,dims));print('항목',len(items),'개 / 분류축',len(dims),'개 / 시점당 분할',len(parts),'회',flush=True)
   for period in periods(start,end,cycle,first,last):
    for part in parts:
     identity=dict(part,orgId=org,tblId=tbl,prdSe=cycle,startPrdDe=period,endPrdDe=period)
     digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()[:16]
     unit=f'{tbl}_{period}_{digest}';path=rawdir/(unit+'.json');old=state.get(unit,{})
     if old.get('status')=='ok' and path.exists() and hashlib.sha256(path.read_bytes()).hexdigest()==old.get('sha256'):
      counts['skipped']+=1;continue
     try:
      rows=api(key,'https://kosis.kr/openapi/Param/statisticsParameterData.do',dict(identity,method='getList'))
      if not rows:raise APIError('30')
      if any('DT' not in r or r.get('TBL_ID')!=tbl or r.get('PRD_DE')!=period for r in rows):raise core.DataError('자료의 표/시점/값 불일치')
      # 공개 응답에서 관측되지 않은 분류 조합은 만들어 채우지 않는다.
      core.atomic_json(path,rows)
      state[unit]={'status':'ok','rows':len(rows),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'at':core.stamp()}
      counts['saved']+=1;print('  저장',period,len(rows),'행',flush=True)
     except APIError as e:
      if e.code in ('10','11','12','13'):raise
      label='no_data' if e.code=='30' else 'failed';counts[label]+=1;state[unit]={'status':label,'code':e.code,'at':core.stamp()};print(' ',period,label,'코드',e.code,flush=True)
     except core.DataError as e:
      counts['failed']+=1;state[unit]={'status':'failed','message':str(e),'at':core.stamp()};print('  실패',period,str(e),flush=True)
     core.atomic_json(statusfile,state);time.sleep(.4)
  except (core.DataError,ValueError) as e:
   table_error=str(e);print('  이 표 중지:',table_error,flush=True)
  finally:
   write_table_csv(rawdir,td/(tbl+'.csv'))
   report.append({'table_id':tbl,'table_name':name,'cycle':cycle,**counts,'table_error':table_error,'note':'no_data·failed·table_error는 미완료/검토 대상. saved/skipped는 요청 단위 수.'})
   core.csvout(out/'수집결과.csv',report)
 print('\n종료. data/kosis_auto/수집결과.csv에서 실패·자료없음 확인. 전체 수집 성공을 뜻하지 않습니다.')
if __name__=='__main__':
 try:main()
 except KeyboardInterrupt:print('\n중단됨. 같은 명령으로 이어받기 가능.')
 except (core.DataError,ValueError,OSError) as e:print('오류:',type(e).__name__,'설정·응답·파일 확인 필요.')
