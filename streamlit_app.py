
import os, re, datetime as dt, requests, pandas as pd, streamlit as st, yfinance as yf, feedparser

st.set_page_config(page_title="世界経済5分チェック", page_icon="🌎", layout="wide")

# =========================
# Settings
# =========================
st.title("🌎 世界経済5分チェック")
st.caption(f"{dt.date.today():%Y年%m月%d日}｜朝5分で「今日は何が相場を動かすか」を確認")

OPENAI_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY",""))
OPENAI_MODEL = st.secrets.get("OPENAI_MODEL", os.getenv("OPENAI_MODEL","gpt-5"))

# =========================
# Market data
# =========================
@st.cache_data(ttl=600)
def market(sym):
    try:
        x = yf.download(sym, period="1y", interval="1d", auto_adjust=False, progress=False)
        if x.empty: return None
        if isinstance(x.columns, pd.MultiIndex):
            x.columns = x.columns.get_level_values(0)
        return x["Close"].dropna()
    except Exception:
        return None

SYMBOLS = {
    "日経平均":"^N225", "S&P500":"^GSPC", "NASDAQ":"^IXIC",
    "ドル円":"JPY=X", "米10年債":"^TNX", "WTI":"CL=F", "金":"GC=F"
}
DATA = {k: market(v) for k,v in SYMBOLS.items()}

def metric(s):
    if s is None or len(s) < 2: return None, None
    a=float(s.iloc[-1]); b=float(s.iloc[-2])
    return a, (a/b-1)*100

st.subheader("📈 世界市場")
cols=st.columns(7)
for c,(name,_) in zip(cols,SYMBOLS.items()):
    with c:
        v,p=metric(DATA[name])
        if v is not None: st.metric(name,f"{v:,.2f}",f"{p:+.2f}%")

# =========================
# Official US data: BLS
# =========================
@st.cache_data(ttl=1800)
def bls(series_ids):
    url="https://api.bls.gov/publicAPI/v2/timeseries/data/"
    try:
        y=dt.date.today().year
        r=requests.post(url,json={"seriesid":series_ids,"startyear":str(y-10),"endyear":str(y)},timeout=25)
        r.raise_for_status()
        return r.json().get("Results",{}).get("series",[])
    except Exception:
        return []

def latest_bls(series_id):
    rows=bls([series_id])
    if not rows or not rows[0].get("data"): return None
    return sorted(rows[0]["data"],key=lambda x:(x["year"],x["period"]),reverse=True)[0]

CPI = latest_bls("CUUR0000SA0")
UNEMP = latest_bls("LNS14000000")
PAYROLL = latest_bls("CES0000000001")

st.divider()
st.subheader("🇺🇸 米国の公的経済データ")
a,b,c=st.columns(3)
with a:
    st.metric("CPI指数", CPI.get("value") if CPI else "取得不可")
    st.caption("BLS CPI-U指数（実績）")
with b:
    st.metric("失業率", UNEMP.get("value")+"%" if UNEMP else "取得不可")
    st.caption("BLS（実績）")
with c:
    st.metric("非農業部門雇用者数", PAYROLL.get("value") if PAYROLL else "取得不可")
    st.caption("BLS（実績）")

# =========================
# News / forecast extraction
# =========================
@st.cache_data(ttl=900)
def news(q,n=10):
    try:
        u="https://news.google.com/rss/search?q="+requests.utils.quote(q)+"&hl=en-US&gl=US&ceid=US:en"
        f=feedparser.parse(u)
        return [{"title":e.title,"link":e.link,"date":getattr(e,"published","")} for e in f.entries[:n]]
    except Exception:
        return []

def extract_forecast(title):
    # Conservative extraction only. Never invent consensus.
    patterns=[
        r"(?:expected|forecast|economists expect|estimate(?:d)?)\s*(?:at|to be|of)?\s*(-?\d+(?:\.\d+)?)\s*%",
        r"(?:expected|forecast|economists expect|estimate(?:d)?)\s*(?:at|to be|of)?\s*(-?\d+(?:\.\d+)?)",
        r"(?:consensus)\s*(?:at|of|:)?\s*(-?\d+(?:\.\d+)?)\s*%"
    ]
    for p in patterns:
        m=re.search(p,title,re.I)
        if m:
            try:return float(m.group(1))
            except: pass
    return None

