import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import random

# --- 頁面設定 ---
st.set_page_config(page_title="當沖生命線戰法練習", layout="wide", page_icon="📈")

# --- CSS 美化 ---
st.markdown("""
<style>
    .stButton>button {
        height: 3em;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 初始化 Session State ---
default_values = {
    'balance': 100000.0,
    'position': 0,
    'avg_cost': 0.0,
    'step': 200,
    'history': [],
    'data': None,
    'ticker': "",
    'nickname': "",
    'game_started': False
}

for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 核心邏輯函數 ---

def load_data():
    tickers = ['NVDA', 'TSLA', 'AMD', 'TQQQ', 'SOXL', 'AAPL', 'MSFT']
    selected_ticker = random.choice(tickers)
    
    # 下載資料
    try:
        with st.spinner(f"正在下載 {selected_ticker} 的歷史資料..."):
            df = yf.download(selected_ticker, period="1mo", interval="5m", progress=False)
            
        # --- 修復錯誤的關鍵步驟 1 ---
        # 如果 yfinance 回傳多層索引 (MultiIndex)，強制把它壓平
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if len(df) < 300:
            st.error("資料不足，請重試")
            return None, None

        # 計算指標
        df['MA200'] = df['Close'].rolling(window=200).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        
        df.reset_index(inplace=True)
        
        # 設定遊戲起始點
        max_start = len(df) - 150
        if max_start > 200:
            start_idx = random.randint(200, max_start)
        else:
            start_idx = 200
            
        st.session_state.step = start_idx
        return selected_ticker, df
        
    except Exception as e:
        st.error(f"資料讀取發生錯誤: {e}")
        return None, None

def reset_game():
    st.session_state.balance = 100000.0
    st.session_state.position = 0
    st.session_state.avg_cost = 0.0
    st.session_state.history = []
    st.session_state.ticker, st.session_state.data = load_data()

def trade(action, price, qty=10):
    # 確保價格是純數字 (浮點數)
    price = float(price)
    
    if action == "buy":
        cost = price * qty
        if st.session_state.balance >= cost:
            st.session_state.balance -= cost
            total_cost = (st.session_state.avg_cost * st.session_state.position) + cost
            st.session_state.position += qty
            st.session_state.avg_cost = total_cost / st.session_state.position
            st.session_state.history.append(f"🔴 {st.session_state.step}K | 買入 {qty} @ {price:.2f}")
        else:
            st.toast("❌ 資金不足！")
            
    elif action == "sell":
        if st.session_state.position >= qty:
            revenue = price * qty
            profit = (price - st.session_state.avg_cost) * qty
            st.session_state.balance += revenue
            st.session_state.position -= qty
            if st.session_state.position == 0:
                st.session_state.avg_cost = 0.0
            
            icon = "💰" if profit > 0 else "💸"
            st.session_state.history.append(f"🟢 {st.session_state.step}K | 賣出 {qty} @ {price:.2f} | 損益: {profit:.2f} {icon}")
        else:
            st.toast("❌ 持倉不足！")

# --- 主程式介面 ---

st.title("🎢 當沖模擬器：挑戰生命線戰法")

if not st.session_state.game_started:
    st.info("👋 歡迎！請輸入暱稱開始訓練盤感。")
    col1, col2 = st.columns([1, 2])
    with col1:
        name_input = st.text_input("輸入你的綽號", "ASUS股神")
        if st.button("🚀 開始挑戰", use_container_width=True):
            st.session_state.nickname = name_input
            st.session_state.game_started = True
            reset_game()
            st.rerun()

else:
    df = st.session_state.data
    if df is None:
        if st.button("重新載入資料"):
            reset_game()
            st.rerun()
        st.stop()

    current_idx = st.session_state.step
    display_df = df.iloc[current_idx-50 : current_idx+1]
    
    # --- 修復錯誤的關鍵步驟 2 ---
    # 使用 .item() 確保只抓出單一數值，或者是直接轉 float
    try:
        current_bar = df.iloc[current_idx]
        raw_price = current_bar['Close']
        # 判斷是否為 Series (列表)，如果是就取第一個值，如果不是就直接轉 float
        if isinstance(raw_price, pd.Series):
             current_price = float(raw_price.iloc[0])
        else:
             current_price = float(raw_price)
    except:
        # 如果真的發生萬一，給個預設值防止當機
        current_price = 0.0
    
    # --- 側邊欄 ---
    with st.sidebar:
        st.subheader(f"👤 {st.session_state.nickname} 的帳戶")
        
        market_val = st.session_state.position * current_price
        unrealized = (current_price - st.session_state.avg_cost) * st.session_state.position if st.session_state.position > 0 else 0
        
        col_metric1, col_metric2 = st.columns(2)
        col_metric1.metric("現金", f"${int(st.session_state.balance)}")
        col_metric2.metric("持倉市值", f"${int(market_val)}")
        st.metric("未實現損益", f"${unrealized:.2f}", delta_color="normal")
        
        st.divider()
        
        # 這裡就是原本報錯的地方，現在 current_price 已經保證是 float 了
        st.write(f"當前價格: **{current_price:.2f}**")
        order_qty = st.number_input("下單股數", min_value=1, value=10, step=10)
        
        c1, c2 = st.columns(2)
        if c1.button("🔴 買進", use_container_width=True):
            trade("buy", current_price, order_qty)
        if c2.button("🟢 賣出", use_container_width=True):
            trade("sell", current_price, order_qty)

        st.divider()
        
        if st.button("⏭️ 下一根 K 棒 (5分)", type="primary", use_container_width=True):
            if st.session_state.step < len(df) - 1:
                st.session_state.step += 1
                st.rerun()
            else:
                st.success("本局結束！")

        if st.button("🔄 重開一局"):
            reset_game()
            st.rerun()

    # --- 主圖表 ---
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(
        x=display_df['Datetime'],
        open=display_df['Open'], high=display_df['High'],
        low=display_df['Low'], close=display_df['Close'],
        name="K線"
    ))

    fig.add_trace(go.Scatter(
        x=display_df['Datetime'], y=display_df['MA200'],
        line=dict(color='blue', width=2), name='生命線 (200MA)'
    ))

    fig.add_trace(go.Scatter(
        x=display_df['Datetime'], y=display_df['MA60'],
        line=dict(color='orange', width=1), name='60MA'
    ))

    fig.update_layout(
        title=f"{st.session_state.ticker} - 5分鐘 K 線圖",
        height=600,
        xaxis_rangeslider_visible=False,
        margin=dict(l=10, r=10, t=40, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)

    with st.expander("📜 交易紀錄", expanded=True):
        if not st.session_state.history:
            st.write("尚無交易")
        for log in reversed(st.session_state.history):
            st.text(log)
