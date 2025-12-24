import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import random
import time
import os

# --- 1. 全域設定 ---
st.set_page_config(page_title="當沖模擬戰 - 操盤手版", layout="wide", page_icon="📉")

# CSS 優化：讓右側控制面板更緊湊，按鈕更好按
st.markdown("""
<style>
    .stButton>button {
        width: 100%;
        height: 60px;
        font-size: 20px;
        font-weight: bold;
        border-radius: 12px;
    }
    /* 紅綠按鈕顏色 */
    div[data-testid="column"] button:contains("買進") {
        border: 2px solid #ff4b4b;
        color: #ff4b4b;
    }
    div[data-testid="column"] button:contains("賣出") {
        border: 2px solid #00c853;
        color: #00c853;
    }
    /* 指標字體 */
    [data-testid="stMetricValue"] { font-size: 22px; }
</style>
""", unsafe_allow_html=True)

FILES = {"leaderboard": "leaderboard.csv", "feedback": "feedback.csv"}

# --- 2. 初始化 Session State ---
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

# --- 3. 核心邏輯 (含放空運算) ---

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
    tickers = ['NVDA', 'TSLA', 'AMD', 'TQQQ', 'SOXL', 'MSTR', 'COIN', 'NFLX']
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

# ★★★ 雙向交易核心邏輯 ★★★
def execute_trade(action, price, qty, current_step_index):
    price = float(price)
    pos = st.session_state.position
    avg = st.session_state.avg_cost
    
    # 定義交易方向：1 為買進 (做多/補空), -1 為賣出 (賣出/放空)
    direction = 1 if action == "buy" else -1
    trade_qty = qty * direction 

    # 1. 計算手續費 (假設 0.1%)
    fee = price * qty * 0.001
    
    # 2. 判斷交易類型
    # A. 加碼 (方向相同)：多單買進 OR 空單賣出
    if (pos >= 0 and action == "buy") or (pos <= 0 and action == "sell"):
        cost = price * qty
        if st.session_state.balance >= cost:
            st.session_state.balance -= (cost + fee)
            # 更新平均成本 (加權平均)
            total_cost = (avg * abs(pos)) + cost
            new_pos_size = abs(pos) + qty
            st.session_state.avg_cost = total_cost / new_pos_size
            st.session_state.position += trade_qty
            
            # 紀錄
            tag = "🔴 加碼做多" if action == "buy" else "🟢 加碼放空"
            st.session_state.history.append(f"{tag} {qty}股 @ {price:.2f}")
        else:
            st.toast("❌ 資金不足以加碼")
            return

    # B. 減碼/平倉/反手 (方向相反)
    else:
        # 這次交易能平掉多少倉位？
        cover_qty = min(abs(pos), qty)
        remaining_qty = qty - cover_qty # 如果還有剩，就是要反手建立新倉
        
        # --- 第一步：先平倉 ---
        # 計算損益
        if pos > 0: # 原本多單，現在賣出
            profit = (price - avg) * cover_qty
            revenue = price * cover_qty
            st.session_state.balance += (revenue - fee)
            tag_close = "🟢 獲利賣出" if profit > 0 else "🟢 停損賣出"
        else: # 原本空單，現在買進
            profit = (avg - price) * cover_qty # 空單獲利 = 賣價(高) - 買價(低)
            cost = price * cover_qty
            st.session_state.balance -= (cost + fee)
            # 空單平倉時，保證金/本金返還邏輯簡化：直接把損益加回餘額
            # (這裡做簡單處理：餘額已在開倉時扣除，平倉只加回損益部分+本金變動)
            # 更正：開倉時已扣全額現金，平倉時補回 (成本+損益)
            st.session_state.balance += (cost + profit) 
            tag_close = "🔴 空單回補" if profit > 0 else "🔴 空單停損"

        st.session_state.position += (cover_qty * direction) # 修正倉位
        
        icon = "💰" if profit > 0 else "💸"
        st.session_state.history.append(f"{tag_close} {cover_qty}股 (損益: {profit:.1f}) {icon}")

        # --- 第二步：如果有剩餘股數，建立新倉 (反手) ---
        if remaining_qty > 0:
            cost = price * remaining_qty
            if st.session_state.balance >= cost:
                st.session_state.balance -= (cost + fee)
                st.session_state.position += (remaining_qty * direction)
                st.session_state.avg_cost = price # 新倉成本即為當前價
                
                tag_new = "🔴 反手做多" if action == "buy" else "🟢 反手放空"
                st.session_state.history.append(f"{tag_new} {remaining_qty}股 @ {price:.2f}")
            else:
                st.toast(f"⚠️ 資金不足以建立反手新倉 (已平倉 {cover_qty} 股)")

    # 視覺化標記
    marker_type = 'buy' if action == 'buy' else 'sell'
    st.session_state.trades_visual.append({'index': current_step_index, 'price': price, 'type': marker_type})


