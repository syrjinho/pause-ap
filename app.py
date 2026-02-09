import streamlit as st
import yfinance as yf
import pandas as pd
from openai import OpenAI
import plotly.graph_objects as go
import json
import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# ---------------------------------------------------------
# 1. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(page_title="PAUSE", page_icon="⏸️", layout="wide")

# ---------------------------------------------------------
# 2. 스타일 설정 (CSS)
# ---------------------------------------------------------
st.markdown("""
<style>
.block-container { padding-top: 1rem; padding-bottom: 5rem; }
section[data-testid="stSidebar"] .block-container { padding-top: 1rem; }
.dojo-box { 
    background-color: #262730; 
    border-radius: 10px; 
    padding: 15px; 
    margin-bottom: 20px; 
    border: 1px solid #444; 
    text-align: center; 
}
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
.stButton>button { 
    background-color: #00FF99; 
    color: black; 
    font-weight: bold; 
    border-radius: 10px; 
    height: 50px; 
    font-size: 20px; 
    width: 100%; 
}
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. 세션 및 콜백 함수
# ---------------------------------------------------------
if 'xp' not in st.session_state: st.session_state.xp = 0
if 'total_saved' not in st.session_state: st.session_state.total_saved = 0
if 'analyzed' not in st.session_state: st.session_state.analyzed = False
if 'msg' not in st.session_state: st.session_state.msg = ""

def cb_analyze():
    st.session_state.xp += 10
    st.session_state.analyzed = True
    st.session_state.msg = ""

def cb_pause(saved_val):
    st.session_state.xp += 50
    st.session_state.total_saved += saved_val
    st.session_state.analyzed = False
    st.session_state.msg = f"🧘 Excellent! Saved risk: ${saved_val:,.0f}"

# ---------------------------------------------------------
# 4. 벨트 시스템
# ---------------------------------------------------------
BELTS = [
    {"limit": 100, "name": "Novice", "color": "⚪"},
    {"limit": 300, "name": "Observer", "color": "🟡"},
    {"limit": 600, "name": "Trader", "color": "🔵"},
    {"limit": 1000, "name": "Risk Manager", "color": "🟤"},
    {"limit": 999999, "name": "Grandmaster", "color": "⚫"}
]
def get_belt(xp):
    for b in BELTS:
        if xp < b["limit"]: return b
    return BELTS[-1]

# ---------------------------------------------------------
# 5. 사이드바
# ---------------------------------------------------------
st.sidebar.markdown("""
<h1 style='margin-bottom: 0px;'>⏸️ PAUSE</h1>
<p style='font-size: 14px; color: #888; margin-top: 0px;'>Absolutely not. We've seen this before.</p>
""", unsafe_allow_html=True)

belt = get_belt(st.session_state.xp)
limit = max(belt['limit'], 1)

st.sidebar.markdown(f"""
<div class="dojo-box">
    <div style="font-size:40px;">{belt['color']}</div>
    <div style="font-weight:bold; color:white;">{belt['name']}</div>
    <div style="color:#00FF99; margin-top:10px;">XP: {st.session_state.xp} / {limit}</div>
</div>
""", unsafe_allow_html=True)
st.sidebar.progress(min(st.session_state.xp / limit, 1.0))

st.sidebar.markdown("""
<div style="background-color: #333; padding: 15px; border-radius: 10px; font-size: 13px; color: #eee; margin-top: 10px; border: 1px solid #555;">
<strong style="color: #00FF99; font-size: 14px;">Road to Grandmaster 🥋</strong>
<ul style="padding-left: 15px; margin-top: 8px; line-height: 1.6;">
<li>🔍 <b>+10 XP</b>: Analyze before you act.</li>
<li>✋ <b>+50 XP</b>: Choose to PAUSE.</li>
</ul>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")

if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")

st.sidebar.markdown("---")
st.sidebar.caption("⚠️ **Disclaimer**: Not financial advice. For educational purposes only. Do your own research before trading.")

if not api_key:
    st.warning("Enter API Key to start")
    st.stop()

# ---------------------------------------------------------
# 6. 데이터 함수
# ---------------------------------------------------------
def get_price(ticker):
    if not ticker or len(ticker) < 2: return 0.0
    try: 
        ticker = ticker.strip().upper()
        t = yf.Ticker(ticker)
        h = t.history(period='1d')
        if not h.empty: return h['Close'].iloc[-1]
        if hasattr(t, 'fast_info') and t.fast_info.last_price:
            return t.fast_info.last_price
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
                pubDate = item.find('pubDate').text if item.find('pubDate') is not None else ""
                news_list.append({'title': title, 'url': link, 'published': pubDate})
    except:
        pass
    return news_list

def get_data(ticker):
    try:
        ticker = ticker.strip().upper()
        t = yf.Ticker(ticker)
        h = t.history(period='3mo')
        if h.empty: return None
        
        try:
            name = t.info.get('longName', ticker)
        except:
            name = ticker

        earnings = "N/A"
        try:
            cal = t.calendar
            if cal is not None:
                if isinstance(cal, pd.DataFrame) and not cal.empty and 'Earnings Date' in cal.index:
                    d_list = cal.loc['Earnings Date'].tolist()
                    earnings = str(d_list[0].date()) if hasattr(d_list[0], 'date') else str(d_list[0])
                elif isinstance(cal, dict) and 'Earnings Date' in cal:
                    d_list = cal['Earnings Date']
                    earnings = str(d_list[0].date()) if hasattr(d_list[0], 'date') else str(d_list[0])

            if earnings == "N/A":
                ts = t.info.get('earningsTimestamp') or t.info.get('nextEarningsDate')
                if ts:
                    if ts > 1e11: ts /= 1000
                    earnings = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
        except:
            earnings = "N/A"

        return {
            'hist': h, 
            'price': h['Close'].iloc[-1], 
            'name': name,
            'earnings': earnings
        }
    except:
        return None

# ---------------------------------------------------------
# 7. 메인 화면
# ---------------------------------------------------------
st.title("⏸️ PAUSE")

if st.session_state.msg:
    st.success(st.session_state.msg)
    st.toast("XP Gained!", icon="✨")
    st.session_state.msg = ""

risk = st.selectbox("Risk", ["Conservative", "Moderate", "Aggressive"], index=1)

c1, c2, c3 = st.columns(3)
with c1: sym = st.text_input("Ticker", "NVDA").strip().upper()
with c2: qty = st.number_input("Qty", 1, value=100)
with c3:
    curr = get_price(sym)
    st.text_input("Est. $", f"${curr*qty:,.0f}", disabled=True)

st.button("🔍 Analyze (+10 XP)", use_container_width=True, on_click=cb_analyze)

# ---------------------------------------------------------
# 8. 분석 로직
# ---------------------------------------------------------
if st.session_state.analyzed:
    with st.spinner("Analyzing..."):
        d = get_data(sym)
        
        if not d:
            st.error(f"Error fetching data for {sym}. Please try again.")
            st.session_state.analyzed = False 
            st.stop()
            
        df = d['hist']
        curr_price = d['price']
        
        st.markdown(f"""
        <div class="company-header">
            <p class="company-ticker">{sym}</p>
            <p class="company-name">{d['name']}</p>
        </div>
        """, unsafe_allow_html=True)
        
        try:
            delta = df['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['RSI'] = 100 - (100 / (1 + rs))
            
            sma = df['Close'].rolling(20).mean()
            std = df['Close'].rolling(20).std()
            df['BBL'] = sma - (2 * std)
            df['BBU'] = sma + (2 * std)
            
            rsi_val = df['RSI'].iloc[-1]
            if pd.isna(rsi_val): rsi_val = 50
            bbl_val = df['BBL'].iloc[-1]
            if pd.isna(bbl_val): bbl_val = curr_price * 0.95
            bbu_val = df['BBU'].iloc[-1]
            if pd.isna(bbu_val): bbu_val = curr_price * 1.05
        except:
            rsi_val = 50
            bbl_val = curr_price * 0.95
            bbu_val = curr_price * 1.05
        
        news_items = get_news(sym)
        if news_items:
            news_text = "\n".join([f"- {n['title']}" for n in news_items])
        else:
            news_text = "No specific news found."

        sys_msg = "You are a helpful assistant. Output valid JSON only."
        # [수정 1] AI에게 명확하게 '3 short bullet points'라고 요청
        user_msg = f"""
        Risk Profile: {risk}
        Ticker: {sym}
        Current Price: {curr_price:.2f}
        RSI: {rsi_val:.1f}
        Bollinger Lower: {bbl_val:.2f}
        Bollinger Upper: {bbu_val:.2f}
        News: {news_text[:1000]}
        TASK: Decide VERDICT (GO or WAIT), set stop_loss, target, and reasoning (3 short bullet points).
        """
        
        try:
            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "system", "content": sys_msg}, {"role": "user", "content": user_msg}],
                response_format={"type": "json_object"}
            )
            ai = json.loads(res.choices[0].message.content)
        except Exception as e:
            st.error(f"AI Connection Error: {e}")
            st.stop()
            
        final_sl = ai.get('stop_loss', bbl_val)
        final_tp = ai.get('target', bbu_val)
        verdict = ai.get('verdict', 'WAIT')
        color = "#00CC7A" if verdict == "GO" else "#FF4B4B"
        
        st.markdown(f"""
        <div class="verdict-box" style="background-color:{color};">
            <h1 style="color:white; margin:0;">{verdict}</h1>
        </div>
        """, unsafe_allow_html=True)
        
        if verdict == "WAIT":
            saved = (curr_price - final_sl) * qty
            if saved < 0: saved = curr_price * qty * 0.05
            st.button(f"✋ I decided to PAUSE (Save ${saved:,.0f} & +50 XP)", type="primary", use_container_width=True, on_click=cb_pause, args=(saved,))
            
        m1, m2, m3 = st.columns(3)
        m1.metric("Current Price", f"${curr_price:.2f}")
        m2.metric("Stop Loss", f"${final_sl:.2f}")
        m3.metric("Target", f"${final_tp:.2f}")
        
        st.divider()
        with st.expander("🧐 Why? & Recent News", expanded=True):
            st.markdown(f"**📅 Next Earnings Date:** {d['earnings']}")
            st.markdown("---")
            
            reasons = ai.get('reasoning', [])
            # [수정 2] 만약 AI가 여전히 줄글(String)로 주면 마침표(.) 단위로 잘라서 리스트로 변환
            if isinstance(reasons, str): 
                reasons = [r.strip() for r in reasons.split('.') if r.strip()]
                
            for r in reasons: st.markdown(f"- {r}")
            st.markdown("---")
            if news_items:
                for n in news_items: st.markdown(f"- [{n['title']}]({n['url']})")
        
        st.subheader("Chart")
        fig = go.Figure(data=[go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'])])
        fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)