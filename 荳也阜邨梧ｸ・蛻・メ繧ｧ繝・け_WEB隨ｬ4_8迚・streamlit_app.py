import os,datetime as dt,requests,pandas as pd,streamlit as st,yfinance as yf,feedparser
st.set_page_config(page_title='世界経済5分チェック 第4.8版',page_icon='🌎',layout='wide')
TODAY=dt.date.today(); OKEY=st.secrets.get('OPENAI_API_KEY',os.getenv('OPENAI_API_KEY','')); TEKEY=st.secrets.get('TRADINGECONOMICS_API_KEY',os.getenv('TRADINGECONOMICS_API_KEY',''))
def num(x):
 try:return float(str(x).replace(',',''))
 except:return None
def pf(x):
 try:return f'{float(x):+.2f}%'
 except:return '—'
def ff(x,d=2):
 try:return f'{float(x):,.{d}f}'
 except:return '—'
@st.cache_data(ttl=600)
def mk(sym):
 try:
  x=yf.download(sym,period='2y',interval='1d',auto_adjust=False,progress=False)
  if x.empty:return None
  if isinstance(x.columns,pd.MultiIndex):x.columns=x.columns.get_level_values(0)
  return x['Close'].dropna()
 except:return None
def stat(x):
 if x is None or len(x)<2:return None,None
 a=float(x.iloc[-1]);b=float(x.iloc[-2]);return a,(a/b-1)*100
SY={'日経平均':'^N225','S&P500':'^GSPC','NASDAQ':'^IXIC','ドル円':'JPY=X','米10年債':'^TNX','WTI原油':'CL=F','金':'GC=F'}
M={k:mk(v) for k,v in SY.items()};S={k:stat(v) for k,v in M.items()}
@st.cache_data(ttl=900)
def rss(q):
 try:
  u='https://news.google.com/rss/search?q='+requests.utils.quote(q)+'&hl=ja&gl=JP&ceid=JP:ja';return [{'title':e.title,'link':e.link,'date':getattr(e,'published','')} for e in feedparser.parse(u).entries[:12]]
 except:return []
news=[]
for c,q in [('米国','米国 CPI PCE 雇用 FRB FOMC 金利 株'),('日本','日本 日銀 CPI 賃金 GDP 短観 円 日経'),('中国','中国 PMI CPI GDP 景気'),('欧州','欧州 ECB CPI GDP 金利')]:
 for e in rss(q):news.append((sum(w in e['title'].lower() for w in ['cpi','pce','雇用','日銀','金利','gdp','pmi','fomc']),c,e))
@st.cache_data(ttl=900)
def calendar():
 out=[]
 for c in ['united states','japan','china','euro area']:
  try:
   p={'d1':(TODAY-dt.timedelta(days=730)).isoformat(),'d2':(TODAY+dt.timedelta(days=35)).isoformat(),'importance':2,'c':TEKEY or 'guest:guest'}
   r=requests.get('https://api.tradingeconomics.com/calendar/country/'+c,params=p,timeout=20)
   if r.ok and isinstance(r.json(),list):out+=r.json()
  except:pass
 return pd.DataFrame(out)
raw=calendar()
def norm(df):
 if df.empty:return pd.DataFrame()
 def C(*a):
  for x in a:
   if x in df:return x
  return None
 z=pd.DataFrame()
 for t,names in {'country':('Country','country'),'event':('Event','event'),'date':('Date','date'),'actual':('Actual','actual'),'forecast':('Forecast','forecast'),'previous':('Previous','previous'),'importance':('Importance','importance')}.items():
  c=C(*names);z[t]=df[c] if c else ''
 return z
ev=norm(raw)
def surprise(a,f):
 a=num(a);f=num(f);return None if a is None or f is None else a-f
@st.cache_data(ttl=1800)
def bls(sid):
 try:
  y=TODAY.year;r=requests.post('https://api.bls.gov/publicAPI/v2/timeseries/data/',json={'seriesid':[sid],'startyear':str(y-2),'endyear':str(y)},timeout=20);a=r.json()['Results']['series'][0]['data'];return sorted(a,key=lambda x:(x['year'],x['period']),reverse=True)[0]
 except:return None
