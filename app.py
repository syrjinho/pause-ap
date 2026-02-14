import streamlit as st
import yfinance as yf
import pandas as pd
from openai import OpenAI
import plotly.graph_objects as go
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# ---------------------------------------------------------
# 1. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="PAUSE", page_icon="⏸️", layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------
# 2. 스타일 설정 (CSS)
# ---------------------------------------------------------
st.markdown("""
<style>
/* 사이드바 숨김 */
[data-testid="stSidebar"] { display: none; }

/* 상단 여백 조정 */
.block-container { 
    padding-top: 2rem; 
    padding-bottom: 5rem; 
}

/* 로고 버튼 스타일 */
div.stButton.logo-btn > button {
    background-color: transparent !important;
    border: none !important;
    color: #FFFFFF !important;
    font-size: 50px !important;
    font-weight: 900 !important;
    padding: 0px !important;
    margin: 0px !important;
    line-height: 1.0 !important;
    text-align: left !important;
    box-shadow: none !important;
    width: auto !important;
}
div.stButton.logo-btn > button:hover {
    color: #00FF99 !important;
    cursor: pointer;
}
div.stButton.logo-btn > button:active {
    color: #00cc7a !important;
    background-color: transparent !important;
}

/* 서브타이틀 */
.main-subtitle {
    font-size: 16px;
    color: #888;
    margin-top: -15px;
    margin-bottom: 30px;
    font-weight: 400;
}

/* 박스 스타일 */
.company-header { 
    padding: 20px; 
    background-color: #1E1E1E; 
    border-radius: 20px; 
    text-align: center; 
    margin-bottom: 20px; 
    border: 1px solid #333; 
}
.company-ticker { 
    font-size: 50px !important; 
    font-weight: 900; 
    color: #00FF99; 
    margin: 0; 
    line-height: 1.0; 
}
.company-name { 
    font-size: 24px !important; 
    color: #DDDDDD; 
    margin: 5px 0 0 0; 
    font-weight: 500; 
}
.verdict-box { 
    padding: 25px; 
    border-radius: 15px; 
    text-align: center; 
    margin-bottom: 20px; 
}

/* 액션 버튼 스타일 */
div.stButton.action-btn > button { 
    background-color: #00FF99; 
    color: black; 
    font-weight: bold; 
    border-radius: 10px; 
    height: 50px; 
    font-size: 20px; 
    width: 100%; 
    border: none;
}
div.stButton.action-btn > button:hover {
    background-color: #00cc7a;
    color: black;
}

/* 탭 스타일 */
.stTabs [data-baseweb="tab-list"] { gap: 20px; }
.stTabs [data-baseweb="tab"] {
    height: 50px;
    white-space: pre-wrap;
    background-color: #0E1117;
    border-radius: 8px 8px 0 0;
    gap: 1px;
    padding-top: 10px;
    padding-bottom: 10px;
}
.stTabs [aria-selected="true"] {
    background-color: #262730;
    color: #00FF99 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. 세션 및 콜백
# ---------------------------------------------------------
if 'analyzed_short' not in st.session_state: st.session_state.analyzed_short = False
if 'analyzed_swing' not in st.session_state: st.session_state.analyzed_swing = False

def cb_home():
    st.session_state.analyzed_short = False
    st.session_state.analyzed_swing = False

def cb_analyze_short():
    st.session_state.analyzed_short = True
    st.session_state.analyzed_swing = False 

def cb_analyze_swing():
    st.session_state.analyzed_swing = True
    st.session_state.analyzed_short = False

# ---------------------------------------------------------
# 4. 헤더
# ---------------------------------------------------------
col_h1, col_h2 = st.columns([3, 1])

with col_h1:
    st.markdown('<div class="logo-container">', unsafe_allow_html=True)
    if st.button("⏸️ PAUSE", on_click=cb_home, key="home_btn"):
        pass
    st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <style>
    div[data-testid="stBaseButton-home_btn"] {
        background-color: transparent !important;
        border: none !important;
        padding: 0 !important;
    }
    div[data-testid="stBaseButton-home_btn"] > button {
        background-color: transparent !important;
        border: none !important;
        color: #FFFFFF !important;
        font-size: 60px !important;
        font-weight: 900 !important;
        text-align: left !important;
        padding: 0px !important;
        margin-top: -20px !important;
        box-shadow: none !important;
    }
    div[data-testid="stBaseButton-home_btn"] > button:hover {
        color: #00FF99 !important;
    }
    div[data-testid="stBaseButton-home_btn"] > button:active {
        color: #00cc7a !important;
        background-color: transparent !important;
    }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="main-subtitle">Think Before You Trade</div>', unsafe_allow_html=True)

with col_h2:
    if "OPENAI_API_KEY" in st.secrets:
        api_key = st.secrets["OPENAI_API_KEY"]
    else:
        api_key = st.text_input("Enter OpenAI API Key", type="password")

if not api_key:
    st.warning("Please configure your API Key in secrets.toml or enter it above.")
    st.stop()

# ---------------------------------------------------------
# 5. 데이터 함수
# ---------------------------------------------------------
def get_price(ticker):
    if not ticker or len(ticker) < 2: return 0.0
    try: 
        ticker = ticker.strip().upper()
        t = yf.Ticker(ticker)
        if hasattr(t, 'fast_info') and t.fast_info.last_price:
             return t.fast_info.last_price
        h = t.history(period='1d')
        if not h.empty: return h['Close'].iloc[-1]
        return 0.0
    except: 
        return 0.0

def get_news(ticker):
    news_list = []
    try:
        url = f"https://news.google.com/rss/search?q={ticker}+stock+finance&hl=en-US&gl=US&ceid=US:en"
        resp = requests.get(url, timeout=3)
        if resp.status_code == 200:
            root = ET.fromstring(resp.content)
            for item in root.findall('./channel/item')[:5]:
                title = item.find('title').text if item.find('title') is not None else "No Title"
                link = item.find('link').text if item.find('link') is not None else "#"
                news_list.append({'title': title, 'url': link})
    except:
        pass
    return news_list

def get_macro_data():
    try:
        tickers = ["SPY", "^VIX", "^TNX"]
        data = yf.download(tickers, period="5d", progress=False)['Close']
        if data.empty: return None
        last_row = data.iloc[-1]
        try:
            spy_price = float(last_row['SPY'])
            vix = float(last_row['^VIX'])
            tnx = float(last_row.get('^TNX', 0))
        except:
            spy_price = float(last_row.get('SPY', 0))
            vix = float(last_row.get('^VIX', 0))
            tnx = float(last_row.get('^TNX', 0))
        return {"spy_price": spy_price, "vix": vix, "tnx": tnx}
    except:
        return None

def get_data(ticker):
    try:
        ticker = ticker.strip().upper()
        t = yf.Ticker(ticker)
        h = t.history(period='6mo') 
        if h.empty: return None
        
        info = t.info
        name = info.get('longName', ticker)

        earnings_warning = False
        earnings_date_str = "N/A"
        try:
            cal = t.calendar
            if cal is not None and isinstance(cal, dict) and 'Earnings Date' in cal:
                e_date = cal['Earnings Date'][0]
                earnings_date_str = str(e_date.date())
                days_diff = (e_date.date() - datetime.now().date()).days
                if 0 <= days_diff <= 5: 
                    earnings_warning = True
        except:
            pass

        fundamentals = {
            "market_cap": info.get('marketCap'),
            "trailing_pe": info.get('trailingPE'),
            "revenue_growth": info.get('revenueGrowth'),
            "profit_margins": info.get('profitMargins'),
        }

        whales = []
        try:
            inst = t.institutional_holders
            if inst is not None and not inst.empty:
                if 'Holder' in inst.columns:
                    whales = inst['Holder'].head(3).tolist()
                else:
                    whales = inst.iloc[:3, 0].tolist()
        except:
            pass

        return {
            'hist': h, 
            'price': h['Close'].iloc[-1], 
            'name': name,
            'earnings_warning': earnings_warning,
            'earnings_date': earnings_date_str,
            'fund': fundamentals,
            'whales': whales
        }
    except:
        return None

def safe_display_list(data_list, fallback_msg):
    if isinstance(data_list, list):
        for item in data_list: st.markdown(f"- {item}")
    elif isinstance(data_list, str): st.markdown(f"- {data_list}")
    else: st.markdown(f"- {fallback_msg}")

def safe_float(val, fallback):
    try:
        if val is None: return fallback
        if isinstance(val, str) and "N/A" in val: return fallback
        return float(val)
    except:
        return fallback

# ---------------------------------------------------------
# 6. 메인 탭 구성
# ---------------------------------------------------------
tab_short, tab_swing = st.tabs(["🚀 Short-Term (1-3 Days)", "🐢 Swing (1 Week - 3 Months)"])

# =========================================================
# TAB 1: SHORT-TERM
# =========================================================
with tab_short:
    c1, c2, c3 = st.columns(3)
    with c1: sym_s = st.text_input("Ticker", "TSLA", key="t_s", on_change=cb_analyze_short).strip().upper()
    with c2: qty_s = st.number_input("Qty", 1, value=100, key="q_s")
    with c3:
        curr_s = get_price(sym_s)
        st.text_input("Est. $", f"${curr_s*qty_s:,.0f}", disabled=True, key="e_s")

    st.markdown('<div class="stButton action-btn">', unsafe_allow_html=True)
    st.button("⚡ Analyze Momentum", use_container_width=True, on_click=cb_analyze_short, key="btn_s")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.analyzed_short:
        with st.spinner("Scanning..."):
            d = get_data(sym_s)
            if not d: st.error("Error fetching data.")
            else:
                df = d['hist']
                curr_price = d['price']
                st.markdown(f"""<div class="company-header"><p class="company-ticker">{sym_s}</p><p class="company-name">{d['name']}</p></div>""", unsafe_allow_html=True)
                
                if d['earnings_warning']: st.error(f"⚠️ Earnings Report on {d['earnings_date']}")

                try:
                    df['EMA5'] = df['Close'].ewm(span=5, adjust=False).mean()
                    ema5_val = df['EMA5'].iloc[-1]
                    trend_str = "BULLISH" if curr_price > ema5_val else "BEARISH"
                    
                    low_14 = df['Low'].rolling(14).min()
                    high_14 = df['High'].rolling(14).max()
                    stoch_k = 100 * ((df['Close'] - low_14) / (high_14 - low_14))
                    stoch_k = stoch_k.iloc[-1]
                    
                    vol_sma = df['Volume'].rolling(20).mean()
                    vol_ratio = (df['Volume'].iloc[-1] / vol_sma.iloc[-1]) * 100
                    
                    is_green = df['Close'].iloc[-1] > df['Open'].iloc[-1]
                except:
                    ema5_val = curr_price
                    stoch_k = 50
                    vol_ratio = 100
                    trend_str = "Unknown"
                    is_green = True

                news_items = get_news(sym_s)
                news_text = "\n".join([f"- {n['title']}" for n in news_items]) if news_items else "No news."
                macro = get_macro_data()
                macro_txt = f"VIX: {macro['vix']:.2f}" if macro else "VIX: N/A"

                sys_msg = "You are a High-Frequency Trader. Predict if stock will be GREEN TOMORROW. Output JSON: {verdict, entry_price, target_tomorrow, stop_loss, reasoning_list}. IMPORTANT: 'verdict' MUST be 'GO' or 'WAIT' (Do not use 'GREEN')."
                user_msg = f"Analyze {sym_s}. Price ${curr_price}, EMA5 ${ema5_val} ({trend_str}), Stoch {stoch_k:.1f}, Vol {vol_ratio:.0f}%, Candle {'GREEN' if is_green else 'RED'}, {macro_txt}. News: {news_text[:500]}"

                try:
                    client = OpenAI(api_key=api_key)
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], response_format={"type": "json_object"})
                    ai = json.loads(res.choices[0].message.content)
                except: st.stop()

                final_tp = safe_float(ai.get('target_tomorrow'), curr_price * 1.02)
                final_sl = safe_float(ai.get('stop_loss'), curr_price * 0.98)
                verdict = ai.get('verdict', 'WAIT')
                if verdict not in ["GO", "WAIT"]: verdict = "GO" if "GO" in verdict else "WAIT"
                color = "#00FF99" if verdict == "GO" else "#FF4B4B"

                # [FIX] "NOW" 텍스트 삭제
                st.markdown(f"""<div class="verdict-box" style="background-color:{color}; color:black;"><h1 style="margin:0;">{verdict}</h1></div>""", unsafe_allow_html=True)
                
                st.markdown('<div class="stButton action-btn">', unsafe_allow_html=True)
                # [FIX] 어떤 결과가 나와도 Check Another Stock 버튼 표시
                st.button("🔄 Check Another Stock", type="secondary", use_container_width=True, on_click=cb_home, key="reset_s")
                st.markdown('</div>', unsafe_allow_html=True)

                c1, c2, c3 = st.columns(3)
                c1.metric("Current", f"${curr_price:.2f}")
                c2.metric("Target", f"${final_tp:.2f}")
                c3.metric("Stop Loss", f"${final_sl:.2f}")
                
                st.divider()
                st.subheader("📝 Analysis")
                safe_display_list(ai.get('reasoning_list'), "No data.")
                
                fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
                fig.add_trace(go.Scatter(x=df.index, y=df['EMA5'], line=dict(color='orange'), name='EMA 5'))
                fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)

# =========================================================
# TAB 2: SWING
# =========================================================
with tab_swing:
    risk = st.selectbox("Risk Profile", ["Conservative", "Moderate", "Aggressive"], index=1)
    
    c1, c2, c3 = st.columns(3)
    with c1: sym_w = st.text_input("Ticker", "NVDA", key="t_w", on_change=cb_analyze_swing).strip().upper()
    with c2: qty_w = st.number_input("Qty", 1, value=100, key="q_w")
    with c3:
        curr_w = get_price(sym_w)
        st.text_input("Est. $", f"${curr_w*qty_w:,.0f}", disabled=True, key="e_w")

    st.markdown('<div class="stButton action-btn">', unsafe_allow_html=True)
    st.button("🐢 Analyze Swing", use_container_width=True, on_click=cb_analyze_swing, key="btn_w")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.session_state.analyzed_swing:
        with st.spinner("Analyzing..."):
            d = get_data(sym_w)
            if not d: st.error("Error.")
            else:
                df = d['hist']
                curr_price = d['price']
                fund = d['fund']
                whales = d['whales']
                st.markdown(f"""<div class="company-header"><p class="company-ticker">{sym_w}</p><p class="company-name">{d['name']}</p></div>""", unsafe_allow_html=True)

                try:
                    delta = df['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                    rs = gain / loss
                    df['RSI'] = 100 - (100 / (1 + rs))
                    rsi_val = df['RSI'].iloc[-1]
                    
                    sma = df['Close'].rolling(20).mean()
                    std = df['Close'].rolling(20).std()
                    bbl_val = sma.iloc[-1] - (2 * std.iloc[-1])
                    bbu_val = sma.iloc[-1] + (2 * std.iloc[-1])
                    
                    vol_ratio = (df['Volume'].iloc[-1] / df['Volume'].rolling(20).mean().iloc[-1]) * 100
                except:
                    rsi_val = 50
                    bbl_val = curr_price * 0.95
                    bbu_val = curr_price * 1.05
                    vol_ratio = 100

                macro = get_macro_data()
                macro_txt = f"VIX: {macro['vix']:.2f}" if macro else "N/A"
                
                mk_cap = (fund['market_cap']/1e9) if fund['market_cap'] else 0
                pe = fund['trailing_pe'] if fund['trailing_pe'] else 0
                whale_str = ", ".join(whales) if whales else "None"

                sys_msg = "You are a Swing Trader. Identify high-probability setups. Output JSON: {verdict, stop_loss, target, fund_analysis, tech_analysis, conclusion}. IMPORTANT: 'verdict' MUST be 'GO' or 'WAIT'."
                user_msg = f"Analyze {sym_w}. Risk {risk}. Cap ${mk_cap:.1f}B, P/E {pe}, Whales: {whale_str}. RSI {rsi_val:.1f}, Vol {vol_ratio:.0f}%. Market {macro_txt}. Decide GO/WAIT."

                try:
                    client = OpenAI(api_key=api_key)
                    res = client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}], response_format={"type": "json_object"})
                    ai = json.loads(res.choices[0].message.content)
                except: st.stop()

                final_sl = safe_float(ai.get('stop_loss'), bbl_val)
                final_tp = safe_float(ai.get('target'), bbu_val)
                verdict = ai.get('verdict', 'WAIT')
                if verdict not in ["GO", "WAIT"]: verdict = "GO" if "GO" in verdict else "WAIT"
                
                color = "#00CC7A" if verdict == "GO" else "#FF4B4B"

                st.markdown(f"""<div class="verdict-box" style="background-color:{color};"><h1 style="color:white; margin:0;">{verdict}</h1></div>""", unsafe_allow_html=True)
                
                st.markdown('<div class="stButton action-btn">', unsafe_allow_html=True)
                # [FIX] Swing 탭에서도 항상 Check Another Stock만 표시
                st.button("🔄 Check Another Stock", type="secondary", use_container_width=True, on_click=cb_home, key="reset_w_go")
                st.markdown('</div>', unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Current", f"${curr_price:.2f}")
                c2.metric("Stop Loss", f"${final_sl:.2f}")
                c3.metric("Target", f"${final_tp:.2f}")
                
                st.divider()
                with st.expander("🧐 Full Report", expanded=True):
                    if whales: st.info(f"🐳 **Whales:** {whale_str}")
                    st.markdown("---")
                    safe_display_list(ai.get('fund_analysis'), "No Data")
                    st.markdown("---")
                    safe_display_list(ai.get('tech_analysis'), "No Data")
                    st.markdown("---")
                    st.subheader("🏁 Conclusion")
                    safe_display_list(ai.get('conclusion'), "No Data")
                
                fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
                fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0))
                st.plotly_chart(fig, use_container_width=True)