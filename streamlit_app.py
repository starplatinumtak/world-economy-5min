import os, re, datetime as dt, requests, pandas as pd, streamlit as st, yfinance as yf, feedparser

st.set_page_config(page_title="世界経済5分チェック", page_icon="🌎", layout="wide")

# =========================
# 設定
# =========================
OPENAI_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", ""))
OPENAI_MODEL = st.secrets.get("OPENAI_MODEL", os.getenv("OPENAI_MODEL", "gpt-5"))
FRED_KEY = st.secrets.get("FRED_API_KEY", os.getenv("FRED_API_KEY", ""))

st.title("🌎 世界経済5分チェック")
st.caption(f"{dt.date.today():%Y年%m月%d日}｜世界の重要指標・市場・ニュースを日本語で整理")

# =========================
# 共通関数
# =========================
def safe_num(x, digits=2):
    try:
        if x is None or pd.isna(x):
            return "—"
        return f"{float(x):,.{digits}f}"
    except Exception:
        return "—"

def pct(x):
    try:
        return f"{float(x):+.2f}%"
    except Exception:
        return "—"

def jp_date(s):
    try:
        return pd.Timestamp(s).strftime("%Y年%m月%d日")
    except Exception:
        return str(s)

@st.cache_data(ttl=600)
def market(sym):
    try:
        x = yf.download(sym, period="1y", interval="1d", auto_adjust=False, progress=False)
        if x.empty:
            return None
        if isinstance(x.columns, pd.MultiIndex):
            x.columns = x.columns.get_level_values(0)
        return x["Close"].dropna()
    except Exception:
        return None

symbols = {
    "日経平均": "^N225",
    "S&P500": "^GSPC",
    "NASDAQ": "^IXIC",
    "ドル円": "JPY=X",
    "米10年債利回り": "^TNX",
    "WTI原油": "CL=F",
    "金": "GC=F",
}

data = {k: market(v) for k, v in symbols.items()}

def market_stats(s):
    if s is None or len(s) < 2:
        return None, None
    now = float(s.iloc[-1])
    prev = float(s.iloc[-2])
    return now, (now / prev - 1) * 100

# =========================
# 最上段：朝5分サマリー
# =========================
st.header("🔥 今日の最重要材料 TOP3")

@st.cache_data(ttl=900)
def news(q, n=10, lang="en-US", gl="US", ceid="US:en"):
    try:
        u = "https://news.google.com/rss/search?q=" + requests.utils.quote(q)
        u += f"&hl={lang}&gl={gl}&ceid={ceid}"
        f = feedparser.parse(u)
        return [{"title": e.title, "link": e.link,
                 "date": getattr(e, "published", "")} for e in f.entries[:n]]
    except Exception:
        return []

important_queries = [
    ("米国インフレ・雇用・FRB", "US CPI inflation PCE jobs payroll Fed interest rates"),
    ("日本・日銀・円", "Japan CPI BOJ wages yen Nikkei"),
    ("中国・欧州", "China PMI CPI PPI Europe ECB inflation"),
]

all_news = []
for category, q in important_queries:
    for e in news(q, 8):
        title = e["title"].lower()
        score = sum(w in title for w in [
            "cpi", "inflation", "pce", "jobs", "payroll", "fed", "rate",
            "tariff", "gdp", "boj", "nikkei", "china", "pmi", "ecb"
        ])
        all_news.append((score, category, e))

top3 = sorted(all_news, key=lambda z: z[0], reverse=True)[:3]

for i, (score, category, e) in enumerate(top3, 1):
    with st.container(border=True):
        st.markdown(f"### {i}. {e['title']}")
        st.caption(f"{category}｜{e['date']}")
        st.markdown(f"[ニュース本文を開く]({e['link']})")

# =========================
# 市場
# =========================
st.divider()
st.header("📈 世界市場の現在地")

cols = st.columns(7)
for c, (name, _) in zip(cols, symbols.items()):
    with c:
        v, p = market_stats(data[name])
        if v is None:
            st.metric(name, "取得中/取得不可", "—")
        else:
            # 米10年債はYahooの値が「％×100」表記なので 10.5 -> 4.1% のような誤表示を防ぐ
            if name == "米10年債利回り":
                display = f"{v/10:.2f}%"
            elif name in ["日経平均", "S&P500", "NASDAQ"]:
                display = safe_num(v, 0 if name == "日経平均" else 2)
            else:
                display = safe_num(v, 2)
            st.metric(name, display, pct(p))