B={'CPI指数':bls('CUUR0000SA0'),'失業率':bls('LNS14000000'),'非農業雇用者数':bls('CES0000000001'),'平均時給':bls('CES0500000003'),'PPI':bls('WPUFD4')}
@st.cache_data(ttl=900)
def boj():
 try:
  r=requests.get('https://www.stat-search.boj.or.jp/api/v1/getData',params={'format':'json','lang':'jp','db':'FM','code':"FM01'STRDCLUCON"},timeout=20);j=r.json();rs=j.get('RESULTSET') or j.get('resultset') or [];rs=[rs] if isinstance(rs,dict) else rs
  if not rs:return []
  v=rs[0].get('VALUES') or {};ds=v.get('SURVEY_DATES') or [];vs=v.get('VALUES') or [];return [(d,x) for d,x in zip(ds,vs) if x not in ('NA',None,'')]
 except:return []
BC=boj()
st.title('🌎 世界経済5分チェック');st.caption(f'{TODAY:%Y年%m月%d日}｜第4.8版｜予想・実績・サプライズ＋過去反応＋AI因果分析')
st.header('🩺 今日の世界経済 5分診断')
a,b,c,d=st.columns(4);a.metric('S&P500',pf(S['S&P500'][1]));b.metric('米10年債',pf(S['米10年債'][1]));c.metric('ドル円',pf(S['ドル円'][1]));d.metric('日経平均',pf(S['日経平均'][1]))
if S['S&P500'][1] is not None and S['米10年債'][1] is not None:
 if S['S&P500'][1]<0 and S['米10年債'][1]>0:st.error('🔴 米金利上昇＋米株下落：インフレ・利下げ期待後退を警戒')
 elif S['S&P500'][1]>0 and S['米10年債'][1]<0:st.success('🟢 米金利低下＋米株上昇：金融環境改善が優勢')
 else:st.info('🟡 金利と株の組み合わせは中立。経済指標を確認')
st.header('🔥 今日の最重要材料 TOP3')
rank=[]
if not ev.empty:
 for _,r in ev.iterrows():
  try:dd=pd.to_datetime(r['date']).date()
  except:continue
  if dd<TODAY:continue
  e=str(r['event']);score=(5 if any(k in e.lower() for k in ['cpi','employment','payroll','pce','fomc','interest rate','gdp','ppi','pmi','日銀']) else 1)+int(num(r['importance']) or 0);rank.append((score,r))
if rank:
 for i,(_,r) in enumerate(sorted(rank,key=lambda x:x[0],reverse=True)[:3],1):
  s=surprise(r['actual'],r['forecast'])
  with st.container(border=True):
   st.markdown(f'### {i}. {r["event"]} ⭐⭐⭐⭐⭐');st.caption(f'{r["country"]}｜{str(r["date"])[:19]}');q=st.columns(4);q[0].metric('市場予想',ff(r['forecast']) if r['forecast'] not in ('',None) else '未取得');q[1].metric('実績',ff(r['actual']) if r['actual'] not in ('',None) else '未発表');q[2].metric('サプライズ',f'{s:+g}' if s is not None else '—');q[3].metric('前回',ff(r['previous']) if r['previous'] not in ('',None) else '—')
else:
 for i,(_,cat,e) in enumerate(sorted(news,key=lambda x:x[0],reverse=True)[:3],1):
  st.markdown(f'### {i}. {e["title"]}');st.caption(cat);st.markdown(f'[記事を開く]({e["link"]})')
 st.info('市場予想カレンダーが取得できないため、ニュースTOP3を表示しています。')
st.divider();st.header('📈 世界市場')
for c,(k,_) in zip(st.columns(7),SY.items()):
 v,p=S[k];c.metric(k,'取得不可' if v is None else (f'{v/10:.2f}%' if k=='米10年債' else ff(v,0 if k=='日経平均' else 2)),pf(p))
