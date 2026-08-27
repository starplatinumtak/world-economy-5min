import os, re, datetime as dt, requests, pandas as pd, streamlit as st, yfinance as yf, feedparser

st.set_page_config(page_title="世界経済5分チェック",page_icon="🌎",layout="wide")

OPENAI_KEY=st.secrets.get("OPENAI_API_KEY",os.getenv("OPENAI_API_KEY",""))
FRED_KEY=st.secrets.get("FRED_API_KEY",os.getenv("FRED_API_KEY",""))

st.title("🌎 世界経済5分チェック")
st.caption(f"{dt.date.today():%Y年%m月%d日}｜重要指標・市場・ニュースを日本語で確認")

def n(x,d=2):
    try:return f"{float(x):,.{d}f}"
    except:return "—"
def ch(x):
    try:return f"{float(x):+.2f}%"
    except:return "—"

@st.cache_data(ttl=600)
def market(sym):
    try:
        x=yf.download(sym,period="1y",interval="1d",auto_adjust=False,progress=False)
        if x.empty:return None
        if isinstance(x.columns,pd.MultiIndex):x.columns=x.columns.get_level_values(0)
        return x["Close"].dropna()
    except:return None

symbols={"日経平均":"^N225","S&P500":"^GSPC","NASDAQ":"^IXIC","ドル円":"JPY=X","米10年債":"^TNX","WTI原油":"CL=F","金":"GC=F"}
data={k:market(v) for k,v in symbols.items()}

def stats(s):
    if s is None or len(s)<2:return None,None
    a=float(s.iloc[-1]);b=float(s.iloc[-2]);return a,(a/b-1)*100

st.header("🔥 今日の最重要材料 TOP3")

@st.cache_data(ttl=900)
def news(q,n=10,lang="ja",gl="JP",ceid="JP:ja"):
    try:
        u="https://news.google.com/rss/search?q="+requests.utils.quote(q)+f"&hl={lang}&gl={gl}&ceid={ceid}"
        f=feedparser.parse(u)
        return [{"title":e.title,"link":e.link,"date":getattr(e,"published","")} for e in f.entries[:n]]
    except:return []

qs=[
("🇺🇸米国","米国 CPI インフレ PCE 雇用 FRB 金利 株価 ドル"),
("🇯🇵日本","日本 CPI 日銀 政策金利 賃金 円 日経"),
("🇨🇳中国・🇪🇺欧州","中国 PMI CPI GDP 欧州 ECB インフレ")
]
items=[]
for cat,q in qs:
    for e in news(q,10):
        t=e["title"].lower()
        score=sum(w in t for w in ["cpi","inflation","pce","jobs","payroll","fed","rate","boj","nikkei","pmi","ecb","gdp","関税","日銀","雇用","物価"])
        items.append((score,cat,e))
for i,(s,cat,e) in enumerate(sorted(items,key=lambda z:z[0],reverse=True)[:3],1):
    with st.container(border=True):
        st.markdown(f"### {i}. {e['title']}")
        st.caption(f"{cat}｜{e['date']}")
        st.markdown(f"[ニュースを開く]({e['link']})")

st.divider();st.header("📈 世界市場")
cols=st.columns(7)
for c,(name,_) in zip(cols,symbols.items()):
    with c:
        v,p=stats(data[name])
        if v is None:st.metric(name,"取得不可","—")
        else:
            if name=="米10年債":disp=f"{v/10:.2f}%"
            elif name=="日経平均":disp=n(v,0)
            else:disp=n(v,2)
            st.metric(name,disp,ch(p))
st.caption("市場価格：Yahoo Finance経由。休場・データ遅延等で取得できない場合があります。")

@st.cache_data(ttl=1800)
def bls(ids):
    try:
        y=dt.date.today().year
        r=requests.post("https://api.bls.gov/publicAPI/v2/timeseries/data/",
                        json={"seriesid":ids,"startyear":str(y-2),"endyear":str(y)},timeout=20)
        return r.json().get("Results",{}).get("series",[])
    except:return []
def latest(series):
    a=bls([series])
    if not a or not a[0].get("data"):return None
    return sorted(a[0]["data"],key=lambda z:(z["year"],z["period"]),reverse=True)[0]
cpi=latest("CUUR0000SA0");unemp=latest("LNS14000000");pay=latest("CES0000000001")
wage=latest("CES0500000003");ppi=latest("WPUFD4")

st.divider();st.header("🇺🇸 米国の公的統計")
a,b,c,d,e=st.columns(5)
a.metric("CPI",cpi["value"]+"%" if cpi else "取得不可");a.caption("消費者物価指数")
b.metric("失業率",unemp["value"]+"%" if unemp else "取得不可");b.caption("失業率")
c.metric("雇用者数",f"{int(float(pay['value'])):,}千人" if pay else "取得不可");c.caption("非農業部門雇用者数")
d.metric("平均時給",f"${wage['value']}" if wage else "取得不可");d.caption("平均時給")
e.metric("PPI",ppi["value"] if ppi else "取得不可");e.caption("生産者物価指数")
st.caption("出典：米労働統計局（BLS）。値は公表値をそのまま表示。")

st.divider();st.header("🇯🇵 日本の主要経済データ")
st.info("日本銀行は2026年2月18日から時系列統計APIを提供開始。JSON/CSVで公式データを取得できます。主要時系列は原則、営業日に9時・12時・15時頃更新されます。")
st.markdown("**現在取得済み：** 日経平均・ドル円・米金利などの市場データ。")
st.markdown("**次段階：** 日銀政策金利、長期金利、短観、マネタリーベース等を公式系列コードで追加します。")
st.caption("日銀APIは公式の系列コードを確認してから接続します。系列コードを推測して数字を表示しません。")

