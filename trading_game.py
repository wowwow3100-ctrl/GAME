import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import random

# --- 頁面設定 ---
st.set_page_config(page_title="當沖生命線戰法練習", layout="wide", page_icon="📈")

# --- CSS 美化 (讓按鈕更好看) ---
st.markdown("""
<style>
    .stButton>button {
        height: 3em;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 初始化 Session State ---
# 這裡儲存資金、持倉、遊戲進度等變數
default_values = {
    'balance': 100000.0,  # 初始資金
    'position': 0,        # 持倉股數
    'avg_cost': 0.0,      # 平均成本
    'step': 200,          # 從第200根K棒開始 (為了讓200MA跑出來)
    'history': [],        # 交易紀錄
    'data': None,         # 股價資料
    'ticker': "",         # 股票代號
    'nickname': "",       # 玩家暱稱
    'game_started': False # 遊戲狀態
}

for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 核心邏輯函數 ---

def load_data():
    # 隨機抽取高波動熱門股
    tickers = ['NVDA', 'TSLA', 'AMD', 'TQQQ', 'SOXL', 'AAPL', 'MSFT']
    selected_ticker = random.choice(tickers)
    
    # 下載 1 個月的 5分鐘線資料 (為了計算 200MA，資料要夠長)
    with st.spinner(f"正在下載 {selected_ticker} 的歷史資料..."):
        df = yf.download(selected_ticker, period="1mo", interval="5m", progress=False)
    
    if len(df) < 300:
        st.error("資料不足，請重試 (可能是盤後或資料源問題)")
        return None, None
    
    # --- 這裡加入你的技術指標 ---
    # 計算 200MA (生命線)
    df['MA200'] = df['Close'].rolling(window=200).mean()
    # 計算 60MA (季線/輔助線)
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # 處理資料格式 (移除多層索引)
    df.reset_index(inplace=True)
    
    # 隨機切分一段用來玩 (取其中 150 根 K 棒，但要確保前面有資料算均線)
    max_start = len(df) - 150
    if max_start > 200:
        start_idx = random.randint(200, max_start)
    else:
        start_idx = 200
        
    # 我們保留完整的 df 以便隨時取用前面的均線數值，但在介面上只透過 step 控制顯示範圍
    # 遊戲將從 start_idx 開始
    st.session_state.step = start_idx
    
    return selected_ticker, df

def reset_game():
    st.session_state.balance = 100000.0
    st.session_state.position = 0
    st.session_state.avg_cost = 0.0
    st.session_state.history = []
    st.session_state.ticker, st.session_state.data = load_data()

def trade(action, price, qty=10):
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

# 1. 登入畫面
if not st.session_state.game_started:
    st.info("👋 歡迎！這是一個訓練盤感的工具。請輸入暱稱開始。")
    col1, col2 = st.columns([1, 2])
    with col1:
        name_input = st.text_input("輸入你的綽號", "ASUS股神")
        if st.button("🚀 開始挑戰", use_container_width=True):
            st.session_state.nickname = name_input
            st.session_state.game_started = True
            reset_game()
            st.rerun()

# 2. 遊戲主畫面
else:
    df = st.session_state.data
    if df is None:
        if st.button("重新載入資料"):
            reset_game()
            st.rerun()
        st.stop()

    current_idx = st.session_state.step
    # 為了讓畫面好看，我們顯示過去 50 根 K 棒，加上現在這 1 根
    display_df = df.iloc[current_idx-50 : current_idx+1]
    
    current_bar = df.iloc[current_idx]
    current_price = current_bar['Close'] # 這裡簡化，用當根收盤價當作成交價
    
    # --- 側邊欄：操盤室 ---
    with st.sidebar:
        st.subheader(f"👤 {st.session_state.nickname} 的帳戶")
        
        # 資產看板
        col_metric1, col_metric2 = st.columns(2)
        market_val = st.session_state.position * current_price
        unrealized = (current_price - st.session_state.avg_cost) * st.session_state.position if st.session_state.position > 0 else 0
        
        col_metric1.metric("現金", f"${int(st.session_state.balance)}")
        col_metric2.metric("持倉市值", f"${int(market_val)}")
        st.metric("未實現損益", f"${unrealized:.2f}", delta_color="normal")
        
        st.divider()
        
        # 下單區
        st.write(f"當前價格: **{current_price:.2f}**")
        order_qty = st.number_input("下單股數", min_value=1, value=10, step=10)
        
        c1, c2 = st.columns(2)
        if c1.button("🔴 買進", use_container_width=True):
            trade("buy", current_price, order_qty)
        if c2.button("🟢 賣出", use_container_width=True):
            trade("sell", current_price, order_qty)

        st.divider()
        
        # 時間控制
        if st.button("⏭️ 下一根 K 棒 (5分)", type="primary", use_container_width=True):
            if st.session_state.step < len(df) - 1:
                st.session_state.step += 1
                st.rerun()
            else:
                st.success("本局結束！請查看最終損益。")

        if st.button("🔄 重開一局"):
            reset_game()
            st.rerun()

    # --- 主圖表 ---
    
    # 設定圖表
    fig = go.Figure()

    # 1. 畫 K 線
    fig.add_trace(go.Candlestick(
        x=display_df['Datetime'],
        open=display_df['Open'],
        high=display_df['High'],
        low=display_df['Low'],
        close=display_df['Close'],
        name="K線"
    ))

    # 2. 畫 200MA (生命線) - 藍色加粗
    fig.add_trace(go.Scatter(
        x=display_df['Datetime'],
        y=display_df['MA200'],
        line=dict(color='blue', width=2),
        name='生命線 (200MA)'
    ))

    # 3. 畫 60MA (季線) - 橘色細線
    fig.add_trace(go.Scatter(
        x=display_df['Datetime'],
        y=display_df['MA60'],
        line=dict(color='orange', width=1),
        name='60MA'
    ))

    fig.update_layout(
        title=f"{st.session_state.ticker} - 5分鐘 K 線圖",
        height=600,
        xaxis_rangeslider_visible=False,
        showlegend=True,
        margin=dict(l=10, r=10, t=40, b=10)
    )

    st.plotly_chart(fig, use_container_width=True)

    # --- 交易明細 ---
    with st.expander("📜 交易紀錄 (點擊展開)", expanded=True):
        if not st.session_state.history:
            st.write("尚無交易")
        for log in reversed(st.session_state.history):
            st.text(log)
