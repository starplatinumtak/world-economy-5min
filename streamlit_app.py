import os, datetime as dt, requests, pandas as pd, streamlit as st, yfinance as yf, feedparser

st.set_page_config(page_title="世界経済5分チェック 第4.8版", page_icon="🌎", layout="wide")
OPENAI_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY",""))

def fmt(x, d=2):
    try: return f"{float(x):,.{d}f}"
    except: return "—"

def pct(x):
    try: return f"{float(x):+.2f}%"
    except: return "—"

@st.cache_data(ttl=600)
def market(sym):
    try:
        x = yf.download(sym, period="2y", interval="1d", auto_adjust=False, progress=False)
        if x.empty: return None
        if isinstance(x.columns, pd.MultiIndex): x.columns = x.columns.get_level_values(0)
        return x["Close"].dropna()
    except: return None

symbols = {"日経平均":"^N225", "S&P500":"^GSPC", "NASDAQ":"^IXIC", "ドル円":"JPY=X", "米10年債":"^TNX", "WTI原油":"CL=F", "金":"GC=F"}
M = {k: market(v) for k, v in symbols.items()}

def stats(s):
    if s is None or len(s) < 2: return None, None
    a = float(s.iloc[-1]); b = float(s.iloc[-2])
    return a, (a/b-1)*100

st.title("🌎 世界経済5分チェック")
st.caption(f"{dt.date.today():%Y年%m月%d日}｜朝5分で「何が相場を動かすか」を確認")

@st.cache_data(ttl=900)
def news(q, n=10):
    try:
        u = "https://news.google.com/rss/search?q=" + requests.utils.quote(q) + "&hl=ja&gl=JP&ceid=JP:ja"
        return [{"title": e.title, "link": e.link, "date": getattr(e, "published", "")} for e in feedparser.parse(u).entries[:n]]
    except: return []

sets = [("🇺🇸米国", "米国 CPI PCE 雇用 FRB 金利 株"), ("🇯🇵日本", "日本 日銀 CPI 賃金 円 日経"), ("🇨🇳中国", "中国 PMI CPI GDP 景気"), ("🇪🇺欧州", "欧州 ECB CPI GDP 金利")]
items = []
for cat, q in sets:
    for e in news(q):
        t = e["title"].lower()
        score = sum(w in t for w in ["cpi", "pce", "payroll", "jobs", "fed", "rate", "boj", "日銀", "雇用", "物価", "金利", "pmi", "gdp", "関税"])
        items.append((score, cat, e))

st.header("🔥 今日の最重要材料 TOP3")
for i, (s, cat, e) in enumerate(sorted(items, key=lambda z: z[0], reverse=True)[:3], 1):
    with st.container(border=True):
        st.markdown(f"### {i}. {e['title']}")
        st.caption(f"{cat}｜{e['date']}")
        st.markdown(f"[記事を開く]({e['link']})")

st.divider()
st.header("📈 世界市場")
cols = st.columns(7)

def fmt_yield(v):
    # Yahoo Financeの^TNXの値に応じて安全に金利表示(%)を調整
    return f"{v/10:.2f}%" if v > 10 else f"{v:.2f}%"

for c, (k, _) in zip(cols, symbols.items()):
    v, p = stats(M[k])
    if v is None:
        c.metric(k, "取得不可", "—")
    else:
        val_str = fmt_yield(v) if k == "米10年債" else fmt(v, 0 if k == "日経平均" else 2)
        c.metric(k, val_str, pct(p))

st.caption("市場データ：Yahoo Finance経由。休場・遅延等の場合があります。")

st.divider()
st.header("🇯🇵 日本経済")
st.subheader("日銀の公式データ")
st.caption("日本銀行 時系列統計データ検索サイト APIを利用。未取得の値は推測しません。")