def classify_forecast(title):
    t=title.lower()
    if any(x in t for x in ["consensus","economists expect","consensus estimate"]): return "高"
    if any(x in t for x in ["expected","forecast","estimate"]): return "中"
    return "低"

@st.cache_data(ttl=900)
def forecast_news():
    qs=[
        ("米CPI","US CPI consensus forecast expected inflation"),
        ("米雇用","US jobs report consensus forecast payroll unemployment"),
        ("米PCE","US PCE consensus forecast inflation"),
        ("日本CPI","Japan CPI consensus forecast inflation"),
        ("日本GDP","Japan GDP consensus forecast"),
        ("中国PMI","China PMI consensus forecast"),
        ("欧州CPI","Eurozone CPI consensus forecast inflation"),
    ]
    out=[]
    for label,q in qs:
        for e in news(q,10):
            f=extract_forecast(e["title"])
            if f is not None:
                out.append({**e,"indicator":label,"forecast":f,"confidence":classify_forecast(e["title"])})
    return out

FORECASTS=forecast_news()

st.divider()
st.subheader("🎯 予想・実績・サプライズ")
st.warning(
    "重要：無料・公開情報だけでは世界各国の正式な市場コンセンサスを安定取得できません。"
    "そのため、ここではニュース見出しに明記された予想だけを「検出予想」として扱います。"
    "見つからない値は推測しません。"
)

if FORECASTS:
    fdf=pd.DataFrame(FORECASTS)[["indicator","forecast","confidence","date","title","link"]]
    fdf.columns=["指標","検出予想","信頼度","日時","ニュース","リンク"]
    st.dataframe(fdf,hide_index=True,use_container_width=True)
else:
    st.info("現在、明示的な予想値を検出できませんでした。")

# =========================
# Upcoming calendar / release schedule
# =========================
st.subheader("🗓️ これからの重要指標")
st.caption("予定日は公的機関・中央銀行の公開スケジュールを優先します。")

calendar = news("US CPI jobs report PCE GDP FOMC Japan CPI BOJ China PMI ECB inflation economic calendar",15)
for e in calendar[:8]:
    st.markdown(f"- **{e['title']}** — {e['date']}  [記事]({e['link']})")

# =========================
# Historical market response helper
# =========================
def event_window(series, event_date, days):
    if series is None or len(series)<2: return None
    idx=pd.to_datetime(series.index)
    d=pd.Timestamp(event_date)
    before=series.loc[idx<=d]
    after=series.loc[idx>d]
    if before.empty or after.empty: return None
    j=min(days-1, len(after)-1)
    return float((after.iloc[j]/before.iloc[-1]-1)*100)

st.divider()
st.subheader("📚 過去の類似サプライズ")
st.info(
    "この版では「予想が確認できたイベントだけ」を分析対象にします。"
    "予想値が取れないイベントを勝手に補完しないため、分析件数が少なくなることがあります。"
)
st.write("正式な過去コンセンサス履歴を無料で安定取得できる公開APIが確認できないため、履歴を捏造せず、次段階で実データ源を追加できる構造にしています。")

# =========================
# Current causal signal
# =========================
st.divider()
st.subheader("🧠 今日の因果関係")
sp=metric(DATA["S&P500"])[1]
fx=metric(DATA["ドル円"])[1]
y10=metric(DATA["米10年債"])[1]
nk=metric(DATA["日経平均"])[1]
wti=metric(DATA["WTI"])[1]

signals=[]
if sp is not None and y10 is not None:
    if sp<0 and y10>0:
        signals.append(("🔴","米金利上昇＋米株下落","金融引き締め懸念が優勢の可能性"))
    elif sp>0 and y10<0:
        signals.append(("🟢","米金利低下＋米株上昇","金融環境改善・利下げ期待が支援材料の可能性"))
    else:
        signals.append(("🟡","米金利と米株の方向が不一致","経済指標・ニュースを追加確認"))
if fx is not None and nk is not None:
    signals.append(("🔵","ドル円と日経","円安は輸出株に追い風になり得る一方、米株安なら相殺され得る"))
