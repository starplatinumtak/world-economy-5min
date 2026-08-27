import os, datetime as dt, requests, pandas as pd, streamlit as st, yfinance as yf, feedparser

st.set_page_config(page_title="世界経済5分チェック", page_icon="🌎", layout="wide")
st.title("🌎 世界経済5分チェック")
st.caption(f"{dt.date.today():%Y年%m月%d日}｜世界経済・市場・ニュースを一画面で確認")

TE_KEY=st.secrets.get("TRADINGECONOMICS_API_KEY", os.getenv("TRADINGECONOMICS_API_KEY",""))
OPENAI_KEY=st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY",""))
OPENAI_MODEL=st.secrets.get("OPENAI_MODEL", os.getenv("OPENAI_MODEL","gpt-5"))

@st.cache_data(ttl=600)
def market(sym):
    try:
        x=yf.download(sym,period="5d",interval="1d",auto_adjust=False,progress=False)
        if x.empty:return None
        if isinstance(x.columns,pd.MultiIndex): x.columns=x.columns.get_level_values(0)
        return x["Close"].dropna()
    except:return None

symbols={"日経平均":"^N225","S&P500":"^GSPC","NASDAQ":"^IXIC","ドル円":"JPY=X","米10年債":"^TNX","WTI":"CL=F","金":"GC=F"}
data={k:market(v) for k,v in symbols.items()}

def metric(s):
    if s is None or len(s)<2:return None,None
    a=float(s.iloc[-1]); b=float(s.iloc[-2])
    return a,(a/b-1)*100

@st.cache_data(ttl=900)
def te_calendar(country="United States"):
    if not TE_KEY:return pd.DataFrame()
    try:
        r=requests.get(f"https://api.tradingeconomics.com/calendar/country/{country}",
          params={"c":TE_KEY,"importance":2},timeout=20)
        r.raise_for_status()
        return pd.DataFrame(r.json())
    except:return pd.DataFrame()

def normalize(df):
    if df.empty:return df
    mp={"Date":"date","Country":"country","Category":"indicator","Event":"event",
        "Actual":"actual","Forecast":"forecast","Previous":"previous","Importance":"importance"}
    df=df.rename(columns={k:v for k,v in mp.items() if k in df.columns})
    for c in ["actual","forecast","previous"]:
        if c in df.columns: df[c]=pd.to_numeric(df[c],errors="coerce")
    if "date" in df.columns: df["date"]=pd.to_datetime(df["date"],errors="coerce")
    return df

@st.cache_data(ttl=900)
def news(q,n=7):
    try:
        u="https://news.google.com/rss/search?q="+requests.utils.quote(q)+"&hl=ja&gl=JP&ceid=JP:ja"
        f=feedparser.parse(u)
        return [{"title":e.title,"link":e.link,"date":getattr(e,"published","")} for e in f.entries[:n]]
    except:return []

st.subheader("📈 世界市場")
cols=st.columns(7)
for c,(name,_) in zip(cols,symbols.items()):
    with c:
        v,p=metric(data[name])
        if v is not None: st.metric(name,f"{v:,.2f}",f"{p:+.2f}%")

st.divider()
st.subheader("🔥 今日の最重要材料 TOP3")
cal=normalize(te_calendar())
today_events=pd.DataFrame()
if not cal.empty and "date" in cal.columns:
    today_events=cal[cal["date"].dt.date==dt.date.today()].copy()
    if "actual" in today_events and "forecast" in today_events:
        today_events["surprise"]=today_events["actual"]-today_events["forecast"]
        today_events["score"]=today_events["surprise"].abs()
        today_events=today_events.sort_values("score",ascending=False)

if not TE_KEY:
    st.warning("本物の市場予想値を使うには、Streamlit Secretsへ TRADINGECONOMICS_API_KEY を設定してください。")
elif today_events.empty:
    st.info("本日の米国重要指標は見つかりませんでした。")
