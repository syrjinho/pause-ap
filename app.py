import streamlit as st
import yfinance as yf
import pandas as pd
from openai import OpenAI
import plotly.graph_objects as go
import json
import time
from duckduckgo_search import DDGS
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
<p style='font-size: 14px; color: #888; margin-top: 0px;'>Welcome to Dojo</p>
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

# [수정] 따옴표 오류 방지를 위해 들여쓰기 조정
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

if not api_key:
    st.warning("Enter API Key")
    st.stop()

# ---------------------------------------------------------
# 6. 데이터 함수
# ---------------------------------------------------------

@st.cache_data(ttl=600)
def get_price(ticker):
    try: 
        return yf.Ticker(ticker).history(period='5d')['Close'].iloc[-1]
    except: return 0.0

def get_news(ticker):
    try:
        ddgs = DDGS()
        r = list(ddgs.text(keywords=f"{ticker} stock news", max_results=3))
        if not r: return []
        return [{'title': x.get('title',''), 'url': x.get('href', x.get('url',''))} for x in r]
    except:
        return []

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
                if isinstance(cal, dict):
                    dates = cal.get('Earnings Date') or cal.get('Earnings High')
                    if dates: earnings = str(dates[0].date()) if hasattr(dates[0], 'date') else str(dates[0])
                elif not cal.empty:
                    val = cal.iloc[0][0]
                    earnings = str(val.date()) if hasattr(val, 'date') else str(val)
        except:
            earnings = "N/A"

        return {
            'hist': h, 
            'price': h['Close'].iloc[-1], 
            'name': name,
            'earnings': earnings
        }
    except Exception as e:
        print(f"Data error: {e}")
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
with c1: sym = st.text_input("Ticker", "NVDA").upper()
with c2: qty = st.number_input("Qty", 1, value=100)
with c3:
    curr = get_price(sym) if sym else 0
    st.text_input("Est. $", f"${curr*qty:,.0f}", disabled=True)

# 버튼 1: Analyze
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
        
        # --- 지표 계산 ---
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
        news_text = "\n".join([f"- {n['title']}" for n in news_items]) if news_items else "No recent news."
        
        # --- AI 프롬프트 ---
        sys_msg = "You are a helpful assistant. Output valid JSON only."
        user_msg = f"""
        Risk Profile: {risk}
        Ticker: {sym}
        Current Price: {curr_price:.2f}
        RSI: {rsi_val:.1f}
        Bollinger Lower: {bbl_val:.2f}
        Bollinger Upper: {bbu_val:.2f}
        News Headlines:
        {news_text[:500]}

        TASK:
        1. Decide VERDICT (GO or WAIT).
        2. Set 'stop_loss' and 'target'. 
        3. Provide 'reasoning' (3 strings).

        STRICT RULES:
        - Conservative: WAIT if RSI > 60.
        - Moderate: WAIT if RSI > 65.
        - Aggressive: WAIT if RSI > 75.

        OUTPUT JSON FORMAT:
        {{
          "verdict": "GO",
          "stop_loss": 100.0,
          "target": 120.0,
          "reasoning": ["Tech...", "News...", "Risk..."]
        }}
        """
        
        try:
            client = OpenAI(api_key=api_key)
            res = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": user_msg}
                ],
                response_format={"type": "json_object"}
            )
            ai = json.loads(res.choices[0].message.content)
        except Exception as e:
            st.error(f"AI Connection Error: {e}")
            st.stop()
            
        final_sl = ai.get('stop_loss', 0.0)
        final_tp = ai.get('target', 0.0)
        
        if final_sl <= 0.1: final_sl = bbl_val
        if final_tp <= 0.1: final_tp = bbu_val
        
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
            
            st.button(
                f"✋ I decided to PAUSE (Save ${saved:,.0f} & +50 XP)", 
                type="primary", 
                use_container_width=True,
                on_click=cb_pause,
                args=(saved,)
            )
            
        m1, m2, m3 = st.columns(3)
        m1.metric("Current Price", f"${curr_price:.2f}")
        m2.metric("Suggested Stop Loss", f"${final_sl:.2f}")
        m3.metric("Suggested Target", f"${final_tp:.2f}")
        
        st.divider()
        
        st.subheader("🧐 Why?")
        reasons = ai.get('reasoning', [])
        if reasons:
            for r in reasons:
                st.markdown(f"- {r}")
        else:
            st.write("No reasoning provided.")
            
        st.divider()
        with st.expander("📰 Recent News & Earnings Date", expanded=True):
            st.markdown(f"**📅 Next Earnings Date:** {d['earnings']}")
            st.markdown("---")
            if news_items:
                for n in news_items:
                    st.markdown(f"- [{n['title']}]({n['url']})")
            else:
                st.write("No recent news found.")
            
        st.divider()
        st.subheader("Chart")
        fig = go.Figure(data=[go.Candlestick(
            x=df.index,
            open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close']
        )])
        fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0))
        st.plotly_chart(fig, use_container_width=True)