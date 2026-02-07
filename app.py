import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
from openai import OpenAI
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import traceback

# --- Page Configuration ---
st.set_page_config(page_title="PAUSE - Risk Manager", page_icon="⏸️", layout="wide")

# --- Custom CSS ---
st.markdown("""
    <style>
    .big-font { font-size: 24px !important; font-weight: bold; }
    
    .company-header {
        padding: 30px;
        background-color: #1E1E1E;
        border-radius: 20px;
        text-align: center;
        margin-bottom: 25px;
        border: 1px solid #333;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .company-ticker {
        font-size: 80px !important;
        font-weight: 900;
        color: #00FF99;
        margin: 0;
        line-height: 1.0;
    }
    .company-name {
        font-size: 40px !important;
        color: #DDDDDD;
        margin: 10px 0 0 0;
        font-weight: 500;
    }

    .verdict-box {
        padding: 30px;
        border-radius: 15px;
        text-align: center;
        margin-bottom: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.3);
    }
    
    .hindsight-box {
        padding: 25px;
        border-radius: 12px;
        text-align: center;
        margin: 20px 0;
        font-size: 22px;
        font-weight: bold;
        line-height: 1.5;
        box-shadow: 0 4px 10px rgba(0,0,0,0.2);
        border: 2px solid rgba(255,255,255,0.1);
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
    }
    .stButton>button:hover {
        background-color: #00CC7A;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

# --- Sidebar ---
st.sidebar.title("⏸️ PAUSE")
st.sidebar.markdown("### Pause Before You Trade")
st.sidebar.info("💡 **Note:** PAUSE is optimized for **1-2 Week Swing Traders**.") 

# API Key Handling
if "OPENAI_API_KEY" in st.secrets:
    api_key = st.secrets["OPENAI_API_KEY"]
    st.sidebar.success("✅ API Key Loaded!")
else:
    api_key = st.sidebar.text_input("OpenAI API Key", type="password")

if not api_key:
    st.sidebar.warning("⬅️ Please enter API Key to start")
    st.stop()

# --- User Inputs ---
risk_tolerance = st.sidebar.selectbox("Risk Tolerance", ["Conservative", "Moderate", "Aggressive"])
ticker_symbol = st.sidebar.text_input("Ticker Symbol", value="NVDA").upper()
quantity = st.sidebar.number_input("Quantity (Shares)", min_value=1, value=100)
analyze_button = st.sidebar.button("🔍 Analyze Trade")

# --- Helper Function ---
def fetch_market_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period='6mo', interval='1d')
        
        if hist.empty:
            return {'success': False, 'error': 'No data found (Check Ticker)'}
        
        try:
            company_name = stock.info.get('longName', ticker)
        except:
            company_name = ticker 

        earnings_date = "Unknown"
        try:
            calendar = stock.calendar
            if isinstance(calendar, dict) and 'Earnings Date' in calendar:
                 dates = calendar['Earnings Date']
                 if dates:
                    earnings_date = str(dates[0])
            elif not isinstance(calendar, dict) and not calendar.empty:
                earnings_date = calendar.iloc[0][0].strftime('%Y-%m-%d')
        except:
            pass

        return {
            'success': True,
            'history': hist,
            'current_price': hist.iloc[-1]['Close'],
            'earnings': earnings_date,
            'company_name': company_name 
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def calculate_hindsight(df, qty, current_price):
    try:
        if len(df) >= 6: 
            past_price = df['Close'].iloc[-6] 
            diff = current_price - past_price
            pnl = diff * qty
            return past_price, pnl
        else:
            return 0, 0
    except:
        return 0, 0

# --- Main Logic ---
if analyze_button:
    with st.spinner("Wait... Calculating your risk..."):
        try:
            # 1. Fetch Data
            data = fetch_market_data(ticker_symbol)
            
            if not data['success']:
                st.error(f"Data Error: {data['error']}")
                st.stop()

            df = data['history']
            curr_price = data['current_price']
            company_name = data['company_name'] 
            
            # 2. Indicators
            df['RSI'] = ta.rsi(df['Close'], length=14)
            bb = ta.bbands(df['Close'], length=20, std=2)
            if bb is not None:
                df = pd.concat([df, bb], axis=1)
            
            rsi = df.iloc[-1].get('RSI', 50)
            past_price, hindsight_pnl = calculate_hindsight(df, quantity, curr_price)
            
            # 3. AI Prompt (대폭 강화됨!)
            prompt = f"""
            You are a Risk Manager for a swing trader.
            Your Risk Attitude is: **{risk_tolerance.upper()}**.

            USER INPUT:
            - Ticker: {ticker_symbol}
            - Shares: {quantity}
            - Current Price: ${curr_price:.2f}
            
            MARKET DATA:
            - RSI: {rsi:.2f}
            - Next Earnings: {data['earnings']}
            
            ### STRICT RULES FOR {risk_tolerance.upper()} MODE:

            1. **CONSERVATIVE (The "Coward" Mode):**
               - Your #1 goal is CAPITAL PRESERVATION.
               - **IF RSI > 60:** You MUST say **WAIT**. (Too expensive).
               - **IF RSI < 40:** You might say GO.
               - If the price is near an All-Time High, say WAIT.
               - **Verdict Rule:** Unless the setup is PERFECT (Cheap + Uptrend), default to WAIT or STOP.

            2. **MODERATE (The "Rational" Mode):**
               - Balance risk and reward.
               - **IF RSI > 70:** Say WAIT.
               - **IF RSI 40-60:** Check the trend. If Up, GO.

            3. **AGGRESSIVE (The "Bull" Mode):**
               - Your #1 goal is MOMENTUM.
               - **IF RSI > 70:** It's okay! It means strong momentum. Say **GO**.
               - Only say STOP if RSI > 85 or trend is clearly broken.

            TASK:
            1. Decide VERDICT (GO / STOP / WAIT) based strictly on the rules above.
            2. Set Stop Loss & Target Price.
            3. Calculate Potential Loss.
            4. Explain 'Why' simply.

            OUTPUT JSON (No markdown):
            {{
                "verdict": "GO" or "STOP" or "WAIT",
                "risk_color": "green" or "red" or "orange",
                "stop_loss_price": 000.00,
                "target_price": 000.00,
                "potential_loss_amount": 000.00,
                "reality_check_message": "Short warning sentence.",
                "reasoning_simple": ["Point 1", "Point 2", "Point 3"]
            }}
            """
            
            # 4. Call AI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                temperature=0 
            )
            
            # 5. Robust JSON Parsing
            raw_content = response.choices[0].message.content
            cleaned_content = raw_content.replace("```json", "").replace("```", "").strip()
            
            try:
                ai_result = json.loads(cleaned_content)
            except json.JSONDecodeError:
                st.error("AI returned invalid JSON. Here is the raw text:")
                st.code(raw_content)
                st.stop()
            
            # 6. UI Rendering
            
            # Header
            st.markdown(f"""
            <div class="company-header">
                <p class="company-ticker">{ticker_symbol}</p>
                <p class="company-name">{company_name}</p>
            </div>
            """, unsafe_allow_html=True)

            # Verdict
            verdict = ai_result.get('verdict', 'WAIT')
            risk_color = ai_result.get('risk_color', 'orange')
            color_map = {"GO": "#00CC7A", "STOP": "#FF4B4B", "WAIT": "#FFA500"}
            bg_color = color_map.get(verdict, "#FFA500") 

            st.markdown(f"""
            <div class="verdict-box" style="background-color: {bg_color};">
                <h1 style="color: white; font-size: 50px; margin:0;">{verdict}</h1>
                <h3 style="color: white; margin:0;">{risk_color.upper()} RISK DETECTED ({risk_tolerance.upper()} MODE)</h3>
            </div>
            """, unsafe_allow_html=True)
            
            # Reality Check
            loss_amt = ai_result.get('potential_loss_amount', 0)
            reality_msg = ai_result.get('reality_check_message', '')
            
            st.markdown(f"""
            <div style="text-align: center; margin-bottom: 20px;">
                <h2 style="color: #FF4B4B;">⚠️ "If the trade goes wrong, you could lose up to ${loss_amt:,.2f} near the Stop Loss."</h2>
                <p style="color: gray;">{reality_msg}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Metrics
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("Current Price", f"${curr_price:.2f}")
            with c2:
                st.metric("Suggested Stop Loss", f"${ai_result.get('stop_loss_price', 0):.2f}", help="Short-term support (1-2 weeks)")
            with c3:
                st.metric("Suggested Target Price", f"${ai_result.get('target_price', 0):.2f}", help="Short-term resistance (1-2 weeks)")
            
            st.divider()

            # Hindsight
            if hindsight_pnl >= 0:
                h_bg = "rgba(0, 204, 122, 0.2)"
                h_border = "#00CC7A"
                icon = "📈"
                title = "Missed Opportunity"
                msg = f"If you followed my strategy 1 week ago, you would have made <span style='color: #00FF99;'>+${hindsight_pnl:,.2f}</span> profit today."
            else:
                h_bg = "rgba(255, 75, 75, 0.2)"
                h_border = "#FF4B4B"
                icon = "🛡️"
                title = "Risk Averted"
                msg = f"If you traded alone 1 week ago without PAUSE, you would have lost <span style='color: #FF4B4B;'>-${abs(hindsight_pnl):,.2f}</span> today."

            st.markdown(f"""
            <div class="hindsight-box" style="background-color: {h_bg}; border-color: {h_border};">
                <div style="font-size: 28px; margin-bottom: 10px;">{icon} {title}</div>
                <div>{msg}</div>
            </div>
            """, unsafe_allow_html=True)

            # Why
            st.subheader("🧐 Why?")
            reasons = ai_result.get('reasoning_simple', [])
            if isinstance(reasons, list):
                for r in reasons:
                    st.markdown(f"- {r}") 
            else:
                st.write(reasons)
            
            with st.expander("Show Earnings Info"):
                st.write(f"**Next Earnings Date:** {data['earnings']}")

            # Chart
            st.markdown("---")
            st.subheader(f"📉 {ticker_symbol} Price Chart (Last 30 Days)")
            chart_df = df.tail(30) 
            fig = go.Figure(data=[go.Candlestick(x=chart_df.index, open=chart_df['Open'], high=chart_df['High'], low=chart_df['Low'], close=chart_df['Close'])])
            fig.update_layout(height=500, margin=dict(l=0,r=0,t=30,b=0))
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error("🚨 An error occurred!")
            st.error(f"Error details: {str(e)}")
            st.code(traceback.format_exc())