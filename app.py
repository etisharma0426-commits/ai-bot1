import streamlit as st
import yfinance as yf
import pandas as pd
import pandas_ta as ta
import requests
import plotly.graph_objects as go
import io
from datetime import datetime

# 1. Telegram Alert Function
TOKEN = "8993032227:AAEu_KGHIof9BQiSbCbfv5tkU64DwFHLL2M"  # अपना बोट टोकन यहाँ डालें
CHAT_ID = "6639229564"        # अपनी चैट आईडी यहाँ डालें

def send_telegram_alert(message, df=None, stock_name=None):
    if TOKEN == "YOUR_TELEGRAM_TOKEN" or CHAT_ID == "YOUR_CHAT_ID":
        return
    if df is not None and stock_name is not None:
        chart_df = df.tail(20)
        fig = go.Figure(data=[go.Candlestick(
            x=chart_df.index, open=chart_df['Open'], high=chart_df['High'],
            low=chart_df['Low'], close=chart_df['Close'], name=stock_name
        )])
        fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", margin=dict(l=20, r=20, t=40, b=20))
        try:
            img_bytes = fig.to_image(format="png")
            url = f"https://telegram.org{TOKEN}/sendPhoto"
            files = {'photo': (f'{stock_name}.png', io.BytesIO(img_bytes), 'image/png')}
            payload = {"chat_id": CHAT_ID, "caption": message, "parse_mode": "Markdown"}
            requests.post(url, data=payload, files=files)
            return
        except Exception:
            pass
    url = f"https://telegram.org{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    requests.post(url, json=payload)

st.set_page_config(page_title="AI Trader Robot Ultimate", layout="wide")
st.title("🤖 AI अल्टीमेट ट्रेडिंग रोबोट - 7x फ़िल्टर + डेली P&L रिपोर्ट")

if "active_trades" not in st.session_state:
    st.session_state.active_trades = {}
if "daily_history" not in st.session_state:
    st.session_state.daily_history = []
if "report_sent" not in st.session_state:
    st.session_state.report_sent = False

NIFTY50_TICKERS = [
    'ADANIENT.NS', 'ADANIPORTS.NS', 'AXISBANK.NS', 'BHARTIARTL.NS', 'HDFCBANK.NS',
    'ICICIBANK.NS', 'ITC.NS', 'INFY.NS', 'RELIANCE.NS', 'SBIN.NS', 'TCS.NS', 'TATAMOTORS.NS'
]

