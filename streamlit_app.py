import os, re, datetime as dt, requests, pandas as pd, streamlit as st, yfinance as yf, feedparser

st.set_page_config(page_title="世界経済5分チェック", page_icon="🌎", layout="wide")
st.title("🌎 世界経済5分チェック")
st.caption(f"{dt.date.today():%Y年%m月%d日}｜朝5分で「何が相場を動かすか」を確認")

OPENAI_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY",""))
OPENAI_MODEL = st.secrets.get("OPENAI_MODEL", os.getenv("OPENAI_MODEL","gpt-5"))

@st.cache_data(ttl=600)
def market(sym):
    try:
        x=yf.download(sym,period="6mo",interval="1d",auto_adjust=False,progress=False)
        if x.empty: return None
        if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(0)
        return x["Close"].dropna()
    except Exception: return None

symbols={"日経平均":"^N225","S&P500":"^GSPC","NASDAQ":"^IXIC","ドル円":"JPY=X","米10年債":"^TNX","WTI":"CL=F","金":"GC=F"}
data={k:market(v) for k,v in symbols.items()}

def metric(s):
    if s is None or len(s)<2:return None,None
    a=float(s.iloc[-1]); b=float(s.iloc[-2])
    return a,(a/b-1)*100

st.subheader("📈 世界市場")
cols=st.columns(7)
for c,(name,_) in zip(cols,symbols.items()):
    with c:
        v,p=metric(data[name])
        if v is not None: st.metric(name,f"{v:,.2f}",f"{p:+.2f}%")

@st.cache_data(ttl=1800)
def bls(series_ids):
    url="https://api.bls.gov/publicAPI/v2/timeseries/data/"
    try:
        y=dt.date.today().year
        r=requests.post(url,json={"seriesid":series_ids,"startyear":str(y-2),"endyear":str(y)},timeout=20)
        r.raise_for_status()
        return r.json().get("Results",{}).get("series",[])
    except Exception:return []

def latest_bls(series_id):
    rows=bls([series_id])
    if not rows or not rows[0].get("data"):return None
    d=sorted(rows[0]["data"],key=lambda x:(x["year"],x["period"]),reverse=True)
    return d[0]

cpi=latest_bls("CUUR0000SA0")
unemp=latest_bls("LNS14000000")
payroll=latest_bls("CES0000000001")

st.divider()
st.subheader("🇺🇸 米国の公的経済データ")
a,b,c=st.columns(3)
with a: st.metric("CPI",cpi.get("value")+"%" if cpi else "取得不可")
with b: st.metric("失業率",unemp.get("value")+"%" if unemp else "取得不可")
with c: st.metric("非農業部門雇用者数",payroll.get("value") if payroll else "取得不可")

@st.cache_data(ttl=900)
def news(q,n=10):
    try:
        u="https://news.google.com/rss/search?q="+requests.utils.quote(q)+"&hl=en-US&gl=US&ceid=US:en"
        f=feedparser.parse(u)
        return [{"title":e.title,"link":e.link,"date":getattr(e,"published","")} for e in f.entries[:n]]
    except Exception:return []

def extract_expectation(title):
    pats=[
        r"(?:expected|forecast|economists expect|estimate(?:d)?)\s*(?:at|to be|of)?\s*(-?\d+(?:\.\d+)?)\s*%",
        r"(?:vs\.?|versus)\s*(?:forecast|estimate|expected)\s*(-?\d+(?:\.\d+)?)\s*%"
    ]
    for p in pats:
        m=re.search(p,title,re.I)
        if m:
            try:return float(m.group(1))
            except Exception:pass
    return None

@st.cache_data(ttl=900)
def expectation_news():
    qs=[
        "US CPI expected forecast economists",
        "US jobs report expected forecast payroll unemployment",
        "US PCE inflation expected forecast",
        "Japan CPI expected forecast",
        "Japan GDP expected forecast",
        "China PMI expected forecast",
        "Eurozone CPI expected forecast"
    ]
    out=[]
    for q in qs:
        for e in news(q,6):
            x=extract_expectation(e["title"])
            if x is not None: out.append({**e,"expectation":x,"query":q})
    return out

expectations=expectation_news()

