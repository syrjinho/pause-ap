import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from openai import OpenAI
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import time
from duckduckgo_search import DDGS

# ---------------------------------------------------------
# 1. 페이지 설정
# ---------------------------------------------------------
st.set_page_config(
    page_title="PAUSE - The Art of Not Losing Money",
    page_icon="⏸️",
    layout="wide"
)

# ---------------------------------------------------------
# 2. 스타일(CSS) 설정
# ---------------------------------------------------------
st.markdown("""
    <style>
    .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    header[data-testid="stHeader"] { height: 2rem !important; }
    .dojo-box { 
        background-color: #262730; 
        border-radius: 10px; 
        padding: 15px; 
        margin-bottom: 20px; 
        border: 1px solid #444; 
        text-align: center; 
    }
    .belt-icon { font-size: 40px; margin-bottom: 5px; }
    .belt-title { color: #FFFFFF; font-weight: bold; font-size: 18px; }
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
        border: none; 
        margin-top: 10px; 
    }
    </style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------
# 3. 세션 상태 초기화
# ---------------------------------------------------------
if 'xp' not in st.session_state:
    st.session_state.xp = 0
if 'total_saved' not in st.session_state:
    st.session_state.total_saved = 0
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False 

# ---------------------------------------------------------
# 4. 벨트 시스템 데이터
# ---------------------------------------------------------
BELTS = [
    {"limit": 100, "name": "Impulsive Novice", "color": "⚪", "msg": "Welcome to the Dojo."},
    {"limit": 300, "name": "Aware Observer", "color": "🟡", "msg": "You are starting to see."},
    {"limit": 600, "name": "Disciplined Trader", "color": "🔵", "msg": "Control is your weapon."},
    {"limit": 1000, "name": "Risk Manager", "color": "🟤", "msg": "You protect your capital."},
    {"limit": 999999, "name": "Grandmaster of Pause", "color": "⚫", "msg": "You have mastered the art."}
]

def get_current_belt(xp):
    for belt in BELTS:
        if xp < belt["limit"]:
            return belt
    return BELTS[-1]

# ---------------------------------------------------------
# 5. 사이드바 구성 (레벨 표시)
# ---------------------------------------------------------
st.sidebar.title("⏸️ PAUSE")
st.sidebar.markdown("### The Art of Not Losing Money")

current_belt = get_current_belt(st.session_state.xp)

st.sidebar.markdown("---")

# 안전한 문자열 포맷팅
belt_color = current_belt['color']
belt_name = current_belt['name']
belt_msg = current_belt['msg']
belt_limit = current_belt['limit']
curr_xp = st.session_state.xp

dojo_html = f"""
<div class="dojo-box">
    <div class="belt-icon">{belt_color}</div>
    <div class="belt-title">{belt_name}</div>
    <div style="color: #888; font-size: 12px; margin-top: 5px;">{belt_msg}</div>
    <div style="margin-top: 10px; font-weight: bold; color: #00FF99;">XP: {curr_xp} / {belt_limit}</div>
</div>
"""
st.sidebar.markdown(dojo_html, unsafe_allow_html=True)

# 프로그래스 바
limit_val = max(belt_limit, 1)
progress_val = min(curr_xp / limit_val, 1.0)
st.sidebar.progress(progress_val)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Tip:** Analyze (+10 XP) and Pause (+50 XP) to level up!")

# API Key 입력
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
else:
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")

if not api_key:
    st.warning("⬅️ Please enter API Key in the Sidebar to start")
    st.stop()

# ---------------------------------------------------------
# 6. 헬퍼 함수들
# ---------------------------------------------------------
@st.cache_data(ttl=600) 
def get_live_price(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='1d')
        if not hist.empty:
            return hist['Close'].iloc[-1]
        return 0.0
    except:
        return 0.0

def fetch_news(ticker):
    try:
        ddgs = DDGS()
        results = []
        try: 
            results = list(ddgs.news(keywords=f"{ticker} stock", region="wt-wt", safesearch="off", max_results=3))
        except: 
            results = []
        
        if not results:
            try: 
                results = list(ddgs.text(keywords=f"{ticker} stock news", region="wt-wt", safesearch="off", max_results=3))
            except: 
                results = []
                
        if results:
            summary = []
            for r in results:
                t = r.get('title', 'No Title')
                u = r.get('url', '#')
                summary.append(f"- [{t}]({u})")
            return "\n".join(summary)
        else: 
            return "No recent news found."
    except Exception as e: 
        return f"News search error: {str(e)}"

def fetch_market_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='6mo', interval='1d')
        if hist.empty: 
            return {'success': False, 'error': 'No data'}
        
        try: c_name = stock.info.get('longName', ticker)
        except: c_name = ticker 
        
        e_date = "Unknown"
        try:
            cal = stock.calendar
            if isinstance(cal, dict) and 'Earnings Date' in cal:
                 dates = cal['Earnings Date']
                 if dates: e_date = str(dates[0])
            elif not isinstance(cal, dict) and not cal.empty:
                e_date = cal.iloc[0][0].strftime('%Y-%m-%d')
        except:
            pass
            
        return {
            'success': True, 
            'history': hist, 
            'current_price': hist.iloc[-1]['Close'], 
            'earnings': e_date, 
            'company_name': c_name
        }
    except Exception as e: 
        return {'success': False, 'error': str(e)}

def calculate_hindsight(df, qty, current_price):
    if df is None: return 0.0, 0.0
    if len(df) < 6: return 0.0, 0.0
    
    try:
        past_price = df['Close'].iloc[-6] 
        diff = current_price - past_price
        pnl = diff * qty
        return past_price, pnl
    except:
        return 0.0, 0.0

# ---------------------------------------------------------
# 7. 메인 화면 구성
# ---------------------------------------------------------
st.title("⏸️ PAUSE")

# 입력창
risk_tolerance = st.selectbox("Risk Tolerance", ["Conservative", "Moderate", "Aggressive"], index=1)

col1, col2, col3 = st.columns(3)
with col1: 
    ticker_symbol = st.text_input("Ticker Symbol", value="NVDA").upper()
with col2: 
    quantity = st.number_input("Quantity (Shares)", min_value=1, value=100)
with col3:
    if ticker_symbol:
        lp = get_live_price(ticker_symbol)
        total_val = lp * quantity
        st.text_input("Est. Amount ($)", value=f"${total_val:,.2f}", disabled=True)
    else:
        st.text_input("Est. Amount ($)", value="$0.00", disabled=True)

# 🔥 [핵심 수정] Analyze 버튼 로직
# 버튼을 누르면 점수를 올리고, '즉시' rerunning 해서 사이드바 숫자를 업데이트함
if st.button("🔍 Analyze Trade (+10 XP)", use_container_width=True):
    st.session_state.xp += 10
    st.session_state.analyzed = True
    st.rerun()  # 이 코드가 있어야 버튼 누르자마자 10점이 올라간 화면이 보입니다!

# ---------------------------------------------------------
# 8. 분석 로직 실행
# ---------------------------------------------------------
if st.session_state.analyzed: 
    
    with st.spinner("Consulting the Master..."):
        try:
            # 데이터 가져오기
            m_data = fetch_market_data(ticker_symbol)
            if not m_data['success']: 
                st.error("Ticker Error: Data not found")
                st.stop()
            
            news_txt = fetch_news(ticker_symbol)
            df = m_data['history']
            curr_p = m_data['current_price']
            comp_n = m_data['company_name']
            
            # 기술적 지표
            df['RSI'] = ta.rsi(df['Close'], length=14)
            bb = ta.bbands(df['Close'], length=20, std=2)
            if bb is not None:
                df = pd.concat([df, bb], axis=1)
                
            rsi_val = df.iloc[-1].get('RSI', 50)
            
            # 볼린저 밴드 (안전 처리)
            try:
                bb_low = df.iloc[-1]['BBL_20_2.0']
                bb_high = df.iloc[-1]['BBU_20_2.0']
            except:
                bb_low = curr_p * 0.95
                bb_high = curr_p * 1.05

            past_p, hindsight_val = calculate_hindsight(df, quantity, curr_p)
            
            # -------------------------------------------------
            # AI 프롬프트 (안전하게 나누어 작성)
            # -------------------------------------------------
            lines = []
            lines.append(f"You are a strict Risk Manager. Risk Attitude: {risk_tolerance}.")
            lines.append(f"Ticker: {ticker_symbol}, Price: {curr_p}, RSI: {rsi_val}.")
            lines.append(f"News: {news_txt[:500]}") 
            lines.append("Task: Decide VERDICT (GO or WAIT).")
            lines.append("IMPORTANT: Even if WAIT, provide 'stop_loss_price' and 'target_price'. Do NOT output 0.00.")
            lines.append("RULES: Conservative(RSI>60->WAIT), Moderate(RSI>65->WAIT), Aggressive(RSI>75->WAIT).")
            lines.append('OUTPUT JSON: {"verdict": "GO/WAIT", "risk_color": "green/orange", "stop_loss_price": 0.0, "target_price": 0.0, "reasoning_simple": ["Reason 1", "Reason 2"]}')
            
            final_prompt = "\n".join(lines)
            
            # AI 호출
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": final_prompt}
                ],
                temperature=0.1,
                response_format={ "type": "json_object" }
            )
            
            raw_content = response.choices[0].message.content
            ai_result = json.loads(raw_content)
            
            # 결과값 보정
            sl_price = ai_result.get('stop_loss_price', 0.0)
            tp_price = ai_result.get('target_price', 0.0)
            
            if sl_price <= 0: sl_price = bb_low
            if tp_price <= 0: tp_price = bb_high
                
            # -------------------------------------------------
            # 결과 표시 UI
            # -------------------------------------------------
            
            # 1. 회사명
            h_html = f"""
            <div class="company-header">
                <p class="company-ticker">{ticker_symbol}</p>
                <p class="company-name">{comp_n}</p>
            </div>
            """
            st.markdown(h_html, unsafe_allow_html=True)
            
            # 2. 판결
            verdict = ai_result.get('verdict', 'WAIT')
            bg_c = "#FF4B4B"
            if verdict == "GO": bg_c = "#00CC7A"
            
            v_html = f"""
            <div class="verdict-box" style="background-color: {bg_c};">
                <h1 style="color: white; font-size: 50px; margin:0;">{verdict}</h1>
                <h3 style="color: white; margin:0;">DECISION FOR {risk_tolerance.upper()} MODE</h3>
            </div>
            """
            st.markdown(v_html, unsafe_allow_html=True)

            # 3. Pause 버튼 (WAIT일 때만)
            if verdict == "WAIT":
                if sl_price > 0 and sl_price < curr_p:
                    risk_unit = curr_p - sl_price
                    saved_amt = risk_unit * quantity
                else:
                    saved_amt = (curr_p * quantity) * 0.05
                
                b_text = f"✋ I decided to PAUSE (Save Risk ${saved_amt:,.0f} & +50 XP)"
                t_tip = f"Entry: ${curr_p:.2f}, Stop Loss: ${sl_price:.2f}"

                # 🔥 [핵심 수정] Pause 버튼 로직
                if st.button(b_text, type="primary", use_container_width=True, help=t_tip):
                    st.session_state.xp += 50
                    st.session_state.total_saved += saved_amt
                    st.session_state.analyzed = False 
                    
                    st.toast(f"✅ +50 XP Gained! Total XP: {st.session_state.xp}", icon="✨")
                    st.success(f"🧘 Excellent discipline. You avoided risk of ${saved_amt:,.0f}.")
                    
                    time.sleep(2)
                    st.rerun() # 여기서도 즉시 새로고침해서 점수 반영

            # 4. 수치
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("Current Price", f"${curr_p:.2f}")
            mc2.metric("Suggested Stop Loss", f"${sl_price:.2f}")
            mc3.metric("Suggested Target", f"${tp_price:.2f}")
            
            st.divider()
            
            # 5. 이유
            st.subheader("🧐 Why?")
            reasons = ai_result.get('reasoning_simple', [])
            if isinstance(reasons, list):
                for r in reasons:
                    st.markdown(f"- {r}")
            else:
                st.write(reasons)

            # 6. 뉴스
            st.divider()
            with st.expander("📰 Show Latest News & Earnings", expanded=False):
                st.markdown(f"**📅 Next Earnings Date:** {m_data['earnings']}")
                st.markdown("---")
                st.markdown(news_txt)

            # 7. 차트
            st.divider()
            st.subheader("Chart")
            c_df = df.tail(30)
            
            candle_stick = go.Candlestick(
                x=c_df.index, 
                open=c_df['Open'], 
                high=c_df['High'], 
                low=c_df['Low'], 
                close=c_df['Close']
            )
            fig = go.Figure(data=[candle_stick])
            fig.update_layout(height=400, margin=dict(l=0,r=0,t=0,b=0))
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error("🚨 System Error Occurred")
            st.error(f"Details: {e}")
            if 'raw_content' in locals():
                st.code(raw_content)