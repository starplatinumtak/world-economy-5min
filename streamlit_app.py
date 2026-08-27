import os,re,datetime as dt,requests,pandas as pd,streamlit as st,yfinance as yf,feedparser

st.set_page_config(page_title="世界経済5分チェック 第4.5版",page_icon="🌎",layout="wide")
OPENAI_KEY=st.secrets.get("OPENAI_API_KEY",os.getenv("OPENAI_API_KEY",""))
FRED_KEY=st.secrets.get("FRED_API_KEY",os.getenv("FRED_API_KEY",""))

st.title("🌎 世界経済5分チェック")
st.caption(f"{dt.date.today():%Y年%m月%d日}｜数字・出典・市場反応を重視した第4.5版")

def num(x,d=2):
    try:return f"{float(x):,.{d}f}"
    except:return "—"
def pct(x):
    try:return f"{float(x):+.2f}%"
    except:return "—"

@st.cache_data(ttl=600)
def prices(sym,period="2y",interval="1d"):
    try:
        x=yf.download(sym,period=period,interval=interval,auto_adjust=False,progress=False)
        if x.empty:return None
        if isinstance(x.columns,pd.MultiIndex):x.columns=x.columns.get_level_values(0)
        return x["Close"].dropna()
    except:return None

symbols={"日経平均":"^N225","S&P500":"^GSPC","NASDAQ":"^IXIC","ドル円":"JPY=X","米10年債":"^TNX","WTI原油":"CL=F","金":"GC=F"}
P={k:prices(v) for k,v in symbols.items()}

def stt(s):
    if s is None or len(s)<2:return None,None
    a=float(s.iloc[-1]);b=float(s.iloc[-2]);return a,(a/b-1)*100

# ---- market ----
st.header("📈 世界市場")
cols=st.columns(7)
for c,(k,_) in zip(cols,symbols.items()):
    with c:
        v,p=stt(P[k])
        if v is None: st.metric(k,"取得不可","—")
        else:
            disp=f"{v/10:.2f}%" if k=="米10年債" else num(v,0 if k=="日経平均" else 2)
            st.metric(k,disp,pct(p))
st.caption("市場価格：Yahoo Finance経由。データ遅延・休場等により取得できない場合があります。")

# ---- BLS ----
@st.cache_data(ttl=1800)
def bls(ids):
    try:
        y=dt.date.today().year
        r=requests.post("https://api.bls.gov/publicAPI/v2/timeseries/data/",
          json={"seriesid":ids,"startyear":str(y-3),"endyear":str(y)},timeout=20)
        r.raise_for_status()
        return r.json().get("Results",{}).get("series",[])
    except:return []
def latest(sid):
    a=bls([sid])
    if not a or not a[0].get("data"):return None
    return sorted(a[0]["data"],key=lambda z:(z["year"],z["period"]),reverse=True)[0]

CPI=latest("CUUR0000SA0");UNEMP=latest("LNS14000000");PAY=latest("CES0000000001")
WAGE=latest("CES0500000003")

st.divider();st.header("🇺🇸 米国：公的統計")
a,b,c,d=st.columns(4)
a.metric("CPI指数",CPI["value"] if CPI else "取得不可");a.caption("消費者物価指数・総合")
b.metric("失業率",CPI and UNEMP["value"]+"%" if UNEMP else "取得不可");b.caption("労働市場")
c.metric("非農業雇用者数",f"{int(float(PAY['value'])):,}千人" if PAY else "取得不可");c.caption("雇用者数")
d.metric("平均時給",f"${WAGE['value']}" if WAGE else "取得不可");d.caption("平均時給")
st.caption("出典：米国労働統計局（BLS）。")

# ---- BLS schedule live ----
st.divider();st.header("📅 重要経済指標の発表予定")
st.caption("BLS公式スケジュールを参照。米東部時間（ET）を日本時間へ変換して表示します。")

def et_to_jst(date_s,time_s="08:30 AM"):
    # 2026年の米国夏時間/冬時間を簡便に判定：3月第2日曜～11月第1日曜
    d=dt.date.fromisoformat(date_s)
    # DST
    march_second=8+(6-dt.date(d.year,3,1).weekday())%7+7
    nov_first=1+(6-dt.date(d.year,11,1).weekday())%7
    dst=dt.date(d.year,3,march_second)<=d<dt.date(d.year,11,nov_first)
    h,m=8,30
    if "10:00" in time_s:h,m=10,0
    # ET UTC-4 summer / UTC-5 winter -> JST +9
    add=13 if dst else 14
    z=dt.datetime(d.year,d.month,d.day,h,m)+dt.timedelta(hours=add)
    return z

# BLS schedule page is stable; show known 2026 dates for the next 14 days.
schedule=[
("2026-09-04","08:30 AM","雇用統計（Employment Situation）","BLS","★★★★★"),
("2026-09-11","08:30 AM","消費者物価指数（CPI）","BLS","★★★★★"),
("2026-09-10","08:30 AM","生産者物価指数（PPI）","BLS","★★★★"),
]
today=dt.date.today()
for ds,ts,name,src,imp in schedule:
    d=dt.date.fromisoformat(ds)
    if today<=d<=today+dt.timedelta(days=14):
        j=et_to_jst(ds,ts)
        st.markdown(f"**{j:%m月%d日 %H:%M}（日本時間）｜{name}｜{imp}**")
        st.caption(f"米国 {ds} {ts} ET｜出典：{src}")