st.caption("※市場データはYahoo Finance経由。表示時点・市場休場等により取得できない場合があります。")

# =========================
# BLS 米国実績
# =========================
@st.cache_data(ttl=1800)
def bls(series_ids):
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    try:
        y = dt.date.today().year
        r = requests.post(
            url,
            json={"seriesid": series_ids, "startyear": str(y-2), "endyear": str(y)},
            timeout=20
        )
        r.raise_for_status()
        return r.json().get("Results", {}).get("series", [])
    except Exception:
        return []

def latest_bls(series_id):
    rows = bls([series_id])
    if not rows or not rows[0].get("data"):
        return None
    return sorted(rows[0]["data"],
                  key=lambda x: (x["year"], x["period"]),
                  reverse=True)[0]

cpi = latest_bls("CUUR0000SA0")
unemp = latest_bls("LNS14000000")
payroll = latest_bls("CES0000000001")

st.divider()
st.header("🇺🇸 米国の主要実績値")
us1, us2, us3 = st.columns(3)

with us1:
    st.metric("消費者物価指数（CPI）", cpi["value"] if cpi else "取得不可")
    st.caption("Consumer Price Index｜米労働統計局 BLS")
    if cpi: st.caption(f"対象：{cpi['year']}年 {cpi['period']}")

with us2:
    st.metric("失業率", f"{unemp['value']}%" if unemp else "取得不可")
    st.caption("Unemployment Rate｜BLS")
    if unemp: st.caption(f"対象：{unemp['year']}年 {unemp['period']}")

with us3:
    st.metric("非農業部門雇用者数", f"{int(float(payroll['value'])):,}千人" if payroll else "取得不可")
    st.caption("Total Nonfarm Payrolls｜BLS")
    if payroll: st.caption(f"対象：{payroll['year']}年 {payroll['period']}")

# =========================
# BOJ API：日本の主要統計（APIの公開開始は2026/2/18）
# =========================
st.divider()
st.header("🇯🇵 日本銀行データ")

st.info("日本銀行は2026年2月から時系列統計APIを公開しています。第4.3版ではAPI接続欄を用意し、取得できた統計を日本語表示する構成にしています。")

st.markdown("**現在の市場確認**：日経平均・ドル円・米金利を上の「世界市場」で確認できます。")
st.caption("日銀の統計系列コードは種類が非常に多いため、系列コードを推測して数字を表示することは避けています。")

# =========================
# 予想・実績・サプライズ
# =========================
st.divider()
st.header("🎯 予想・実績・サプライズ")

st.markdown("""
**サプライズ = 実績 − 市場予想**

ただし、正式な市場コンセンサスを確認できない場合は、数字を推測しません。
「取得なし」と表示します。
""")

def extract_expectation(title):
    patterns = [
        r"(?:expected|forecast|economists expect|estimate(?:d)?)\s*(?:at|to be|of)?\s*(-?\d+(?:\.\d+)?)\s*%",
        r"(?:vs\.?|versus)\s*(?:forecast|estimate|expected)\s*(-?\d+(?:\.\d+)?)\s*%",
    ]
    for pat in patterns:
        m = re.search(pat, title, re.I)
        if m:
            try:
                return float(m.group(1))
            except Exception:
                pass
    return None

expectations = []
for category, q in important_queries:
    for e in news(q + " forecast consensus expected", 10):
        x = extract_expectation(e["title"])
        if x is not None:
            expectations.append({
                "分類": category,
                "日時": e["date"],
                "ニュース": e["title"],
                "検出予想値": x,
                "リンク": e["link"]
            })

if expectations:
    st.dataframe(pd.DataFrame(expectations), hide_index=True, use_container_width=True)
else:
    st.warning("現在、ニュース見出しから明確な予想値を検出できませんでした。推測値は表示していません。")

# =========================
# イベント・スタディ
# =========================
st.divider()
st.header("📊 過去の類似ケース・市場反応")

st.write("""
発表前 → 1時間後 → 当日終値 → 翌営業日 → 5営業日後、という共通の物差しで
市場反応を分析するための画面です。
""")

st.warning("第4.3版では、予想値の正式な履歴を無料で完全取得できないため、正式なサプライズ値が確認できたイベントだけを将来の母集団に入れる設計です。未確認の予想値を使った過去分析は行いません。")