if wti is not None:
    signals.append(("🟠","原油","エネルギー価格の変化はインフレ・企業コスト・家計購買力に波及"))

for icon,title,desc in signals:
    st.markdown(f"**{icon} {title}** — {desc}")

# =========================
# TOP 3 scoring
# =========================
st.subheader("🔥 今日の最重要材料 TOP3")
allnews = news("US CPI PCE jobs payroll Fed rates inflation tariff GDP BOJ Japan Nikkei China PMI ECB",30)
keywords={
    "cpi":3,"inflation":3,"payroll":3,"jobs":3,"employment":3,"fed":3,"fomc":3,
    "interest rate":3,"rate":2,"pce":3,"gdp":2,"boj":3,"bank of japan":3,
    "nikkei":2,"china":2,"pmi":2,"tariff":2,"trade":2,"yen":2
}
ranked=[]
for e in allnews:
    t=e["title"].lower()
    score=sum(v for k,v in keywords.items() if k in t)
    if "breaking" in t or "surprise" in t or "unexpected" in t: score+=2
    ranked.append((score,e))
top=sorted(ranked,key=lambda x:x[0],reverse=True)[:3]
for i,(score,e) in enumerate(top,1):
    st.markdown(f"### {i}. {e['title']}")
    st.caption(f"重要度スコア {score}｜{e['date']}")
    st.markdown(f"[ニュースを開く]({e['link']})")

# =========================
# AI
# =========================
st.divider()
st.subheader("🤖 AIによる因果分析")
if OPENAI_KEY:
    if st.button("AI分析を更新",type="primary"):
        payload={
            "market":{k:metric(v) for k,v in DATA.items()},
            "official_us":{"cpi":CPI,"unemployment":UNEMP,"payroll":PAYROLL},
            "forecasts":FORECASTS[:20],
            "top_news":[e for _,e in top],
            "signals":signals
        }
        prompt=(
            "あなたは日本の個人投資家向けの世界経済朝刊アナリストです。"
            "与えられたDATAだけを根拠に、日本語で読みやすく分析してください。"
            "必ず次の順番：1 今日の最重要材料TOP3、2 予想・実績・サプライズ、"
            "3 因果チェーン（物価→中央銀行→金利→為替→米株→日経）、"
            "4 日経・ドル円・S&P500への短期影響、5 反証材料、6 今日確認する数字。"
            "予想値がDATAにない場合は絶対に推測せず「予想値取得なし」と書く。"
            "事実と推論を明確に区別し、断定的な投資助言はしない。DATA="+str(payload)
        )
        try:
            r=requests.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
                json={"model":OPENAI_MODEL,"input":prompt},
                timeout=60
            )
            r.raise_for_status()
            j=r.json()
            ans=j.get("output_text")
            if not ans:
                ans="\n".join(
                    c.get("text","")
                    for o in j.get("output",[])
                    for c in o.get("content",[])
                    if isinstance(c,dict)
                )
            st.markdown(ans or "AIから回答が返りませんでした。")
        except Exception as e:
            st.error(f"AI接続エラー: {e}")
else:
    st.info("AI分析を有効にするには、Streamlit Secretsに OPENAI_API_KEY を設定してください。")

# =========================
# News
# =========================
st.divider()
st.subheader("📰 経済ニュース")
for tab,q in zip(
    st.tabs(["🇺🇸米国","🇯🇵日本","🇨🇳中国・🇪🇺欧州"]),
    [
        "US CPI PCE jobs Fed interest rates stocks",
        "Japan CPI BOJ wages yen Nikkei GDP",
        "China PMI CPI PPI Europe ECB inflation"
    ]
):
    with tab:
        for e in news(q,8):
            st.markdown(f"**{e['title']}**  \n{e['date']}  \n[{e['link']}]({e['link']})")

with st.sidebar:
    st.header("⚙️ データ構成")
    st.write("市場：Yahoo Finance")
    st.write("米国実績：BLS Public Data API")
    st.write("ニュース：Google News RSS")
    st.write("AI：OpenAI API（任意）")
    st.caption("無料構成を優先。取得できない予想値は推測しません。情報整理・分析支援用です。")
