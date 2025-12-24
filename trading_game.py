import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import random
import time
import os

# --- 1. 全域設定 ---
st.set_page_config(page_title="當沖模擬戰 - 專業版", layout="wide", page_icon="📉")

# CSS 優化：側邊欄按鈕與字體調整
st.markdown("""
<style>
    /* 側邊欄按鈕樣式 */
    section[data-testid="stSidebar"] .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
    }
    /* 買賣按鈕顏色 */
    section[data-testid="stSidebar"] button:contains("買進") {
        background-color: #ffcccc;
        color: #cc0000;
        border: 1px solid #cc0000;
    }
    section[data-testid="stSidebar"] button:contains("賣出") {
        background-color: #ccffcc;
        color: #006600;
        border: 1px solid #006600;
    }
    /* 指標字體微調 */
    [data-testid="stMetricValue"] { font-size: 20px; }
</style>
""", unsafe_allow_html=True)

FILES = {"leaderboard": "leaderboard.csv", "feedback": "feedback.csv"}

# --- 2. 版本歷史紀錄 (Changelog) ---
VERSION_HISTORY = """
### 📜 版本更新紀錄 (Changelog)

#### v1.5 - 介面重構與發布準備
* **[UI]** 介面大改版：將操作面板移至左側側邊欄，解決 K 線圖超出邊界問題。
* **[Feature]** 新增版本歷史紀錄分頁。
* **[Fix]** 優化手機與窄螢幕的顯示效果。

#### v1.4 - 空軍總司令 (Short Selling)
* **[Feature]** 新增「雙向交易」功能，支援放空 (Short) 操作。
* **[Feature]** 智能判斷：無庫存時賣出自動轉為空單，有空單時買進自動回補。
* **[UI]** 新增左右分割視窗模式 (v1.5 已整合至側邊欄)。

#### v1.3 - 盲測模式與技術指標
* **[Core]** 實裝「時間馬賽克」：隱藏真實日期，改為 K 棒編號，防止背題作弊。
* **[Chart]** 導入 Plotly 互動式圖表，新增買賣點標記 (Markers)。
* **[Analysis]** 新增 MACD、KD 指標與成交量副圖。

#### v1.2 - 英雄榜與數據持久化
* **[Data]** 建立 CSV 資料庫，紀錄玩家歷史成績與排行榜。
* **[System]** 優化檔案讀寫邏輯，確保重啟程式後紀錄不遺失。

#### v1.1 - 生命線戰法
* **[Indicator]** 加入 200MA (生命線) 與 60MA (季線) 輔助判斷。
* **[Data]** 擴大數據下載範圍至一個月，確保均線運算正確。

#### v1.0 - 雛形誕生
* **[Init]** 專案啟動：基於 yfinance 與 Streamlit 的當沖練習器。
* **[Core]** 實裝隨機選股、資金計算、下單基礎邏輯。
"""

# --- 3. 初始化 Session State ---
default_values = {
    'balance': 100000.0,
    'position': 0,      # 正數=多單，負數=空單
    'avg_cost': 0.0,
    'step': 200,
    'history': [],
    'trades_visual': [],
    'data': None,
    'ticker': "",
    'nickname': "",
    'game_started': False,
    'auto_play': False
}

for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 4. 核心邏輯函數 ---

def calculate_technical_indicators(df):
    df['MA200'] = df['Close'].rolling(window=200).mean()
    df['MA60'] = df['Close'].rolling(window=60).mean()
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['Signal']
    # KD
    low_min = df['Low'].rolling(window=9).min()
    high_max = df['High'].rolling(window=9).max()
    df['RSV'] = (df['Close'] - low_min) / (high_max - low_min) * 100
    df['K'] = df['RSV'].ewm(com=2).mean()
    df['D'] = df['K'].ewm(com=2).mean()
    return df

