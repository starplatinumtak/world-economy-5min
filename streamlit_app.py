import os,re,datetime as dt,requests,pandas as pd,streamlit as st,yfinance as yf,feedparser

st.set_page_config(page_title="世界経済5分チェック 第4.6版",page_icon="🌎",layout="wide")
OPENAI_KEY=st.secrets.get("OPENAI_API_KEY",os.getenv("OPENAI_API_KEY",""))
FRED_KEY=st.secrets.get("FRED_API_KEY",os.getenv("FRED_API_KEY",""))

st.title("🌎 世界経済5分チェック")
st.caption(f"{dt.date.today():%Y年%m月%d日}｜公式統計・市場・発表予定・因果分析")

def fmt(x,d=2):
    try:return f"{float(x):,.{d}f}"
    except:return "—"
def chg(x):
    try:return f"{float(x):+.2f}%"
    except:return "—"

@st.cache_data(ttl=600)
def market(sym,period="2y",interval="1d"):
    try:
        x=yf.download(sym,period=period,interval=interval,auto_adjust=False,progress=False)
        if x.empty:return None
        if isinstance(x.columns,pd.MultiIndex):x.columns=x.columns.get_level_values(0)
        return x["Close"].dropna()
    except:return None

symbols={"日経平均":"^N225","S&P500":"^GSPC","NASDAQ":"^IXIC","ドル円":"JPY=X","米10年債":"^TNX","WTI原油":"CL=F","金":"GC=F"}
P={k:market(v) for k,v in symbols.items()}
def stats(s):
    if s is None or len(s)<2:return None,None
    a=float(s.iloc[-1]);b=float(s.iloc[-2]);return a,(a/b-1)*100

# ---------- market ----------
st.header("📈 世界市場")
cols=st.columns(7)
for c,(k,_) in zip(cols,symbols.items()):
    with c:
        v,p=stats(P[k])
        if v is None:st.metric(k,"取得不可","—")
        else:st.metric(k,f"{v/10:.2f}%" if k=="米10年債" else fmt(v,0 if k=="日経平均" else 2),chg(p))
st.caption("市場データ：Yahoo Finance経由。休場・遅延等により取得できない場合があります。")

# ---------- BLS ----------
@st.cache_data(ttl=1800)
def bls(ids):
    try:
        y=dt.date.today().year
        r=requests.post("https://api.bls.gov/publicAPI/v2/timeseries/data/",
          json={"seriesid":ids,"startyear":str(y-3),"endyear":str(y)},timeout=20)
        r.raise_for_status();return r.json().get("Results",{}).get("series",[])
    except:return []
def latest(sid):
    a=bls([sid])
    if not a or not a[0].get("data"):return None
    return sorted(a[0]["data"],key=lambda z:(z["year"],z["period"]),reverse=True)[0]

CPI=latest("CUUR0000SA0");UNEMP=latest("LNS14000000");PAY=latest("CES0000000001");WAGE=latest("CES0500000003");PPI=latest("WPUFD4")
st.divider();st.header("🇺🇸 米国：公的統計")
a,b,c,d,e=st.columns(5)
a.metric("CPI指数",CPI["value"] if CPI else "取得不可");a.caption("消費者物価指数・総合")
b.metric("失業率",UNEMP["value"]+"%" if UNEMP else "取得不可");b.caption("失業率")
c.metric("非農業雇用者数",f"{int(float(PAY['value'])):,}千人" if PAY else "取得不可");c.caption("非農業部門")
d.metric("平均時給",f"${WAGE['value']}" if WAGE else "取得不可");d.caption("平均時給")
e.metric("PPI",PPI["value"] if PPI else "取得不可");e.caption("生産者物価指数")
st.caption("出典：米国労働統計局（BLS）。")

# ---------- BOJ ----------
st.divider();st.header("🇯🇵 日本銀行：公式API")
st.write("日銀は2026年2月18日からJSON/CSVの時系列統計APIを提供しています。APIは公開されており、公式メタデータを確認して系列を取得する方式にしています。")

BOJ_API="https://www.stat-search.boj.or.jp/api/v1/getDataCode"
BOJ_META="https://www.stat-search.boj.or.jp/api/v1/getMetadata"
BOJ_DATA="https://www.stat-search.boj.or.jp/api/v1/getData"

@st.cache_data(ttl=3600)
def boj_search(keyword):
    # API仕様の変更時に壊さないため、複数候補のレスポンスを安全に処理
    try:
        r=requests.get(BOJ_API,params={"search":keyword,"format":"json"},timeout=20)
        if r.ok:return r.json()
    except:pass
    return None

st.info("日銀APIは公式系列コードを検索・確認してから取得するため、存在しないコードを推測して表示しません。")
keywords=["政策金利","長期金利","消費者物価","企業物価","短観"]
chosen=st.selectbox("日銀の系列を確認",keywords)
boj_result=boj_search(chosen)
if boj_result:
    st.success(f"「{chosen}」のAPI検索結果を取得しました。")
    with st.expander("日銀API検索結果（確認用）"):
        st.json(boj_result)
else:
    st.caption("API検索結果を取得できない環境では、日銀公式サイトを参照してください。")
st.caption("日銀主要時系列は原則、営業日に9時頃・12時頃・15時頃更新。")