st.divider();st.header("📅 今日から7日間の米国重要経済指標")
st.caption("BLS公式発表予定を基にした表示です。発表時刻は米東部時間（ET）。日本時間への変換は米国夏時間/冬時間を考慮する実装を次版で追加します。")
schedule=[
("2026-08-28","個人所得・個人消費支出（PCE）","米商務省 BEA","★5"),
("2026-09-04","雇用統計（Employment Situation）","米労働統計局 BLS","★5"),
]
today=dt.date.today()
for date,name,src,imp in schedule:
    dd=dt.date.fromisoformat(date)
    if today<=dd<=today+dt.timedelta(days=7):
        st.markdown(f"**{date}｜{name}｜{imp}**  \n{src}")

st.divider();st.header("🎯 予想 → 実績 → サプライズ")
st.write("サプライズ＝実績−市場予想。正式なコンセンサスが確認できない場合は推測しません。")
def exp(title):
    pats=[r"(?:expected|forecast|consensus|estimate)\s*(?:at|to be|of)?\s*(-?\d+(?:\.\d+)?)\s*%"]
    for p in pats:
        m=re.search(p,title,re.I)
        if m:
            try:return float(m.group(1))
            except:pass
    return None
rows=[]
for cat,q in qs:
    for e in news(q+" forecast consensus expected",12,"en-US","US","US:en"):
        x=exp(e["title"])
        if x is not None:rows.append([cat,e["date"],e["title"],x,e["link"]])
if rows:
    st.dataframe(pd.DataFrame(rows,columns=["分類","日時","ニュース","検出予想値","リンク"]),hide_index=True,use_container_width=True)
else:st.warning("現在、明確な市場予想値を検出できません。推測値は表示していません。")

st.divider();st.header("📊 過去の類似ケース")
st.info("発表前→1時間後→当日終値→翌営業日→5営業日後、の共通指標でイベント分析するための土台です。正式な予想履歴を取得できたイベントだけをサプライズ分析の母集団にします。")
st.warning("第4.4版では、過去イベントを捏造しないことを優先しています。次版で公式リリース日時と市場価格を結合し、実データによるイベント・スタディを追加します。")

st.divider();st.header("🧠 今日の因果関係")
sp=stats(data["S&P500"])[1];fx=stats(data["ドル円"])[1];y=stats(data["米10年債"])[1];nk=stats(data["日経平均"])[1]
if sp is not None and y is not None:
    if sp<0 and y>0:st.error("🔴 米金利上昇＋米株下落 → 金融引き締め懸念を優先確認")
    elif sp>0 and y<0:st.success("🟢 米金利低下＋米株上昇 → 金融環境改善の可能性")
    else:st.info("🟡 金利と米株の方向が一致していません。指標・ニュースを確認。")
if fx is not None and nk is not None:st.write(f"ドル円 {ch(fx)}｜日経平均 {ch(nk)}")

st.divider();st.header("🤖 AIによる因果分析")
if OPENAI_KEY:
    if st.button("AI分析を更新",type="primary"):
        payload={"市場":{k:stats(v) for k,v in data.items()},"米国公的統計":{"CPI":cpi,"失業率":unemp,"雇用者数":pay,"平均時給":wage,"PPI":ppi},"ニュース":[e for _,_,e in sorted(items,key=lambda z:z[0],reverse=True)[:10]]}
        prompt="""世界経済の朝刊アナリストとして日本語で回答。
①最重要材料TOP3 ②予想→実績→サプライズ（予想なしは推測禁止）
③インフレ→中央銀行→米金利→ドル円→米株→日経の因果関係
④日経・ドル円・S&P500の注目方向 ⑤反証材料 ⑥今日見るべき数字。
必ず「確認できた事実」と「AIの推論」を分ける。数字は入力データを改変しない。
専門用語には日本語説明を付ける。
DATA="""+str(payload)
        try:
            r=requests.post("https://api.openai.com/v1/responses",headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},json={"model":"gpt-5","input":prompt},timeout=60)
            r.raise_for_status();j=r.json()
            ans=j.get("output_text") or "\n".join(c.get("text","") for o in j.get("output",[]) for c in o.get("content",[]) if isinstance(c,dict))
            st.markdown(ans or "回答なし")
        except Exception as e:st.error(f"AI接続エラー：{e}")
else:st.info("AI分析を使う場合はStreamlit SecretsにOPENAI_API_KEYを設定してください。")

st.divider();st.header("📰 経済ニュース（日本語）")
tabs=st.tabs(["🇺🇸米国","🇯🇵日本","🇨🇳中国","🇪🇺欧州"])
for tab,(label,q) in zip(tabs,[("米国","米国 経済 CPI 雇用 FRB 金利"),("日本","日本 経済 日銀 CPI 賃金 円 日経"),("中国","中国 経済 PMI CPI GDP"),("欧州","欧州 ECB CPI 経済")]):
    with tab:
        for e in news(q,8):
            st.markdown(f"**{e['title']}**");st.caption(e["date"]);st.markdown(f"[記事を開く]({e['link']})")

with st.expander("🔎 出典・取得状態"):
    st.write("🇺🇸 BLS：CPI、雇用、失業率、平均時給、PPI")
    st.write("🇯🇵 日本銀行：時系列統計API（公式）")
    st.write("📈 市場：Yahoo Finance経由")
    st.write("📰 ニュース：Google News RSS")
    st.write("📚 FRED：APIキー設定時に拡張可能")

st.caption("情報整理・分析支援用。投資判断の前に公式発表・原資料をご確認ください。")