def load_data():
    tickers = ['NVDA', 'TSLA', 'AMD', 'TQQQ', 'SOXL', 'MSTR', 'COIN', 'NFLX', 'AAPL', 'MSFT']
    selected_ticker = random.choice(tickers)
    try:
        df = yf.download(selected_ticker, period="1mo", interval="5m", progress=False)
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        if len(df) < 300: return None, None
        df = calculate_technical_indicators(df)
        df.reset_index(inplace=True)
        df['Bar_Index'] = range(len(df))
        max_start = len(df) - 150
        st.session_state.step = random.randint(200, max_start) if max_start > 200 else 200
        return selected_ticker, df
    except: return None, None

def reset_game():
    st.session_state.balance = 100000.0
    st.session_state.position = 0
    st.session_state.avg_cost = 0.0
    st.session_state.history = []
    st.session_state.trades_visual = []
    st.session_state.auto_play = False
    st.session_state.ticker, st.session_state.data = load_data()

def execute_trade(action, price, qty, current_step_index):
    price = float(price)
    pos = st.session_state.position
    avg = st.session_state.avg_cost
    direction = 1 if action == "buy" else -1
    trade_qty = qty * direction 
    fee = price * qty * 0.001 # 手續費
    
    # A. 加碼 (方向相同)
    if (pos >= 0 and action == "buy") or (pos <= 0 and action == "sell"):
        cost = price * qty
        if st.session_state.balance >= cost:
            st.session_state.balance -= (cost + fee)
            total_cost = (avg * abs(pos)) + cost
            new_pos_size = abs(pos) + qty
            st.session_state.avg_cost = total_cost / new_pos_size
            st.session_state.position += trade_qty
            
            tag = "🔴 加碼做多" if action == "buy" else "🟢 加碼放空"
            st.session_state.history.append(f"{tag} {qty}股 @ {price:.2f}")
        else:
            st.toast("❌ 資金不足")
            return

    # B. 平倉/反手
    else:
        cover_qty = min(abs(pos), qty)
        remaining_qty = qty - cover_qty
        
        # 平倉部分
        if pos > 0: # 多單賣出
            profit = (price - avg) * cover_qty
            revenue = price * cover_qty
            st.session_state.balance += (revenue - fee)
            tag_close = "🟢 獲利賣出" if profit > 0 else "🟢 停損賣出"
        else: # 空單回補
            profit = (avg - price) * cover_qty
            cost = price * cover_qty
            st.session_state.balance -= (cost + fee)
            st.session_state.balance += (cost + profit) 
            tag_close = "🔴 空單回補" if profit > 0 else "🔴 空單停損"

        st.session_state.position += (cover_qty * direction)
        st.session_state.history.append(f"{tag_close} {cover_qty}股 (損益: {profit:.1f})")

        # 反手建倉部分
        if remaining_qty > 0:
            cost = price * remaining_qty
            if st.session_state.balance >= cost:
                st.session_state.balance -= (cost + fee)
                st.session_state.position += (remaining_qty * direction)
                st.session_state.avg_cost = price
                tag_new = "🔴 反手做多" if action == "buy" else "🟢 反手放空"
                st.session_state.history.append(f"{tag_new} {remaining_qty}股 @ {price:.2f}")

    marker_type = 'buy' if action == 'buy' else 'sell'
    st.session_state.trades_visual.append({'index': current_step_index, 'price': price, 'type': marker_type})

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

# --- 5. 介面呈現 (側邊欄佈局) ---

# 頂部歡迎頁 (未開始時)
if not st.session_state.game_started:
    st.markdown("<h1 style='text-align: center;'>📉 當沖模擬戰：操盤手版</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>請在左側輸入暱稱開始遊戲</p>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("🚀 登入系統")
        name = st.text_input("輸入你的綽號", "華爾街之狼")
        if st.button("🔥 開始當沖", use_container_width=True):
            st.session_state.nickname = name
            st.session_state.game_started = True
            reset_game()
            st.rerun()
        st.info("