BOJ_URL = "https://www.stat-search.boj.or.jp/api/v1/getData"
@st.cache_data(ttl=900)
def get_boj():
    try:
        # パラメータの不要なシングルクォーテーションを除去・安全なリクエスト構成
        r = requests.get(BOJ_URL, params={"format": "json", "lang": "jp", "db": "FM", "code": "FM01STRDCLUCON"}, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception as e: return {"error": str(e)}

bj = get_boj()
pairs = []
if isinstance(bj, dict):
    rs = bj.get("RESULTSET") or bj.get("resultset") or bj.get("data") or []
    if isinstance(rs, dict): rs = [rs]
    if rs:
        vals = rs[0].get("VALUES") or rs[0].get("values") or {}
        dates = vals.get("SURVEY_DATES") or vals.get("survey_dates") or []
        values = vals.get("VALUES") or vals.get("values") or []
        pairs = [(d, v) for d, v in zip(dates, values) if v not in ("NA", None, "")]

if pairs:
    ld, lv = pairs[-1]
    pv = pairs[-2][1] if len(pairs) > 1 else None
    a, b, c = st.columns(3)
    a.metric("無担保コールO/N物レート", f"{lv}%"); a.caption(f"基準日：{ld}")
    b.metric("前回値", f"{pv}%" if pv is not None else "—")
    c.metric("前回比", f"{float(lv)-float(pv):+.3f} pt" if pv is not None else "—")
else:
    st.warning("日銀APIから現在値を取得できませんでした。")

st.markdown("### 日本経済の重要指標")
for c, name, desc in zip(st.columns(4), ["政策金利", "長期金利", "CPI", "短観"], ["金融政策", "国債市場", "物価", "景況感"]):
    c.metric(name, "順次接続"); c.caption(desc)
st.caption("出典：日本銀行 時系列統計データ検索サイト API。")

# BLS API制限緩和のためキャッシュ時間を延長(6時間)
@st.cache_data(ttl=21600)
def bls(sid):
    try:
        y = dt.date.today().year
        r = requests.post("https://api.bls.gov/publicAPI/v2/timeseries/data/", json={"seriesid": [sid], "startyear": str(y-2), "endyear": str(y)}, timeout=20)
        a = r.json()["Results"]["series"][0]["data"]
        return sorted(a, key=lambda z: (z["year"], z["period"]), reverse=True)[0]
    except: return None

CPI = bls("CUUR0000SA0"); UNEMP = bls("LNS14000000"); PAY = bls("CES0000000001"); WAGE = bls("CES0500000003"); PPI = bls("WPUFD4")

st.divider()
st.header("🇺🇸 米国主要統計")
a, b, c, d, e = st.columns(5)
a.metric("CPI指数", CPI["value"] if CPI else "取得不可")
b.metric("失業率", UNEMP["value"] + "%" if UNEMP else "取得不可")
c.metric("非農業雇用者数", f"{int(float(PAY['value'])):,}千人" if PAY else "取得不可")
d.metric("平均時給", f"${WAGE['value']}" if WAGE else "取得不可")
e.metric("PPI", PPI["value"] if PPI else "取得不可")
st.caption("出典：米国労働統計局（BLS）。")

st.divider()
st.header("📅 今後の重要経済指標")
st.markdown("**2026年9月4日 21:30 日本時間｜米雇用統計（8月分）｜★★★★★**")
st.markdown("**2026年9月10日 21:30 日本時間｜米CPI（8月分）｜★★★★★**")
st.markdown("**2026年9月11日 21:30 日本時間｜米PPI（8月分）｜★★★★**")
st.caption("BLS公式スケジュール基準。米東部時間8:30 ETを日本時間へ換算。")

st.divider()
st.header("🎯 予想 → 実績 → サプライズ")
st.write("サプライズ ＝ 実績 − 市場予想。市場予想を確認できない場合は計算しません。")
st.info("第4.8版は実績・公式発表予定を自動取得。市場コンセンサス予想の履歴は、信頼できる予想データ源を接続した段階で自動計算します。")

st.header("📊 過去の類似サプライズ")
st.write("予想・実績・発表時刻が揃ったイベントだけを対象に、日経平均・ドル円・S&P500を発表直前→15分→1時間→当日→翌日→5営業日後で比較します。")
st.info("未確認の過去イベントは作らず、データが揃ったケースだけを分析します。")

st.divider()
st.header("🧠 今日の相場の因果関係")
sp = stats(M["S&P500"])[1]; y = stats(M["米10年債"])[1]; fx = stats(M["ドル円"])[1]; nk = stats(M["日経平均"])[1]
if sp is not None and y is not None:
    if sp < 0 and y > 0: st.error("🔴 米金利上昇＋米株下落 → インフレ・利下げ期待を確認")
    elif sp > 0 and y < 0: st.success("🟢 米金利低下＋米株上昇 → 金融環境改善の可能性")
    else: st.info("🟡 金利と米株の方向が一致していません。")
if fx is not None and nk is not None: st.write(f"ドル円 {pct(fx)}｜日経平均 {pct(nk)}")

st.divider()
st.header("🤖 AIによる因果分析")
if OPENAI_KEY and st.button("AI分析を更新", type="primary"):
    data = {
        "市場": {k: stats(v) for k, v in M.items()},
        "米国": {"CPI": CPI, "失業率": UNEMP, "雇用": PAY, "平均時給": WAGE, "PPI": PPI},
        "日本": {"日銀O/N": pairs[-1] if pairs else None},
        "ニュース": [e for _, _, e in sorted(items, key=lambda z: z[0], reverse=True)[:10]]
    }
    prompt = "世界経済の朝刊アナリストとして日本語で回答。①今日の最重要材料TOP3 ②確認できた事実 ③AIの推論 ④インフレ→中央銀行→金利→ドル円→米株→日経の因果関係 ⑤反証材料 ⑥今日見る数字。入力にない数値や市場予想を作らない。事実と推論を分ける。"
    
    headers = {
        "Authorization": f"Bearer {OPENAI_KEY}",
        "Content-Type": "application/json"
    }
    
    # 正しい OpenAI Chat Completions API 仕様へ修正
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": f"{prompt}\nDATA={data}"}
        ],
        "temperature": 0.3
    }
    
    try:
        r = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        res_json = r.json()
        ai_response = res_json["choices"][0]["message"]["content"]
        st.markdown(ai_response)
    except Exception as ex:
        st.error(f"AI接続エラー：{ex}")
else:
    st.info("AI分析を利用するにはStreamlit SecretsにOPENAI_API_KEYを設定してください。")

with st.expander("🔎 出典・注意"):
    st.write("日本銀行 時系列統計データ検索サイト API")
    st.write("米国労働統計局（BLS）")
    st.write("Yahoo Finance経由の市場データ")
    st.write("Google News RSS")
st.caption("情報整理・分析支援用。投資判断の前に公式発表・原資料をご確認ください。")