def save_score(player, ticker, assets, roi):
    new_entry = pd.DataFrame([{
        "日期": time.strftime("%Y-%m-%d %H:%M"), "玩家": player,
        "股票": ticker, "最終資產": round(assets, 2), "報酬率": f"{roi:.2f}%"
    }])
    # 使用 mode='a' (append) 確保不覆蓋舊資料
    header = not os.path.exists(FILES["leaderboard"])
    new_entry.to_csv(FILES["leaderboard"], mode='a', header=header, index=False)

def save_feedback(name, text):
    with open(FILES["feedback"], "a", encoding="utf-8") as f:
        f.write(f"[{time.strftime('%Y-%m-%d')}] {name}: {text}\n")

# --- 4. 介面呈現 ---

with st.sidebar:
    st.header("⚙️ 設定")
    with st.popover("💬 意見回饋"):
        with st.form("fb"):
            txt = st.text_area("內容", height=100)
            if st.form_submit_button("送出"): 
                save_feedback(st.session_state.nickname, txt)
                st.toast("已送出")

# 分頁
tab1, tab2 = st.tabs(["🎮 操盤室", "🏆 英雄榜"])

with tab1:
    if not st.session_state.game_started:
        st.markdown("<h1 style='text-align: center;'>📉 當沖模擬戰：多空雙巴</h1>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            name = st.text_input("輸入你的綽號", "空軍總司令")
            if st.button("🔥 開始當沖", use_container_width=True):
                st.session_state.nickname = name
                st.session_state.game_started = True
                reset_game()
                st.rerun()
    else:
        df = st.session_state.data
        if df is None:
            st.error("資料錯誤，請重開")
            if st.button("重開"): reset_game(); st.rerun()
            st.stop()

        # 數據準備
        curr_idx = st.session_state.step
        display_start = max(0, curr_idx - 80) # 看更長一點
        display_df = df.iloc[display_start : curr_idx+1]
        
        try:
            curr_price = float(display_df.iloc[-1]['Close'])
        except: curr_price = 0.0

        # 計算損益與狀態
        pos = st.session_state.position
        avg = st.session_state.avg_cost
        
        # 未實現損益計算 (區分多空)
        if pos > 0: # 多單
            unrealized = (curr_price - avg) * pos
            pos_label = f"🔴 多單 {pos} 股"
        elif pos < 0: # 空單
            unrealized = (avg - curr_price) * abs(pos)
            pos_label = f"🟢 空單 {abs(pos)} 股"
        else:
            unrealized = 0
            pos_label = "無庫存"

        market_val = abs(pos) * curr_price
        total_assets = st.session_state.balance + unrealized # 簡易估算：現金+未實現
        roi = ((total_assets - 100000) / 100000) * 100

        # --- 介面佈局：左右分割 ---
        # 左邊是圖表 (75%)，右邊是操作盤 (25%)
        col_chart, col_ctrl = st.columns([3, 1])

        with col_chart:
            # 畫圖
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.02, 
                              row_heights=[0.6, 0.2, 0.2], specs=[[{}],[{}],[{}]])
            
            # K線
            fig.add_trace(go.Candlestick(
                x=display_df['Bar_Index'], open=display_df['Open'], high=display_df['High'],
                low=display_df['Low'], close=display_df['Close'], name="K線",
                increasing_line_color='red', decreasing_line_color='green'
            ), row=1, col=1)
            
            # 均線
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA200'], line=dict(color='blue', width=2), name='200MA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA60'], line=dict(color='orange', width=1), name='60MA'), row=1, col=1)

            # 交易標記
            visible = [t for t in st.session_state.trades_visual if display_start <= t['index'] <= curr_idx]
            bx = [t['index'] for t in visible if t['type']=='buy']
            by = [t['price']*0.998 for t in visible if t['type']=='buy']
            sx = [t['index'] for t in visible if t['type']=='sell']
            sy = [t['price']*1.002 for t in visible if t['type']=='sell']
            
            if bx: fig.add_trace(go.Scatter(x=bx, y=by, mode='markers', name='買/補', marker=dict(symbol='triangle-up', size=14, color='darkred')), row=1, col=1)
            if sx: fig.add_trace(go.Scatter(x=sx, y=sy, mode='markers', name='賣/空', marker=dict(symbol='triangle-down', size=14, color='darkgreen')), row=1, col=1)

            # 副圖
            colors = ['red' if r['Open'] < r['Close'] else 'green' for i, r in display_df.iterrows()]
            fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['Volume'], marker_color=colors, name="Vol"), row=2, col=1)
            
            hist_c = ['red' if v > 0 else 'green' for v in display_df['MACD_Hist']]
            fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['MACD_Hist'], marker_color=hist_c, name="MACD"), row=3, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MACD'], line=dict(color='gold', width=1)), row=3, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['Signal'], line=dict(color='blue', width=1)), row=3, col=1)

            fig.update_layout(height=800, margin=dict(l=10, r=10, t=30, b=10), showlegend=False, 
                            title=f"{st.session_state.ticker} (Bar: {curr_idx}) Price: {curr_price:.2f}")
            fig.update_xaxes(showticklabels=False, row=1, col=1)
            fig.update_xaxes(showticklabels=False, row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)

        with col_ctrl:
            # 右側控制面板
            st.markdown("### 💼 資產看板")
            st.metric("總資產 (含未實現)", f"${int(total_assets):,}", f"{roi:.2f}%")
            st.metric("現金餘額", f"${int(st.session_state.balance):,}")
            st.divider()
            
            st.markdown("### 📦 庫存狀態")
            st.info(pos_label) # 顯示 "多單 10 股" 或 "空單 5 股"
            st.metric("平均成本", f"${avg:.2f}")
            st.metric("未實現損益", f"${int(unrealized):,}", delta_color="normal")
            st.divider()

            st.markdown("### ⚡ 下單操作")
            st.write(f"當前價: **{curr_price:.2f}**")
            qty = st.number_input("股數", 10, 5000, 10, step=10)
            
            c1, c2 = st.columns(2)
            # 按鈕邏輯
            # 如果是空單，買進顯示 "回補"；如果是多單或無，買進顯示 "買進"
            buy_label = "🔴 回補/買進" if pos < 0 else "🔴 買進"
            sell_label = "🟢 賣出/放空" if pos <= 0 else "🟢 賣出"

            if c1.button(buy_label, use_container_width=True):
                execute_trade("buy", curr_price, qty, curr_idx)
                st.rerun()
            
            if c2.button(sell_label, use_container_width=True):
                execute_trade("sell", curr_price, qty, curr_idx)
                st.rerun()

            st.divider()
            st.markdown("### ⏩ 盤勢控制")
            
            if st.session_state.auto_play:
                if st.button("⏸️ 暫停", type="primary", use_container_width=True):
                    st.session_state.auto_play = False
                    st.rerun()
            else:
                if st.button("▶️ 自動播放", use_container_width=True):
                    st.session_state.auto_play = True
                    st.rerun()
                if st.button("⏭️ 下一根", use_container_width=True):
                    if st.session_state.step < len(df) - 1:
                        st.session_state.step += 1
                        st.rerun()

            st.divider()
            if st.button("🏁 結算/下一局", use_container_width=True):
                save_score(st.session_state.nickname, st.session_state.ticker, total_assets, roi)
                st.success("✅ 成績已保存！")
                time.sleep(1)
                reset_game()
                st.rerun()
            
            # 交易紀錄 (顯示最近5筆)
            with st.expander("📜 最近交易", expanded=True):
                for log in reversed(st.session_state.history[-5:]):
                    st.caption(log)

            # 自動播放邏輯
            if st.session_state.auto_play:
                if st.session_state.step < len(df) - 1:
                    time.sleep(0.5)
                    st.session_state.step += 1
                    st.rerun()
                else:
                    st.session_state.auto_play = False

with tab2:
    st.title("🏆 華爾街英雄榜")
    if os.path.exists(FILES["leaderboard"]):
        lb = pd.read_csv(FILES["leaderboard"])
        st.dataframe(lb.sort_index(ascending=False), use_container_width=True)
    else:
        st.info("目前還沒有紀錄，快去創造傳奇！")