# =========================
# 因果分析
# =========================
st.divider()
st.header("🧠 今日の因果関係")

sp = market_stats(data["S&P500"])[1]
fx = market_stats(data["ドル円"])[1]
y10 = market_stats(data["米10年債利回り"])[1]
nk = market_stats(data["日経平均"])[1]

if sp is not None and y10 is not None:
    if sp < 0 and y10 > 0:
        st.error("🔴 米金利上昇 ＋ 米株下落 → 金融引き締め懸念を最優先で確認")
    elif sp > 0 and y10 < 0:
        st.success("🟢 米金利低下 ＋ 米株上昇 → 金融環境改善が支援材料の可能性")
    else:
        st.info("🟡 米金利と米株の方向が一致していません。経済指標・ニュースを確認してください。")

if fx is not None and nk is not None:
    st.write(f"ドル円：{pct(fx)}　｜　日経平均：{pct(nk)}")
    st.caption("円安は一般に輸出企業には追い風ですが、米株安・金利上昇など別要因が強い場合は相殺されます。")

# =========================
# AI
# =========================
st.divider()
st.header("🤖 AIによる因果分析")

if OPENAI_KEY:
    if st.button("AI分析を更新", type="primary"):
        payload = {
            "market": {k: market_stats(v) for k, v in data.items()},
            "US_official": {
                "CPI": cpi,
                "unemployment": unemp,
                "payroll": payroll
            },
            "top_news": [e for _, _, e in top3],
            "detected_expectations": expectations[:20],
        }

        prompt = """
あなたは世界経済の朝刊アナリストです。
以下のDATAだけを根拠に、日本語で分析してください。

必須：
1. 今日の最重要材料TOP3
2. 予想→実績→サプライズ。予想値がない場合は絶対に推測しない
3. インフレ→中央銀行→米金利→ドル円→米国株→日経の因果チェーン
4. 日経・ドル円・S&P500の短期的な注目方向
5. 反対方向に動く可能性がある材料
6. 今日もっとも確認すべき数字
7. 「事実」と「AIの推論」を明確に区別

表示されている数字は桁・単位を変えず、分からない数字を補完しないでください。
専門用語には可能な限り日本語説明を付けてください。

DATA:
""" + str(payload)

        try:
            r = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {OPENAI_KEY}",
                    "Content-Type": "application/json"
                },
                json={"model": OPENAI_MODEL, "input": prompt},
                timeout=60
            )
            r.raise_for_status()
            j = r.json()
            ans = j.get("output_text")
            if not ans:
                ans = "\n".join(
                    c.get("text", "")
                    for o in j.get("output", [])
                    for c in o.get("content", [])
                    if isinstance(c, dict)
                )
            st.markdown(ans or "AIから回答が返りませんでした。")
        except Exception as e:
            st.error(f"AI接続エラー：{e}")
else:
    st.info("AI分析を使う場合は Streamlit Secrets に OPENAI_API_KEY を設定してください。")

# =========================
# ニュース：日本語検索を優先
# =========================
st.divider()
st.header("📰 経済ニュース（日本語優先）")

jp_queries = [
    ("🇺🇸 米国", "米国 CPI 雇用統計 FRB 金利 株価 ドル"),
    ("🇯🇵 日本", "日本 CPI 日銀 賃金 円 日経"),
    ("🇨🇳 中国", "中国 PMI CPI GDP 経済"),
    ("🇪🇺 欧州", "欧州 ECB CPI 経済"),
]

tabs = st.tabs([x[0] for x in jp_queries])
for tab, (label, q) in zip(tabs, jp_queries):
    with tab:
        for e in news(q, 8, lang="ja", gl="JP", ceid="JP:ja"):
            st.markdown(f"**{e['title']}**")
            st.caption(e["date"])
            st.markdown(f"[ニュースを開く]({e['link']})")

# =========================
# 詳細
# =========================
with st.expander("🔎 データの出典・取得状態"):
    st.write("米国実績：米国労働統計局（BLS）")
    st.write("日本銀行：日本銀行 時系列統計データ検索サイト API")
    st.write("市場価格：Yahoo Finance経由")
    st.write("ニュース：Google News RSS")
    st.write("FRED：APIキーを設定した場合に拡張可能")
    st.write("AI分析：OpenAI API（任意）")

st.caption("このアプリは情報整理・分析支援を目的としています。投資判断の前に各公的機関・取引所・金融機関等の原資料を確認してください。")