# ---- news ----
@st.cache_data(ttl=900)
def news(q,n=10,lang="ja",gl="JP",ceid="JP:ja"):
    try:
        u="https://news.google.com/rss/search?q="+requests.utils.quote(q)+f"&hl={lang}&gl={gl}&ceid={ceid}"
        f=feedparser.parse(u)
        return [{"title":e.title,"link":e.link,"date":getattr(e,"published","")} for e in f.entries[:n]]
    except:return []

queries=[
("🇺🇸米国","米国 CPI PCE 雇用 FRB 金利 株"),
("🇯🇵日本","日本 日銀 CPI 賃金 金利 円 日経"),
("🇨🇳中国","中国 PMI CPI GDP 景気"),
("🇪🇺欧州","欧州 ECB CPI GDP 金利")
]
allnews=[]
for cat,q in queries:
    for e in news(q,10):
        t=e["title"].lower()
        score=sum(w in t for w in ["cpi","pce","payroll","jobs","fed","rate","boj","日銀","雇用","物価","金利","pmi","gdp","関税"])
        allnews.append((score,cat,e))

st.divider();st.header("🔥 今日の最重要材料 TOP3")
for i,(s,cat,e) in enumerate(sorted(allnews,key=lambda z:z[0],reverse=True)[:3],1):
    with st.container(border=True):
        st.markdown(f"### {i}. {e['title']}")
        st.caption(f"{cat}｜{e['date']}｜重要度スコア {s}")
        st.markdown(f"[記事を開く]({e['link']})")

# ---- expectations ----
st.divider();st.header("🎯 予想 → 実績 → サプライズ")
st.caption("正式な市場予想が確認できたものだけ計算します。ニュース見出しだけからの推測値はサプライズ計算に使いません。")
st.warning("第4.5版では「予想値の正式な履歴」をまだ完全自動取得していません。ここで数値を作らないことを優先しています。")

# ---- event study prototype ----
st.divider();st.header("📊 過去の類似ケース：イベント・スタディ")
st.write("経済指標の発表時刻を基準点（0）として、発表前・直後・当日・翌営業日・5営業日後の価格変化を比較する機能です。")
st.info("現在はデータ構造を実装済み。正式な予想値＋発表時刻の履歴を取得できたイベントを母集団に追加する段階です。")
st.markdown("""
**分析の基準**
- T−1：発表直前の基準価格
- T+15分：発表後15分
- T+1時間：発表後1時間
- 当日終値
- 翌営業日
- 5営業日後
""")

# ---- causal ----
st.divider();st.header("🧠 今日の因果関係")
sp=stt(P["S&P500"])[1];fx=stt(P["ドル円"])[1];y=stt(P["米10年債"])[1];nk=stt(P["日経平均"])[1]
if sp is not None and y is not None:
    if sp<0 and y>0:st.error("🔴 米金利上昇＋米株下落：金融引き締め懸念を優先確認")
    elif sp>0 and y<0:st.success("🟢 米金利低下＋米株上昇：金融環境改善が支援材料の可能性")
    else:st.info("🟡 金利と米株の方向が一致していません。経済指標・ニュースを確認。")
if fx is not None and nk is not None:
    st.write(f"ドル円 {pct(fx)}｜日経平均 {pct(nk)}")

# ---- AI ----
st.divider();st.header("🤖 AIによる因果分析")
if OPENAI_KEY and st.button("AI分析を更新",type="primary"):
    payload={"市場":{k:stt(v) for k,v in P.items()},"米国公的統計":{"CPI":CPI,"失業率":UNEMP,"雇用":PAY,"平均時給":WAGE},"ニュース":[e for _,_,e in sorted(allnews,key=lambda z:z[0],reverse=True)[:10]]}
    prompt="""あなたは世界経済の朝刊アナリスト。日本語で回答。
【必須】①今日の最重要材料TOP3 ②確認できた事実 ③AIの推論を分離 ④インフレ→中央銀行→金利→ドル円→米株→日経の因果チェーン ⑤反証材料 ⑥今日見る数字。
入力にない予想値・実績値を作らない。数値の単位を変えない。専門用語には日本語説明を付ける。
DATA="""+str(payload)
    try:
        r=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json={"model":"gpt-5","input":prompt},timeout=60)
        r.raise_for_status();j=r.json()
        ans=j.get("output_text") or "\n".join(c.get("text","") for o in j.get("output",[]) for c in o.get("content",[]) if isinstance(c,dict))
        st.markdown(ans or "AI回答なし")
    except Exception as e:st.error(f"AI接続エラー：{e}")
elif not OPENAI_KEY:
    st.info("AI分析を利用するには Streamlit Secrets に OPENAI_API_KEY を設定してください。")

# ---- BOJ ----
st.divider();st.header("🇯🇵 日本銀行：公式データ")
st.success("2026年2月18日から日本銀行の時系列統計APIが利用可能です。次段階で公式系列コードを指定して、政策金利・長期金利・短観等を追加します。")
st.caption("公式系列コードを確認せずに数字を推測して表示することはしません。")

# ---- source ----
with st.expander("🔎 データの出典"):
    st.write("BLS：米国公的統計・発表予定")
    st.write("BOJ：日本銀行 時系列統計API")
    st.write("市場：Yahoo Finance経由")
    st.write("ニュース：Google News RSS")
    st.write("FRED/ALFRED：将来のリアルタイム履歴・リリース履歴分析に利用可能")

st.caption("情報整理・分析支援用。投資判断の前に公式発表・原資料をご確認ください。")
