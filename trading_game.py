import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
import random
import time
import os

# --- 1. 頁面與全域設定 ---
st.set_page_config(page_title="當沖模擬器 - 旗艦版", layout="wide", page_icon="📈")

# 自定義 CSS：讓字體變大，解決 "..." 擁擠問題
st.markdown("""
<style>
    /* 調整 metric 指標的字體大小 */
    [data-testid="stMetricValue"] {
        font-size: 24px;
    }
    /* 讓按鈕顯眼一點 */
    .stButton>button {
        font-weight: bold;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# 檔案路徑 (用來存排行榜)
LEADERBOARD_FILE = "leaderboard.csv"

# --- 2. 初始化 Session State ---
default_values = {
    'balance': 100000.0,
    'position': 0,
    'avg_cost': 0.0,
    'step': 200,
    'history': [],
    'data': None,
    'ticker': "",
    'nickname': "",
    'game_started': False,
    'auto_play': False,  # 新增：控制自動播放
    'speed': 1.0         # 新增：播放速度
}

for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 3. 核心邏輯函數 ---

def load_leaderboard():
    if os.path.exists(LEADERBOARD_FILE):
        return pd.read_csv(LEADERBOARD_FILE)
    else:
        return pd.DataFrame(columns=["日期", "玩家", "股票", "最終資產", "報酬率"])

def save_score(player, ticker, assets, roi):
    new_entry = pd.DataFrame([{
        "日期": time.strftime("%Y-%m-%d %H:%M"),
        "玩家": player,
        "股票": ticker,
        "最終資產": round(assets, 2),
        "報酬率": f"{roi:.2f}%"
    }])
    if os.path.exists(LEADERBOARD_FILE):
        df = pd.read_csv(LEADERBOARD_FILE)
        df = pd.concat([df, new_entry], ignore_index=True)
    else:
        df = new_entry
    df.to_csv(LEADERBOARD_FILE, index=False)

def load_data():
    tickers = ['NVDA', 'TSLA', 'AMD', 'TQQQ', 'SOXL', 'MSTR', 'COIN']
    selected_ticker = random.choice(tickers)
    
    try:
        # 下載資料
        df = yf.download(selected_ticker, period="1mo", interval="5m", progress=False)
        
        # 強制壓平多層索引 (修復之前的 bug)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if len(df) < 300:
            return None, None

        # 計算均線
        df['MA200'] = df['Close'].rolling(window=200).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df.reset_index(inplace=True)
        
        # 設定起始點
        max_start = len(df) - 150
        start_idx = random.randint(200, max_start) if max_start > 200 else 200
        st.session_state.step = start_idx
        return selected_ticker, df
        
    except Exception as e:
        print(f"Error: {e}")
        return None, None

def reset_game():
    st.session_state.balance = 100000.0
    st.session_state.position = 0
    st.session_state.avg_cost = 0.0
    st.session_state.history = []
    st.session_state.auto_play = False
    st.session_state.ticker, st.session_state.data = load_data()

def trade(action, price, qty):
    price = float(price)
    if action == "buy":
        cost = price * qty
        if st.session_state.balance >= cost:
            st.session_state.balance -= cost
            total_cost = (st.session_state.avg_cost * st.session_state.position) + cost
            st.session_state.position += qty
            st.session_state.avg_cost = total_cost / st.session_state.position
            st.session_state.history.append(f"🔴 買入 {qty} 股 @ {price:.2f}")
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
            st.session_state.history.append(f"🟢 賣出 {qty} 股 @ {price:.2f} (損益: {profit:.2f}) {icon}")
        else:
            st.toast("❌ 持倉不足！")

# --- 4. 主程式介面 ---

# 使用 Tabs 分頁功能：把遊戲區跟排行榜分開
tab1, tab2 = st.tabs(["🎮 當沖戰場", "🏆 排行榜與紀錄"])

with tab1:
    st.title("📈 閃電當沖王")

    if not st.session_state.game_started:
        st.info("請輸入暱稱並點擊開始")
        col1, col2 = st.columns([1, 2])
        with col1:
            name_input = st.text_input("玩家暱稱", "神之手")
            if st.button("🔥 開始遊戲", use_container_width=True):
                st.session_state.nickname = name_input
                st.session_state.game_started = True
                reset_game()
                st.rerun()

    else:
        df = st.session_state.data
        if df is None:
            st.error("資料載入失敗，請按重開一局")
            if st.button("重開"):
                reset_game()
                st.rerun()
            st.stop()

        # 取得當前數據
        current_idx = st.session_state.step
        try:
            row = df.iloc[current_idx]
            current_price = float(row['Close'].iloc[0]) if isinstance(row['Close'], pd.Series) else float(row['Close'])
            current_time = row['Datetime']
        except:
            current_price = 0.0
            current_time = "Unknown"

        # --- A. 頂部資訊列 (解決擁擠問題) ---
        # 計算總資產與未實現損益
        market_val = st.session_state.position * current_price
        total_assets = st.session_state.balance + market_val
        unrealized = (current_price - st.session_state.avg_cost) * st.session_state.position if st.session_state.position > 0 else 0
        roi = ((total_assets - 100000) / 100000) * 100

        # 使用 4 個欄位寬鬆顯示
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 現金餘額", f"${int(st.session_state.balance):,}")
        m2.metric("📦 持倉庫存", f"{st.session_state.position} 股", f"市值 ${int(market_val):,}")
        m3.metric("📊 未實現損益", f"${unrealized:,.0f}", delta_color="normal")
        m4.metric("🚀 總資產報酬", f"${int(total_assets):,}", f"{roi:.2f}%")

        st.divider()

        # --- B. 圖表區域 ---
        display_df = df.iloc[current_idx-60 : current_idx+1]
        
        fig = go.Figure()
        # K線
        fig.add_trace(go.Candlestick(
            x=display_df['Datetime'],
            open=display_df['Open'], high=display_df['High'],
            low=display_df['Low'], close=display_df['Close'],
            name="K線"
        ))
        # 均線
        fig.add_trace(go.Scatter(x=display_df['Datetime'], y=display_df['MA200'], line=dict(color='blue', width=2), name='200MA (生命線)'))
        fig.add_trace(go.Scatter(x=display_df['Datetime'], y=display_df['MA60'], line=dict(color='orange', width=1), name='60MA'))

        fig.update_layout(
            title=f"{st.session_state.ticker} ({current_time}) - 價格: {current_price:.2f}",
            height=500,
            xaxis_rangeslider_visible=False,
            margin=dict(l=10, r=10, t=30, b=10)
        )
        st.plotly_chart(fig, use_container_width=True)

        # --- C. 操作控制區 ---
        c1, c2, c3 = st.columns([1, 1, 1])
        
        # 1. 買賣操作
        with c1:
            st.subheader("交易")
            qty = st.number_input("股數", 10, 1000, 10, step=10)
            b_col, s_col = st.columns(2)
            if b_col.button("🔴 買進", use_container_width=True):
                trade("buy", current_price, qty)
            if s_col.button("🟢 賣出", use_container_width=True):
                trade("sell", current_price, qty)

        # 2. 自動播放控制
        with c2:
            st.subheader("時間控制")
            
            # 自動播放按鈕邏輯
            if st.session_state.auto_play:
                if st.button("⏸️ 暫停", type="primary", use_container_width=True):
                    st.session_state.auto_play = False
                    st.rerun()
            else:
                if st.button("▶️ 自動播放", use_container_width=True):
                    st.session_state.auto_play = True
                    st.rerun()
            
            # 手動下一步
            if st.button("⏭️ 下一根 K 棒", disabled=st.session_state.auto_play, use_container_width=True):
                if st.session_state.step < len(df) - 1:
                    st.session_state.step += 1
                    st.rerun()

        # 3. 遊戲狀態
        with c3:
            st.subheader("狀態")
            if st.button("🏳️ 結算成績 / 重來", use_container_width=True):
                # 儲存成績
                save_score(st.session_state.nickname, st.session_state.ticker, total_assets, roi)
                st.toast("✅ 成績已儲存到排行榜！")
                time.sleep(1)
                reset_game()
                st.rerun()

        # --- 自動播放邏輯 ---
        if st.session_state.auto_play:
            if st.session_state.step < len(df) - 1:
                time.sleep(0.5) # 控制速度 (0.5秒一根)
                st.session_state.step += 1
                st.rerun()
            else:
                st.session_state.auto_play = False
                st.success("盤勢結束！")

        # --- 底部：交易紀錄 ---
        with st.expander("📜 本局交易紀錄", expanded=False):
            for log in reversed(st.session_state.history):
                st.text(log)

# --- 排行榜分頁 ---
with tab2:
    st.header("🏆 英雄榜 (維護紀錄)")
    st.write("這裡記錄了所有玩家的輝煌戰績與損益結果。")
    
    leaderboard_df = load_leaderboard()
    
    if not leaderboard_df.empty:
        # 依照報酬率排序 (需處理字串轉數字)
        try:
            # 簡單排序，把報酬率最高的排上面
            st.dataframe(leaderboard_df.sort_index(ascending=False), use_container_width=True)
        except:
            st.dataframe(leaderboard_df, use_container_width=True)
            
        # 提供下載 CSV 功能
        csv = leaderboard_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            "📥 下載完整紀錄 (CSV)",
            csv,
            "leaderboard.csv",
            "text/csv",
            key='download-csv'
        )
    else:
        st.info("目前還沒有紀錄，快去玩一局吧！")