@st.cache_data(ttl=60)
def run_ultimate_bot():
    stock_data = []
    current_time = datetime.now().time()
    if current_time >= datetime.strptime("15:30:00", "%H:%M:%S").time():
        if not st.session_state.report_sent and len(st.session_state.daily_history) > 0:
            total_pnl = sum([t['pnl'] for t in st.session_state.daily_history])
            report_msg = f"📊 *DAILY TRADING REPORT*\n\n📅 दिनांक: {datetime.now().strftime('%d-%m-%Y')}\n कुल ट्रेड्स: {len(st.session_state.daily_history)}\n"
            for t in st.session_state.daily_history:
                report_msg += f"{'🟢' if t['pnl'] > 0 else '🔴'} *{t['stock']}*: Profit/Loss ₹{round(t['pnl'], 2)}\n"
            report_msg += f"\n💰 *नेट डेली प्रॉफिट/लॉस: {'+₹' if total_pnl > 0 else '-₹'}{abs(round(total_pnl, 2))}*"
            send_telegram_alert(report_msg)
            st.session_state.report_sent = True
    else:
        st.session_state.report_sent = False
        
    for ticker in NIFTY50_TICKERS:
        try:
            stock = yf.Ticker(ticker)
            df = stock.history(period="10d", interval="15m")
            if len(df) < 40: continue
            df['EMA_9'] = ta.ema(df['Close'], length=9)
            df['EMA_21'] = ta.ema(df['Close'], length=21)
            df['RSI'] = ta.rsi(df['Close'], length=14)
            sti = ta.supertrend(df['High'], df['Low'], df['Close'], length=7, multiplier=3)
            df['ST_Direction'] = sti['SUPERTd_7_3.0']
            macd_df = ta.macd(df['Close'], fast=12, slow=26, signal=9)
            df['MACD'] = macd_df['MACD_12_26_9']
            df['MACD_Signal'] = macd_df['MACDs_12_26_9']
            bb = ta.bbands(df['Close'], length=20, std=2)
            df['BBU'] = bb['BBU_20_2.0']
            df['BBL'] = bb['BBL_20_2.0']
            stoch_rsi = ta.stochrsi(df['Close'], length=14, rsi_length=14, k=3, d=3)
            df['STOCHRSIk'] = stoch_rsi['STOCHRSIk_14_14_3_3']
            df['Vol_SMA'] = ta.sma(df['Volume'], length=20)
            df['ATR'] = ta.atr(df['High'], df['Low'], df['Close'], length=14)
            
            current_price = df['Close'].iloc[-1]
            last_volume = df['Volume'].iloc[-1]
            vol_sma = df['Vol_SMA'].iloc[-1]
            ema_9 = df['EMA_9'].iloc[-1]
            ema_21 = df['EMA_21'].iloc[-1]
            last_rsi = df['RSI'].iloc[-1]
            st_dir = df['ST_Direction'].iloc[-1]
            macd_val = df['MACD'].iloc[-1]
            macd_sig = df['MACD_Signal'].iloc[-1]
            bbu = df['BBU'].iloc[-1]
            bbl = df['BBL'].iloc[-1]
            stoch_k = df['STOCHRSIk'].iloc[-1]
            atr_value = df['ATR'].iloc[-1] if not pd.isna(df['ATR'].iloc[-1]) else (current_price * 0.01)
            stock_name = ticker.replace(".NS", "")
            
            if stock_name in st.session_state.active_trades:
                trade = st.session_state.active_trades[stock_name]
                if trade['type'] == "BUY":
                    if current_price >= trade['target']:
                        pnl = (trade['target'] - trade['entry']) * trade['qty']
                        send_telegram_alert(f"🎯 *TARGET HIT: {stock_name}*\n\n📈 पोजीशन: BUY\n💵 *मुनाफा: +₹{round(pnl, 2)}*")
                        st.session_state.daily_history.append({"stock": stock_name, "pnl": pnl})
                        del st.session_state.active_trades[stock_name]
                    elif current_price <= trade['sl']:
                        pnl = (current_price - trade['entry']) * trade['qty']
                        send_telegram_alert(f"🛡️ *STOP LOSS HIT: {stock_name}*\n\n📉 पोजीशन: BUY\n💵 *नुकसान: -₹{round(abs(pnl), 2)}*")
                        st.session_state.daily_history.append({"stock": stock_name, "pnl": pnl})
                        del st.session_state.active_trades[stock_name]
            else:
                buy_cond = ((ema_9 > ema_21) and (last_rsi > 55) and (st_dir == 1) and (macd_val > macd_sig) and (current_price >= bbu * 0.99) and (last_volume > vol_sma * 1.3))
                sell_cond = ((ema_9 < ema_21) and (last_rsi < 45) and (st_dir == -1) and (macd_val < macd_sig) and (current_price <= bbl * 1.01) and (last_volume > vol_sma * 1.3))
                
                if buy_cond:
                    sl = current_price - (atr_value * 1.5)
                    tgt = current_price + (atr_value * 3.0)
                    qty = int(50000 / current_price)
                    st.session_state.active_trades[stock_name] = {"type": "BUY", "entry": current_price, "sl": sl, "target": tgt, "qty": qty}
                    msg = f"🚀 *AI PAPER TRADE (BUY)*\n\n📦 स्टॉक: *{stock_name}*\n💰 एंट्री: ₹{round(current_price, 2)}\n🎯 Target: ₹{round(tgt, 2)} | 🛡️ SL: ₹{round(sl, 2)}"
                    send_telegram_alert(msg, df, stock_name)
                elif sell_cond:
                    sl = current_price + (atr_value * 1.5)
                    tgt = current_price - (atr_value * 3.0)
                    qty = int(50000 / current_price)
                    st.session_state.active_trades[stock_name] = {"type": "SELL", "entry": current_price, "sl": sl, "target": tgt, "qty": qty}
                    msg = f"📉 *AI PAPER TRADE (SELL)*\n\n📦 स्टॉक: *{stock_name}*\n💰 एंट्री: ₹{round(current_price, 2)}\n🎯 Target: ₹{round(tgt, 2)} | 🛡️ SL: ₹{round(sl, 2)}"
                    send_telegram_alert(msg, df, stock_name)

            status = st.session_state.active_trades.get(stock_name, None)
            stock_data.append({
                "Stock": stock_name, "Price (₹)": round(current_price, 2),
                "Status": f"🔄 इन-ट्रेड ({status['type']})" if status else "⏳ स्कैनिंग...",
                "Target": round(status['target'], 2) if status else "-", "Stop Loss": round(status['sl'], 2) if status else "-"
            })
        except Exception:
            pass
    return pd.DataFrame(stock_data)

with st.spinner("7x एआई इंजन स्कैन कर रहा है..."):
    results_df = run_ultimate_bot()
st.dataframe(results_df, use_container_width=True)