else:
    for i,(_,e) in enumerate(today_events.head(3).iterrows(),1):
        s=e.get("surprise")
        verdict="予想上振れ" if pd.notna(s) and s>0 else ("予想下振れ" if pd.notna(s) and s<0 else "予想通り")
        st.markdown(f"### {i}. {e.get('indicator',e.get('event','重要指標'))} — {verdict}")
        if pd.notna(s):
            st.write(f"前回 {e.get('previous','-')} → 予想 {e.get('forecast','-')} → 実績 {e.get('actual','-')} → サプライズ {s:+.2f}")
        else: st.write("実績発表前です。")

st.subheader("🧠 今日の因果関係")
sp=metric(data["S&P500"])[1]; fx=metric(data["ドル円"])[1]; y10=metric(data["米10年債"])[1]; nk=metric(data["日経平均"])[1]
if sp is not None and y10 is not None:
    if sp<0 and y10>0: st.error("米金利上昇 → 米国株下落。インフレ・FRB政策を最優先で確認。")
    elif sp>0 and y10<0: st.success("米金利低下 → 米国株上昇。金融緩和期待が支援材料の可能性。")
    else: st.info("米金利と米株の方向が不一致。指標サプライズとニュースを確認。")
if fx is not None and nk is not None:
    st.write(f"ドル円 {fx:+.2f}%、日経 {nk:+.2f}%。円安は輸出企業に追い風ですが、米株安なら効果が相殺されます。")

st.divider()
st.subheader("🤖 AIによる『なぜ動くのか』分析")
if OPENAI_KEY:
    if st.button("AI分析を更新",type="primary"):
        payload={"market":{k:metric(v) for k,v in data.items()},
                 "events":today_events.head(10).to_dict("records"),
                 "news":news("米国 日本 中国 欧州 インフレ 雇用 金利 株価 為替",10)}
        prompt = (
            "あなたは世界経済の朝刊アナリストです。与えられた市場・経済指標・ニュースだけを根拠に日本語で回答してください。"
            "①今日の最重要材料TOP3 ②予想→実績→サプライズ ③インフレ→中央銀行→米金利→ドル円→米株→日経の因果チェーン "
            "④日経・ドル円・S&P500の短期方向 ⑤反証材料 ⑥今日最も見るべき数字。断定せず根拠を示してください。DATA="
            + str(payload)
        )
        try:
            r=requests.post("https://api.openai.com/v1/responses",
              headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
              json={"model":OPENAI_MODEL,"input":prompt},timeout=45)
            r.raise_for_status()
            j=r.json()
            ans=j.get("output_text")
            if not ans:
                ans="\n".join(c.get("text","") for o in j.get("output",[]) for c in o.get("content",[]) if isinstance(c,dict))
            st.markdown(ans or "AIから回答が返りませんでした。")
        except Exception as e: st.error(f"AI接続エラー: {e}")
else:
    st.info("AI分析を使うには Streamlit Secrets に OPENAI_API_KEY を設定してください。")

st.divider()
st.subheader("📰 経済ニュース")
tabs=st.tabs(["米国","日本","中国・欧州"])
for tab,q in zip(tabs,["米国 CPI PCE 雇用 FRB 金利 株価","日本 CPI 日銀 賃金 円相場 日経","中国 PMI CPI PPI 欧州 ECB インフレ"]):
    with tab:
        for e in news(q):
            st.markdown(f"**{e['title']}**  \n{e['date']}  \n[{e['link']}]({e['link']})")

with st.sidebar:
    st.header("⚙️ データ設定")
    st.write("市場：Yahoo Finance")
    st.write("予想・コンセンサス：Trading Economics API")
    st.write("AI：OpenAI API")
    st.caption("APIキーはコードに書かず、Streamlit Secretsで管理してください。")

st.caption("情報整理・分析支援用。投資判断は公式発表とご自身の判断で確認してください。")