st.subheader("🎯 予想・実績・サプライズ")
st.info("無料構成では、有料コンセンサスAPIを使わず、公式発表の実績値とニュース見出しから明示的に検出できる市場予想だけを表示します。予想が検出できない場合は推測しません。")
if expectations:
    st.dataframe(pd.DataFrame(expectations)[["date","title","expectation","link"]].rename(columns={"date":"日時","title":"ニュース","expectation":"検出された予想値","link":"リンク"}),hide_index=True,use_container_width=True)
else:
    st.warning("現在、見出しから信頼できる予想値を検出できませんでした。")

st.divider()
st.subheader("🧠 今日の因果関係")
sp=metric(data["S&P500"])[1]; fx=metric(data["ドル円"])[1]; y10=metric(data["米10年債"])[1]; nk=metric(data["日経平均"])[1]
if sp is not None and y10 is not None:
    if sp<0 and y10>0: st.error("米金利上昇＋米株下落 → 金融引き締め懸念を最優先で確認。")
    elif sp>0 and y10<0: st.success("米金利低下＋米株上昇 → 利下げ期待・金融環境改善が支援材料の可能性。")
    else: st.info("米金利と米株の方向が不一致。経済指標とニュースを確認。")
if fx is not None and nk is not None: st.write(f"ドル円 {fx:+.2f}%、日経 {nk:+.2f}%。")

st.subheader("🔥 今日の最重要材料 TOP3")
items=[]
for e in news("US CPI jobs Fed inflation interest rates stocks dollar Japan Nikkei China Europe",12):
    title=e["title"].lower()
    score=sum(word in title for word in ["cpi","inflation","jobs","payroll","fed","rate","tariff","gdp","boj","nikkei","china"])
    items.append((score,e))
for i,(score,e) in enumerate(sorted(items,key=lambda x:x[0],reverse=True)[:3],1):
    st.markdown(f"### {i}. {e['title']}")
    st.caption(e["date"])
    st.markdown(f"[ニュースを開く]({e['link']})")

st.divider()
st.subheader("🤖 AIによる因果分析")
if OPENAI_KEY:
    if st.button("AI分析を更新",type="primary"):
        payload={"market":{k:metric(v) for k,v in data.items()},"official_us":{"cpi":cpi,"unemployment":unemp,"payroll":payroll},"detected_expectations":expectations[:15]}
        prompt=("世界経済の朝刊アナリストとして日本語で分析。①最重要材料TOP3 ②予想・実績・サプライズ（予想なしは推測禁止） "
        "③インフレ→中央銀行→米金利→ドル円→米株→日経の因果チェーン ④短期注目方向 ⑤反証材料 ⑥今日最も見る数字。"
        "事実と推論を分ける。DATA="+str(payload))
        try:
            r=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json={"model":OPENAI_MODEL,"input":prompt},timeout=45)
            r.raise_for_status(); j=r.json()
            ans=j.get("output_text") or "\n".join(c.get("text","") for o in j.get("output",[]) for c in o.get("content",[]) if isinstance(c,dict))
            st.markdown(ans or "AIから回答が返りませんでした。")
        except Exception as e: st.error(f"AI接続エラー: {e}")
else: st.info("AI分析を使う場合は Streamlit Secrets に OPENAI_API_KEY を設定してください。")

st.divider()
st.subheader("📰 経済ニュース")
for tab,q in zip(st.tabs(["🇺🇸米国","🇯🇵日本","🇨🇳中国・🇪🇺欧州"]),["US CPI PCE jobs Fed interest rates stocks","Japan CPI BOJ wages yen Nikkei","China PMI CPI PPI Europe ECB inflation"]):
    with tab:
        for e in news(q,8): st.markdown(f"**{e['title']}**  \n{e['date']}  \n[{e['link']}]({e['link']})")

with st.sidebar:
    st.header("⚙️ データ構成")
    st.write("市場：Yahoo Finance")
    st.write("米国実績：BLS Public Data API（登録不要）")
    st.write("ニュース：Google News RSS")
    st.write("AI：OpenAI API（任意）")
    st.caption("無料構成を優先し、取得できない予想値は推測しません。")
st.caption("情報整理・分析支援用。投資判断は公式発表等で確認してください。")
