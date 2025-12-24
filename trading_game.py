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
        st.info("👈 按下按鈕進入戰場")

else:
    # 遊戲進行中：側邊欄全功能控制
    df = st.session_state.data
    if df is None:
        st.error("資料錯誤，請按重開")
        if st.sidebar.button("重開"): reset_game(); st.rerun()
        st.stop()

    curr_idx = st.session_state.step
    try:
        curr_row = df.iloc[curr_idx]
        curr_price = float(curr_row['Close'])
    except: curr_price = 0.0

    # 計算資產數據
    pos = st.session_state.position
    avg = st.session_state.avg_cost
    
    if pos > 0:
        unrealized = (curr_price - avg) * pos
        pos_label = f"🔴 多單 {pos} 股"
    elif pos < 0:
        unrealized = (avg - curr_price) * abs(pos)
        pos_label = f"🟢 空單 {abs(pos)} 股"
    else:
        unrealized = 0
        pos_label = "無庫存"

    total_assets = st.session_state.balance + (abs(pos) * curr_price if pos > 0 else 0) + (unrealized if pos < 0 else 0)
    # 修正資產顯示：多單是市值加現金，空單是保證金邏輯(簡化為現金+損益)
    # 為求簡單顯示：總權益 = 現金 + 未實現損益 (若為多單，現金已扣除成本)
    total_equity = st.session_state.balance + (pos * curr_price if pos > 0 else 0) # 這是錯的，修正邏輯
    # 正確邏輯：餘額(已扣成本) + 市值(多單) OR 餘額(已扣成本) + 損益補回(空單)
    # 這裡採用最簡單的：
    # 總資產 = 初始 10萬 + 已實現 + 未實現
    # 但因為沒存初始，我們用：當前現金 + (部位市值 - 成本) [多單] 
    # 這裡顯示 "權益數 (Equity)" 最準
    equity = st.session_state.balance + (pos * curr_price if pos > 0 else 0) 
    # 再次修正：因為買入時已經扣除現金，所以多單時權益=現金+市值。空單時買入扣除現金(保證金)，權益=現金+未實現。
    # 為了不讓使用者混淆，我們顯示 "預估總資產"
    est_total_assets = st.session_state.balance
    if pos > 0: est_total_assets += (pos * curr_price)
    elif pos < 0: est_total_assets += (abs(pos) * avg) + unrealized # 退回保證金+損益
    
    roi = ((est_total_assets - 100000) / 100000) * 100

    # --- 左側控制面板 (Sidebar) ---
    with st.sidebar:
        st.header(f"👤 {st.session_state.nickname}")
        
        # 1. 資產看板
        with st.expander("💼 資產狀態", expanded=True):
            st.metric("💰 總權益", f"${int(est_total_assets):,}", f"{roi:.2f}%")
            st.metric("💵 現金餘額", f"${int(st.session_state.balance):,}")
            st.divider()
            st.info(pos_label)
            if pos != 0:
                st.metric("成本價", f"${avg:.2f}")
                st.metric("未實現損益", f"${int(unrealized):,}", delta_color="normal")

        # 2. 下單區
        st.markdown("### ⚡ 快速下單")
        st.write(f"當前價: **{curr_price:.2f}**")
        qty = st.number_input("股數", 10, 5000, 10, step=10)
        
        c1, c2 = st.columns(2)
        buy_label = "🔴 回補/買進" if pos < 0 else "🔴 買進"
        sell_label = "🟢 賣出/放空" if pos <= 0 else "🟢 賣出"

        if c1.button(buy_label, use_container_width=True):
            execute_trade("buy", curr_price, qty, curr_idx)
            st.rerun()
        if c2.button(sell_label, use_container_width=True):
            execute_trade("sell", curr_price, qty, curr_idx)
            st.rerun()

        st.divider()

        # 3. 遊戲控制
        st.markdown("### 🎮 盤勢控制")
        if st.session_state.auto_play:
            if st.button("⏸️ 暫停", type="primary", use_container_width=True):
                st.session_state.auto_play = False
                st.rerun()
        else:
            col_play, col_next = st.columns(2)
            if col_play.button("▶️ 播放", use_container_width=True):
                st.session_state.auto_play = True
                st.rerun()
            if col_next.button("⏭️ 下一根", use_container_width=True):
                if st.session_state.step < len(df) - 1:
                    st.session_state.step += 1
                    st.rerun()

        st.divider()
        if st.button("🏁 結算成績 / 下一局", use_container_width=True):
            save_score(st.session_state.nickname, st.session_state.ticker, est_total_assets, roi)
            st.success("✅ 成績已保存！")
            time.sleep(1)
            reset_game()
            st.rerun()

        # 4. 意見回饋 Popover
        with st.popover("💬 意見回饋 / Bug 回報"):
            with st.form("fb_form"):
                fb_txt = st.text_area("內容", height=100)
                if st.form_submit_button("送出"): 
                    save_feedback(st.session_state.nickname, fb_txt)
                    st.toast("感謝回饋")

    # --- 右側主畫面 (Tabs) ---
    tab_game, tab_rank, tab_log = st.tabs(["📊 操盤室 (K線圖)", "🏆 英雄榜", "📜 版本紀錄"])

    with tab_game:
        # 繪製圖表 (全螢幕寬度)
        display_start = max(0, curr_idx - 100)
        display_df = df.iloc[display_start : curr_idx+1]
        
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                          row_heights=[0.6, 0.2, 0.2], specs=[[{}],[{}],[{}]])
        
        # K線
        fig.add_trace(go.Candlestick(
            x=display_df['Bar_Index'], open=display_df['Open'], high=display_df['High'],
            low=display_df['Low'], close=display_df['Close'], name="K線",
            increasing_line_color='red', decreasing_line_color='green'
        ), row=1, col=1)
        
        # 均線
        fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA200'], line=dict(color='blue', width=2), name='200MA'), row=1, col=1)
        
        # 交易標記
        visible = [t for t in st.session_state.trades_visual if display_start <= t['index'] <= curr_idx]
        bx = [t['index'] for t in visible if t['type']=='buy']
        by = [t['price']*0.99 for t in visible if t['type']=='buy']
        sx = [t['index'] for t in visible if t['type']=='sell']
        sy = [t['price']*1.01 for t in visible if t['type']=='sell']
        
        if bx: fig.add_trace(go.Scatter(x=bx, y=by, mode='markers', name='買/補', marker=dict(symbol='triangle-up', size=12, color='darkred')), row=1, col=1)
        if sx: fig.add_trace(go.Scatter(x=sx, y=sy, mode='markers', name='賣/空', marker=dict(symbol='triangle-down', size=12, color='darkgreen')), row=1, col=1)

        # 副圖
        colors = ['red' if r['Open'] < r['Close'] else 'green' for i, r in display_df.iterrows()]
        fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['Volume'], marker_color=colors, name="Vol"), row=2, col=1)
        
        hist_c = ['red' if v > 0 else 'green' for v in display_df['MACD_Hist']]
        fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['MACD_Hist'], marker_color=hist_c, name="MACD"), row=3, col=1)
        fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MACD'], line=dict(color='gold', width=1)), row=3, col=1)
        fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['Signal'], line=dict(color='blue', width=1)), row=3, col=1)

        fig.update_layout(height=700, margin=dict(l=20, r=20, t=30, b=20), showlegend=False, 
                        title=f"{st.session_state.ticker} - Price: {curr_price:.2f}")
        fig.update_xaxes(showticklabels=False, row=1, col=1)
        fig.update_xaxes(showticklabels=False, row=2, col=1)
        st.plotly_chart(fig, use_container_width=True)
        
        # 底部交易紀錄
        with st.expander("📝 本局交易流水帳"):
            for log in reversed(st.session_state.history):
                st.text(log)

        # 自動播放邏輯
        if st.session_state.auto_play:
            if st.session_state.step < len(df) - 1:
                time.sleep(0.5)
                st.session_state.step += 1
                st.rerun()
            else:
                st.session_state.auto_play = False

    with tab_rank:
        st.markdown("### 🏆 華爾街英雄榜")
        if os.path.exists(FILES["leaderboard"]):
            lb = pd.read_csv(FILES["leaderboard"])
            st.dataframe(lb.sort_index(ascending=False), use_container_width=True)
        else:
            st.info("尚無紀錄")

    with tab_log:
        st.markdown(VERSION_HISTORY)
