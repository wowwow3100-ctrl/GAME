import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import random
import time
import os
import numpy as np

# --- 1. 頁面與全域設定 ---
st.set_page_config(page_title="當沖模擬戰 - 專業版", layout="wide", page_icon="💹")

# 自定義 CSS
st.markdown("""
<style>
    [data-testid="stMetricValue"] { font-size: 24px; }
    .stButton>button { font-weight: bold; border-radius: 8px; }
    /* 調整 Tab 字體 */
    button[data-baseweb="tab"] { font-size: 18px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

FILES = {"leaderboard": "leaderboard.csv", "feedback": "feedback.csv"}

# --- 2. 初始化 Session State ---
default_values = {
    'balance': 100000.0,
    'position': 0,
    'avg_cost': 0.0,
    'step': 200,
    'history': [],      # 文字紀錄
    'trades_visual': [], # 視覺化紀錄 (用於在圖上畫箭頭)
    'data': None,
    'ticker': "",
    'nickname': "",
    'game_started': False,
    'auto_play': False,
    'speed': 1.0
}

for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 3. 技術指標計算函數 ---

def calculate_technical_indicators(df):
    # 1. 均線
    df['MA200'] = df['Close'].rolling(window=200).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    
    # 2. KD 指標 (9, 3, 3)
    # RSV = (Close - MinLow) / (MaxHigh - MinLow) * 100
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    df['RSV'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    # K值與D值 (使用簡單遞迴計算平滑)
    df['K'] = df['RSV'].ewm(com=2).mean() # com=2 等同於 alpha=1/3
    df['D'] = df['K'].ewm(com=2).mean()
    
    # 3. MACD (12, 26, 9)
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    
    return df

def load_data():
    tickers = ['NVDA', 'TSLA', 'AMD', 'TQQQ', 'SOXL', 'MSTR', 'COIN', 'AAPL']
    selected_ticker = random.choice(tickers)
    
    try:
        # 下載資料
        df = yf.download(selected_ticker, period="1mo", interval="5m", progress=False)
        
        # 格式整理
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if len(df) < 300: return None, None

        # 計算指標
        df = calculate_technical_indicators(df)
        
        # 匿名化處理：我們不使用真實日期當 Index，改用流水號
        df.reset_index(inplace=True)
        df['Bar_Index'] = range(len(df)) # 建立流水號 0, 1, 2...
        
        # 隨機切入點
        max_start = len(df) - 150
        start_idx = random.randint(200, max_start) if max_start > 200 else 200
        st.session_state.step = start_idx
        return selected_ticker, df
        
    except Exception as e:
        return None, None

def reset_game():
    st.session_state.balance = 100000.0
    st.session_state.position = 0
    st.session_state.avg_cost = 0.0
    st.session_state.history = []
    st.session_state.trades_visual = [] # 重置圖表標記
    st.session_state.auto_play = False
    st.session_state.ticker, st.session_state.data = load_data()

def trade(action, price, qty, current_step_index):
    price = float(price)
    if action == "buy":
        cost = price * qty
        if st.session_state.balance >= cost:
            st.session_state.balance -= cost
            total_cost = (st.session_state.avg_cost * st.session_state.position) + cost
            st.session_state.position += qty
            st.session_state.avg_cost = total_cost / st.session_state.position
            st.session_state.history.append(f"🔴 買入 {qty} 股 @ {price:.2f}")
            
            # 紀錄視覺化座標
            st.session_state.trades_visual.append({
                'index': current_step_index,
                'price': price,
                'type': 'buy'
            })
        else:
            st.toast("❌ 資金不足！")
            
    elif action == "sell":
        if st.session_state.position >= qty:
            revenue = price * qty
            profit = (price - st.session_state.avg_cost) * qty
            st.session_state.balance += revenue
            st.session_state.position -= qty
            if st.session_state.position == 0: st.session_state.avg_cost = 0.0
            
            icon = "💰" if profit > 0 else "💸"
            st.session_state.history.append(f"🟢 賣出 {qty} 股 @ {price:.2f} (損益: {profit:.2f}) {icon}")
            
            # 紀錄視覺化座標
            st.session_state.trades_visual.append({
                'index': current_step_index,
                'price': price,
                'type': 'sell'
            })
        else:
            st.toast("❌ 持倉不足！")

def save_score(player, ticker, assets, roi):
    new_entry = pd.DataFrame([{
        "日期": time.strftime("%Y-%m-%d %H:%M"), "玩家": player,
        "股票": ticker, "最終資產": round(assets, 2), "報酬率": f"{roi:.2f}%"
    }])
    header = not os.path.exists(FILES["leaderboard"])
    new_entry.to_csv(FILES["leaderboard"], mode='a', header=header, index=False)

def save_feedback(name, text):
    with open(FILES["feedback"], "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d')}] {name}: {text}\n")

# --- 4. 主程式介面 ---

# 側邊欄：功能選單與意見回饋
with st.sidebar:
    st.header("⚙️ 設定與回饋")
    st.write("這是一個隨機抽選歷史數據的練習場，時間已隱藏，請專注於 K 線型態。")
    
    with st.expander("📝 意見回饋 (Feedback)"):
        with st.form("feedback_form"):
            fb_text = st.text_area("有什麼建議或發現Bug嗎？")
            if st.form_submit_button("送出"):
                save_feedback(st.session_state.nickname or "匿名", fb_text)
                st.success("收到！感謝你的建議。")

# 分頁設計
tab1, tab2 = st.tabs(["🎮 當沖操盤室", "🏆 英雄榜"])

with tab1:
    # 歡迎語
    if not st.session_state.game_started:
        st.markdown("""
        <div style="text-align: center; padding: 50px;">
            <h1>🎢 體驗當沖的魅力，純粹好玩</h1>
            <p style="font-size: 20px;">隨機抽選美股熱門標的 • 隱藏時間軸 • 挑戰你的盤感</p>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            name_input = st.text_input("請輸入你的稱號", "當沖少年股神")
            if st.button("🔥 開始挑戰", use_container_width=True):
                st.session_state.nickname = name_input
                st.session_state.game_started = True
                reset_game()
                st.rerun()

    else:
        # --- 遊戲進行中 ---
        df = st.session_state.data
        if df is None:
            st.error("資料載入失敗，請重試")
            if st.button("重開"): reset_game(); st.rerun()
            st.stop()

        current_idx = st.session_state.step
        # 顯示範圍：過去 60 根
        display_start = max(0, current_idx - 60)
        display_df = df.iloc[display_start : current_idx+1]
        
        # 取得最新價格
        try:
            current_price = float(display_df.iloc[-1]['Close'])
        except:
            current_price = 0.0

        # --- A. 頂部資訊看板 ---
        market_val = st.session_state.position * current_price
        total_assets = st.session_state.balance + market_val
        unrealized = (current_price - st.session_state.avg_cost) * st.session_state.position if st.session_state.position > 0 else 0
        roi = ((total_assets - 100000) / 100000) * 100

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("💰 現金", f"${int(st.session_state.balance):,}")
        m2.metric("📦 庫存", f"{st.session_state.position} 股", f"${int(market_val):,}")
        m3.metric("📊 損益", f"${unrealized:,.0f}", delta_color="normal")
        m4.metric("🚀 總資產", f"${int(total_assets):,}", f"{roi:.2f}%")

        # --- B. 專業 K 線圖 (含指標與買賣點) ---
        
        # 建立三個子圖：K線(含標記)、成交量、MACD/KD
        fig = make_subplots(
            rows=3, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.03, 
            row_heights=[0.6, 0.2, 0.2],
            specs=[[{"secondary_y": False}], [{"secondary_y": False}], [{"secondary_y": False}]]
        )

        # 1. 主圖：K線 (台灣紅漲綠跌習慣)
        fig.add_trace(go.Candlestick(
            x=display_df['Bar_Index'],
            open=display_df['Open'], high=display_df['High'],
            low=display_df['Low'], close=display_df['Close'],
            name="K線",
            increasing_line_color='red', decreasing_line_color='green'
        ), row=1, col=1)

        # 主圖：均線
        fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA200'], line=dict(color='blue', width=2), name='200MA'), row=1, col=1)
        fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA60'], line=dict(color='orange', width=1), name='60MA'), row=1, col=1)

        # ★★★ 主圖：買賣點標記 (重點功能) ★★★
        # 過濾出「在當前顯示範圍內」的交易紀錄
        visible_trades = [t for t in st.session_state.trades_visual if display_start <= t['index'] <= current_idx]
        
        buy_x = [t['index'] for t in visible_trades if t['type'] == 'buy']
        buy_y = [t['price'] * 0.999 for t in visible_trades if t['type'] == 'buy'] # 畫在K棒下方一點點
        
        sell_x = [t['index'] for t in visible_trades if t['type'] == 'sell']
        sell_y = [t['price'] * 1.001 for t in visible_trades if t['type'] == 'sell'] # 畫在K棒上方一點點

        if buy_x:
            fig.add_trace(go.Scatter(
                x=buy_x, y=buy_y, mode='markers', name='買進點',
                marker=dict(symbol='triangle-up', size=12, color='darkred')
            ), row=1, col=1)
            
        if sell_x:
            fig.add_trace(go.Scatter(
                x=sell_x, y=sell_y, mode='markers', name='賣出點',
                marker=dict(symbol='triangle-down', size=12, color='darkgreen')
            ), row=1, col=1)

        # 2. 副圖1：成交量
        colors = ['red' if row['Open'] < row['Close'] else 'green' for index, row in display_df.iterrows()]
        fig.add_trace(go.Bar(
            x=display_df['Bar_Index'], y=display_df['Volume'],
            name="Volume", marker_color=colors
        ), row=2, col=1)

        # 3. 副圖2：MACD (預設) 或 KD
        # 這裡同時畫，但你可以透過圖例開關
        # MACD 柱狀
        hist_colors = ['red' if v > 0 else 'green' for v in display_df['MACD_Hist']]
        fig.add_trace(go.Bar(
            x=display_df['Bar_Index'], y=display_df['MACD_Hist'],
            name="MACD柱", marker_color=hist_colors
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=display_df['Bar_Index'], y=display_df['MACD'],
            line=dict(color='gold', width=1), name="DIF"
        ), row=3, col=1)
        fig.add_trace(go.Scatter(
            x=display_df['Bar_Index'], y=display_df['Signal'],
            line=dict(color='blue', width=1), name="DEM"
        ), row=3, col=1)

        # 版面設定
        fig.update_layout(
            title=f"標的: {st.session_state.ticker} (隱藏時間) - Price: {current_price:.2f}",
            height=700, # 加高圖表
            xaxis_rangeslider_visible=False,
            xaxis3_title="K棒編號 (Bar Index)", # X軸標籤
            margin=dict(l=10, r=10, t=30, b=10),
            showlegend=True
        )
        # 隱藏上方子圖的 X 軸標籤，只顯示最下面的
        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_xaxes(showticklabels=False, row=2, col=1)

        st.plotly_chart(fig, use_container_width=True)

        # --- C. 操作區 ---
        col_trade, col_ctrl, col_sys = st.columns([1.2, 1, 1])

        with col_trade:
            st.subheader("⚡ 下單")
            qty = st.number_input("股數", 10, 5000, 10, step=10, key="qty_input")
            b, s = st.columns(2)
            if b.button("🔴 買進", use_container_width=True):
                trade("buy", current_price, qty, current_idx)
            if s.button("🟢 賣出", use_container_width=True):
                trade("sell", current_price, qty, current_idx)

        with col_ctrl:
            st.subheader("⏩ 時間")
            if st.session_state.auto_play:
                if st.button("⏸️ 暫停", type="primary", use_container_width=True):
                    st.session_state.auto_play = False
                    st.rerun()
            else:
                if st.button("▶️ 自動播放", use_container_width=True):
                    st.session_state.auto_play = True
                    st.rerun()
            
            if st.button("⏭️ 下一步", disabled=st.session_state.auto_play, use_container_width=True):
                if st.session_state.step < len(df) - 1:
                    st.session_state.step += 1
                    st.rerun()

        with col_sys:
            st.subheader("🏁 系統")
            if st.button("結算 / 下一局", use_container_width=True):
                save_score(st.session_state.nickname, st.session_state.ticker, total_assets, roi)
                st.toast("成績已保存！")
                time.sleep(1)
                reset_game()
                st.rerun()

        # 自動播放邏輯
        if st.session_state.auto_play:
            if st.session_state.step < len(df) - 1:
                time.sleep(0.3) # 速度
                st.session_state.step += 1
                st.rerun()
            else:
                st.session_state.auto_play = False
                st.success("本局結束")

with tab2:
    st.title("🏆 當沖英雄榜")
    if os.path.exists(FILES["leaderboard"]):
        lb = pd.read_csv(FILES["leaderboard"])
        # 簡易美化表格
        st.dataframe(lb.sort_index(ascending=False), use_container_width=True)
    else:
        st.info("尚無紀錄")