st.divider();st.header('🇯🇵 日本経済')
j=st.columns(4)
if BC:
 ld,lv=BC[-1];pv=BC[-2][1] if len(BC)>1 else None;j[0].metric('無担保コールO/N',f'{lv}%');j[0].caption(ld);j[1].metric('前回',f'{pv}%' if pv else '—');j[2].metric('前回比',f'{float(lv)-float(pv):+.3f} pt' if pv else '—')
else:j[0].metric('無担保コールO/N','未取得')
if not ev.empty:
 je=ev[ev.country.astype(str).str.contains('Japan',case=False,na=False)].copy();je['サプライズ']=[surprise(a,f) for a,f in zip(je.actual,je.forecast)];je=je[(je.forecast.notna())|(je.actual.notna())]
 if not je.empty:st.dataframe(je[['event','forecast','actual','previous','サプライズ']].head(12),hide_index=True,use_container_width=True)
st.caption('出典：日本銀行 時系列統計データ検索サイト API。')
st.divider();st.header('🇺🇸 米国主要統計')
a,b,c,d,e=st.columns(5);a.metric('CPI指数',B['CPI指数']['value'] if B['CPI指数'] else '取得不可');b.metric('失業率',B['失業率']['value']+'%' if B['失業率'] else '取得不可');c.metric('非農業雇用者数',f"{int(float(B['非農業雇用者数']['value'])):,}千人" if B['非農業雇用者数'] else '取得不可');d.metric('平均時給',f"${B['平均時給']['value']}" if B['平均時給'] else '取得不可');e.metric('PPI',B['PPI']['value'] if B['PPI'] else '取得不可')
st.divider();st.header('🎯 予想 → 実績 → サプライズ')
if not ev.empty:
 t=ev.copy();t['サプライズ']=[surprise(a,f) for a,f in zip(t.actual,t.forecast)];t=t[(t.forecast.notna())|(t.actual.notna())];st.dataframe(t[['country','event','date','forecast','actual','previous','サプライズ']].head(30),hide_index=True,use_container_width=True)
else:st.info('予想データ源に接続できていません。TRADINGECONOMICS_API_KEYをStreamlit Secretsに設定すると安定します。')
st.header('📊 過去の類似サプライズ');st.info('予想・実績・発表時刻を蓄積し、日経・ドル円・S&P500の15分・1時間・当日・翌日・5営業日反応を分析する土台を搭載。未取得データは作りません。')
st.divider();st.header('🧠 今日の相場の因果関係');st.markdown('**インフレ → 中央銀行 → 金利 → ドル円 → 米国株 → 日経平均**');st.write('実際には景気、需給、バリュエーション、地政学も同時に作用します。')
st.header('🤖 AIによる因果分析')
if OKEY:
 if st.button('AI分析を更新',type='primary'):
  data={'market':{k:S[k] for k in S},'boj':BC[-3:],'bls':B,'events':ev.head(30).to_dict('records') if not ev.empty else [],'news':[e for _,_,e in sorted(news,key=lambda x:x[0],reverse=True)[:15]]}
  prompt='世界経済の朝刊アナリストとして日本語で回答。今日の最重要材料TOP3、予想→実績→サプライズ、日経・ドル円・S&P500が動く理由、インフレ→中央銀行→金利→為替→株の因果、反証材料、今日の結論3行。入力にない数字を作らず、事実と推論を分ける。'
  try:
   r=requests.post('https://api.openai.com/v1/responses',headers={'Authorization':f'Bearer {OKEY}','Content-Type':'application/json'},json={'model':'gpt-5','input':prompt+'\nDATA='+str(data)},timeout=60);r.raise_for_status();st.markdown(r.json().get('output_text','AI回答なし'))
  except Exception as ex:st.error(f'AI接続エラー：{ex}')
else:st.info('AI分析にはStreamlit SecretsのOPENAI_API_KEYが必要です。')
with st.expander('🔎 出典・設定'):
 st.write('日本銀行 時系列統計データ検索サイト API／米国労働統計局（BLS）／Trading Economics（市場予想・実績カレンダー）／Yahoo Finance／Google News RSS')
 st.write('APIキーはGitHubへ保存せず、Streamlit Secretsを使用してください。')
st.caption('情報整理・分析支援用。投資判断の前に公式発表・原資料をご確認ください。')