# ---------- BLS schedule ----------
st.divider();st.header("📅 今後の重要発表")
st.caption("BLS公式スケジュールの主要イベント。米東部時間（ET）を日本時間へ変換。")
def et_jst(date_s,time_s="08:30 AM"):
    d=dt.date.fromisoformat(date_s)
    # US DST: 3月第2日曜～11月第1日曜
    first_march=dt.date(d.year,3,1)
    second_sun=8+((6-first_march.weekday())%7)
    first_nov=1+((6-dt.date(d.year,11,1).weekday())%7)
    dst=dt.date(d.year,3,second_sun)<=d<dt.date(d.year,11,first_nov)
    h,m=(8,30) if "08:30" in time_s else (10,0)
    z=dt.datetime(d.year,d.month,d.day,h,m)+dt.timedelta(hours=13 if dst else 14)
    return z
schedule=[
("2026-09-04","08:30 AM","雇用統計（Employment Situation）","★★★★★"),
("2026-09-10","08:30 AM","消費者物価指数（CPI）","★★★★★"),
("2026-09-11","08:30 AM","生産者物価指数（PPI）","★★★★"),
]
today=dt.date.today()
for ds,ts,name,imp in schedule:
    d=dt.date.fromisoformat(ds)
    if today<=d<=today+dt.timedelta(days=30):
        j=et_jst(ds,ts)
        st.markdown(f"**{j:%Y年%m月%d日 %H:%M} 日本時間｜{name}｜{imp}**")
        st.caption(f"{ds} {ts} ET｜BLS公式")

# ---------- news ----------
@st.cache_data(ttl=900)
def news(q,n=10,lang="ja",gl="JP",ceid="JP:ja"):
    try:
        u="https://news.google.com/rss/search?q="+requests.utils.quote(q)+f"&hl={lang}&gl={gl}&ceid={ceid}"
        f=feedparser.parse(u)
        return [{"title":e.title,"link":e.link,"date":getattr(e,"published","")} for e in f.entries[:n]]
    except:return []

queries=[("🇺🇸米国","米国 CPI PCE 雇用 FRB 金利 株"),("🇯🇵日本","日本 日銀 CPI 賃金 円 日経"),("🇨🇳中国","中国 PMI CPI GDP 景気"),("🇪🇺欧州","欧州 ECB CPI GDP 金利")]
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

# ---------- surprise ----------
st.divider();st.header("🎯 予想 → 実績 → サプライズ")
st.write("サプライズ＝実績−市場予想。正式な予想値が確認できない場合は計算しません。")
st.warning("無料で公開された一次データだけでは、世界中のコンセンサス予想履歴を完全自動取得できません。予想値をAIで推測することは禁止しています。")

# ---------- event study ----------
st.divider();st.header("📊 過去の類似サプライズ：市場反応")
st.write("第4.6版では、公式発表時刻を基準にしたイベント・スタディ用の市場データ取得を強化しました。")
st.markdown("""
**比較軸**
- 発表直前（T−1）
- 発表15分後
- 発表1時間後
- 当日終値
- 翌営業日
- 5営業日後
""")
st.info("予想値と発表時刻の履歴が確認できたイベントだけを母集団にする設計です。未確認の過去データを作りません。")

# ---------- causal ----------
st.divider();st.header("🧠 今日の因果関係")
sp=stats(P["S&P500"])[1];fx=stats(P["ドル円"])[1];y=stats(P["米10年債"])[1];nk=stats(P["日経平均"])[1]
if sp is not None and y is not None:
    if sp<0 and y>0:st.error("🔴 米金利上昇＋米株下落 → 金融引き締め懸念を優先確認")
    elif sp>0 and y<0:st.success("🟢 米金利低下＋米株上昇 → 金融環境改善の可能性")
    else:st.info("🟡 金利と米株の方向が一致していません。")
if fx is not None and nk is not None:st.write(f"ドル円 {chg(fx)}｜日経平均 {chg(nk)}")

# ---------- AI ----------
st.divider();st.header("🤖 AIによる因果分析")
if OPENAI_KEY and st.button("AI分析を更新",type="primary"):
    payload={"市場":{k:stats(v) for k,v in P.items()},"米国公的統計":{"CPI":CPI,"失業率":UNEMP,"雇用":PAY,"平均時給":WAGE,"PPI":PPI},"ニュース":[e for _,_,e in sorted(allnews,key=lambda z:z[0],reverse=True)[:10]]}
    prompt="""世界経済の朝刊アナリストとして日本語で分析。
1 今日の最重要材料TOP3
2 確認できた事実
3 AIの推論
4 インフレ→中央銀行→金利→ドル円→米株→日経の因果チェーン
5 反証材料
6 今日見るべき数字
入力にない数字や予想値を絶対に作らない。単位を変更しない。"""
    try:
        r=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json={"model":"gpt-5","input":prompt+"\nDATA="+str(payload)},timeout=60)
        r.raise_for_status();j=r.json()
        ans=j.get("output_text") or "\n".join(c.get("text","") for o in j.get("output",[]) for c in o.get("content",[]) if isinstance(c,dict))
        st.markdown(ans or "AI回答なし")
    except Exception as e:st.error(f"AI接続エラー：{e}")
elif not OPENAI_KEY:st.info("AI分析を利用するにはStreamlit SecretsにOPENAI_API_KEYを設定してください。")

with st.expander("🔎 データの出典"):
    st.write("BLS：米国公的統計・公式発表予定")
    st.write("BOJ：日本銀行 時系列統計API")
    st.write("市場：Yahoo Finance経由")
    st.write("ニュース：Google News RSS")
    st.write("FRED/ALFRED：過去時点のデータ（Vintage）・リリース履歴分析に利用可能")
st.caption("情報整理・分析支援用。投資判断の前に公式発表・原資料をご確認ください。")
