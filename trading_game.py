import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import random
import time
import os
from datetime import datetime
import math

# --- 1. 全域設定 ---
st.set_page_config(page_title="交易挑戰賽", layout="wide", page_icon="⚔️")

# CSS 優化
st.markdown("""
<style>
    /* 1. 全域容器 */
    .block-container { padding-top: 1rem !important; padding-bottom: 0rem !important; max-width: 100%; }
    footer {visibility: hidden;} #MainMenu {visibility: hidden;}

    /* 2. 側邊欄與按鈕 */
    div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
    section[data-testid="stSidebar"] .stButton>button { width: 100%; border-radius: 8px; font-weight: bold; height: 50px; font-size: 16px; }
    div[data-testid="stSidebar"] button:contains("買進") { background-color: #ffe6e6 !important; color: #d90000 !important; border: 1px solid #d90000 !important; }
    div[data-testid="stSidebar"] button:contains("賣出") { background-color: #e6ffe6 !important; color: #008000 !important; border: 1px solid #008000 !important; }
    
    /* 3. 選單 Radio Button */
    div[role="radiogroup"] { background-color: transparent; padding: 5px; border-radius: 10px; margin-bottom: 10px; }
    div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] p { color: #333333 !important; font-weight: 900 !important; font-size: 16px !important; }
    div[role="radiogroup"] label { background-color: #e0e0e0 !important; border: 1px solid #cccccc !important; margin-right: 5px !important; padding: 10px 15px !important; border-radius: 8px !important; flex-grow: 1; text-align: center; }
    div[role="radiogroup"] label[data-checked="true"] { background-color: #ff4b4b !important; border: 1px solid #ff4b4b !important; }
    div[role="radiogroup"] label[data-checked="true"] div[data-testid="stMarkdownContainer"] p { color: #ffffff !important; }

    /* 4. 彈窗與提示 */
    .reveal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.85); z-index: 9998; backdrop-filter: blur(5px); }
    .reveal-box { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 85%; max-width: 400px; background-color: #ffffff; color: #333; border-radius: 20px; padding: 30px; text-align: center; z-index: 9999; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 4px solid #4CAF50; animation: popIn 0.5s; }
    .reveal-title { font-size: 28px; font-weight: 900; color: #4CAF50; margin-bottom: 10px; }
    .reveal-stock { font-size: 22px; font-weight: bold; color: #333; margin-bottom: 20px; border-bottom: 2px dashed #eee; padding-bottom: 10px;}
    .reveal-stat { font-size: 18px; margin: 5px 0; color: #555; }
    .reveal-stat span { font-weight: bold; color: #000; }
    @keyframes popIn { 0% { transform: translate(-50%, -50%) scale(0.5); opacity: 0; } 100% { transform: translate(-50%, -50%) scale(1); opacity: 1; } }

    .margin-call-box { position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 85%; max-width: 400px; padding: 30px; background-color: #ffcccc; color: #cc0000; border-radius: 12px; text-align: center; font-size: 24px; font-weight: bold; border: 4px solid #ff0000; z-index: 10000; box-shadow: 0 0 20px rgba(255, 0, 0, 0.5); }

    /* 5. 倒數計時 */
    .countdown-box {
        position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
        font-size: 180px; font-weight: 900; color: #FFD700;
        text-shadow: 0 0 30px rgba(0,0,0,0.9);
        z-index: 10001;
        animation: pulse 0.8s infinite;
        font-family: 'Arial', sans-serif;
    }
    @keyframes pulse { 0% { transform: translate(-50%, -50%) scale(0.8); opacity: 0; } 50% { transform: translate(-50%, -50%) scale(1.2); opacity: 1; } 100% { transform: translate(-50%, -50%) scale(1); opacity: 0; } }

    /* 其他 */
    .asset-box { padding: 10px; background-color: #f0f2f6; border-radius: 8px; margin-bottom: 10px; }
    .asset-label { font-size: 14px; color: #666; font-weight: bold; }
    .asset-value { font-size: 20px; font-weight: bold; color: #333; }
    .price-text { font-size: 26px; font-weight: bold; color: #333; margin-bottom: 5px; }
    .tip-box { background-color: #e3f2fd; color: #0d47a1; padding: 10px; border-radius: 5px; font-size: 14px; border-left: 4px solid #2196f3; margin-top: 10px; }
    .warning-text { color: #ff9800; font-weight: bold; padding: 10px; border: 1px dashed #ff9800; border-radius: 5px; margin-bottom: 20px; text-align: center; background-color: #fff3e0; line-height: 1.6; font-size: 14px; }
    .warning-text a { color: #E1306C; text-decoration: none; border-bottom: 1px dashed #E1306C; }
    
    .js-plotly-plot { touch-action: pan-y !important; }
    .stPlotlyChart { touch-action: pan-y !important; }
    
    .signal-bull { color: #d90000; font-weight: bold; }
    .signal-bear { color: #008000; font-weight: bold; }
    .signal-wait { color: #666; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

FILES = { "leaderboard": "leaderboard_tw_v4.csv", "feedback": "feedback.csv", "traffic": "traffic_log.csv" }

HOT_STOCKS_MAP = {
    '6462.TWO': '神盾', '8054.TWO': '安國', '6684.TWO': '安格', '3529.TWO': '力旺', 
    '6531.TW': '愛普', '6643.TW': 'M31', '3661.TW': '世芯-KY',
    '4979.TW': '華星光', '3363.TW': '上詮', '3450.TW': '聯鈞', '4908.TWO': '前鼎', 
    '3163.TWO': '波若威', '4977.TW': '眾達-KY',
    '1519.TW': '華城', '1514.TW': '亞力', '1513.TW': '中興電', '1609.TW': '大亞',
    '6806.TW': '森崴能源', '9958.TW': '世紀鋼',
    '6472.TWO': '保瑞', '4763.TWO': '材料-KY', '1795.TWO': '美時', '4114.TWO': '健喬',
    '3017.TW': '奇鋐', '3324.TWO': '雙鴻', '8996.TWO': '高力', '3653.TW': '健策',
    '3032.TW': '偉訓', '8210.TW': '勤誠',
    '3583.TW': '辛耘', '3131.TW': '弘塑', '6187.TWO': '萬潤', '5443.TWO': '均豪'
}

# --- 3. 初始化 Session State ---
default_values = {
    'balance': 10000000.0, 'position': 0, 'avg_cost': 0.0, 'step': 0,
    'history': [], 'trades_visual': [], 'data': None, 'ticker': "",
    'stock_name': "", 'nickname': "", 'game_started': False, 
    'auto_play': False, 'first_load': True, 'is_admin': False,
    'trade_returns': [], 'last_equity': 10000000.0,
    'show_hints': False,
    'round': 1, 'max_rounds': 3, 'in_countdown': False,
    'nav_selection': "📊 操盤室"
}

for key, value in default_values.items():
    if key not in st.session_state: st.session_state[key] = value

# --- 4. 後台與數據系統 ---
def log_traffic():
    if 'traffic_logged' not in st.session_state:
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_data = pd.DataFrame([{"Time": timestamp, "Page": "Home"}])
            hdr = not os.path.exists(FILES["traffic"])
            new_data.to_csv(FILES["traffic"], mode='a', header=hdr, index=False)
            st.session_state.traffic_logged = True
        except: pass

def get_admin_data():
    data = {}
    if os.path.exists(FILES["traffic"]):
        df_t = pd.read_csv(FILES["traffic"]); df_t['Time'] = pd.to_datetime(df_t['Time']); data['traffic'] = df_t
    else: data['traffic'] = pd.DataFrame()
    if os.path.exists(FILES["feedback"]):
        try:
            with open(FILES["feedback"], "r", encoding="utf-8") as f: data['feedback'] = f.readlines()
        except: data['feedback'] = []
    else: data['feedback'] = []
    if os.path.exists(FILES["leaderboard"]): data['leaderboard'] = pd.read_csv(FILES["leaderboard"])
    else: data['leaderboard'] = pd.DataFrame()
    return data

# --- 5. 核心邏輯 ---
def calculate_technical_indicators(df):
    try:
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA22'] = df['Close'].rolling(window=22).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA240'] = df['Close'].rolling(window=240).mean()
        df['MA22_Slope'] = df['MA22'].diff()
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        
        df['Signal_Bull'] = ((df['MA5'] > df['MA22']) & (df['MA22_Slope'] > 0) & (df['MACD_Hist'] > 0) & (df['MACD_Hist'] > df['MACD_Hist'].shift(1)))
        df['Signal_Bear'] = ((df['MA5'] < df['MA22']) & (df['MA22_Slope'] < 0) & (df['MACD_Hist'] < 0) & (df['MACD_Hist'] < df['MACD_Hist'].shift(1)))
        return df
    except: return df

def load_data():
    max_retries = 60 # 限制嘗試次數，避免無限迴圈
    ticker_list = list(HOT_STOCKS_MAP.keys())
    
    status_placeholder = st.empty() # 用來顯示搜尋進度
    
    for i in range(max_retries):
        selected_ticker = random.choice(ticker_list)
        status_placeholder.info(f"🔍 正在掃描市場標的：{HOT_STOCKS_MAP[selected_ticker]} ({selected_ticker})...")
        
        try:
            df = yf.download(selected_ticker, period="60d", interval="5m", progress=False)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df[df['Volume'] > 0]
            if len(df) < 300: continue
            
            # 價格過濾: <= 200
            current_price = df['Close'].iloc[-1]
            if current_price > 200: continue

            # 波動過濾
            df['Fluctuation'] = (df['High'] - df['Low']) / df['Open'] * 100
            if df['Fluctuation'].mean() < 0.15 or df['Fluctuation'].max() < 1.5: continue

            df = calculate_technical_indicators(df)
            df.dropna(inplace=True); df.reset_index(inplace=True); df['Bar_Index'] = range(len(df))
            if len(df) < 200: continue
            
            max_start = len(df) - 150
            start_idx = random.randint(50, max_start) if max_start > 50 else 50
            st.session_state.step = start_idx
            st.session_state.first_load = True
            
            status_placeholder.empty() # 清除進度條
            return selected_ticker, HOT_STOCKS_MAP[selected_ticker], df
        except: continue
    
    status_placeholder.error("搜尋超時，將隨機載入一檔。")
    time.sleep(1)
    status_placeholder.empty()
    return selected_ticker, HOT_STOCKS_MAP.get(selected_ticker, "未知"), df

# [修復] 將準備下一關的邏輯拆分，不在此處加載數據，避免UI卡死
def prepare_next_round(full_reset=False):
    if full_reset:
        st.session_state.balance = 10000000.0
        st.session_state.round = 1
        st.session_state.trade_returns = []
        st.session_state.last_equity = 10000000.0
        st.session_state.nav_selection = "📊 操盤室"
    else:
        st.session_state.balance = st.session_state.last_equity
        st.session_state.round += 1
    
    # 關鍵：清空數據，觸發主流程的重新加載
    st.session_state.data = None 
    st.session_state.position = 0
    st.session_state.avg_cost = 0.0
    st.session_state.history = []
    st.session_state.trades_visual = []
    st.session_state.auto_play = False
    st.session_state.in_countdown = True

def execute_trade(action, price, qty, current_step_index):
    try:
        price = float(price); pos = st.session_state.position; avg = st.session_state.avg_cost
        fee = price * qty * 0.002
        if action == "buy":
            if pos < 0:
                cover_qty = min(abs(pos), qty); remaining_qty = qty - cover_qty
                principal_returned = avg * cover_qty; profit = (avg - price) * cover_qty
                trade_roi = (avg - price) / avg * 100
                st.session_state.trade_returns.append(trade_roi)
                st.session_state.balance += (principal_returned + profit - fee)
                st.session_state.position += cover_qty
                st.session_state.history.append(f"🔴 空單回補 {cover_qty}股 (損: {int(profit)}, {trade_roi:.2f}%)")
                if remaining_qty > 0:
                    cost_new = price * remaining_qty
                    if st.session_state.balance >= cost_new:
                        st.session_state.balance -= (cost_new + fee); st.session_state.position += remaining_qty
                        st.session_state.avg_cost = price
                        st.session_state.history.append(f"🔴 反手做多 {remaining_qty}股 @ {price:.2f}")
            else:
                cost = price * qty
                if st.session_state.balance >= cost:
                    st.session_state.balance -= (cost + fee)
                    total_cost = (avg * pos) + cost; new_pos_size = pos + qty
                    st.session_state.avg_cost = total_cost / new_pos_size; st.session_state.position += qty
                    st.session_state.history.append(f"🔴 買進 {qty}股 @ {price:.2f}")
                else: st.toast("❌ 資金不足", icon="💸")
        elif action == "sell":
            if pos > 0:
                sell_qty = min(pos, qty); remaining_qty = qty - sell_qty
                profit = (price - avg) * sell_qty; revenue = price * sell_qty
                trade_roi = (price - avg) / avg * 100
                st.session_state.trade_returns.append(trade_roi)
                st.session_state.balance += (revenue - fee); st.session_state.position -= sell_qty
                st.session_state.history.append(f"🟢 賣出 {sell_qty}股 (損: {int(profit)}, {trade_roi:.2f}%)")
                if remaining_qty > 0:
                    cost_new = price * remaining_qty
                    if st.session_state.balance >= cost_new:
                        st.session_state.balance -= (cost_new + fee); st.session_state.position -= remaining_qty
                        st.session_state.avg_cost = price
                        st.session_state.history.append(f"🟢 反手放空 {remaining_qty}股 @ {price:.2f}")
            else:
                cost = price * qty
                if st.session_state.balance >= cost:
                    st.session_state.balance -= (cost + fee)
                    total_cost = (avg * abs(pos)) + cost; new_pos_size = abs(pos) + qty
                    st.session_state.avg_cost = total_cost / new_pos_size; st.session_state.position -= qty
                    st.session_state.history.append(f"🟢 放空 {qty}股 @ {price:.2f}")
                else: st.toast(f"❌ 資金不足！", icon="💸")
        marker_type = 'buy' if action == 'buy' else 'sell'
        st.session_state.trades_visual.append({'index': current_step_index, 'price': price, 'type': marker_type})
    except Exception as e: pass

def save_score(player, ticker, name, assets, roi):
    try:
        trades = st.session_state.trade_returns
        avg_sniper = sum(trades) / len(trades) if trades else 0.0
        total_profit = assets - 10000000
        profit_score = (total_profit / 10000) 
        power_score = (avg_sniper * 40) + (roi * 30) + (profit_score * 0.3 * 30) 
        new = pd.DataFrame([{"日期": time.strftime("%Y-%m-%d %H:%M"), "玩家": player, "股名": "三關通關", "綜合戰力": round(power_score, 1), "狙擊率(%)": round(avg_sniper, 2), "總報酬(%)": round(roi, 2), "總獲利($)": int(total_profit)}])
        hdr = not os.path.exists(FILES["leaderboard"]); new.to_csv(FILES["leaderboard"], mode='a', header=hdr, index=False)
    except: pass

def save_feedback(name, text):
    try:
        timestamp = time.strftime('%Y-%m-%d %H:%M')
        if not os.path.exists(FILES["feedback"]):
             with open(FILES["feedback"], "w", encoding="utf-8") as f: f.write("Time,User,Message\n")
        clean_text = text.replace(",", "，").replace("\n", " ")
        with open(FILES["feedback"], "a", encoding="utf-8") as f: f.write(f"{timestamp},{name},{clean_text}\n")
    except: pass

# --- 6. 程式進入點 ---
log_traffic()

try: ADMIN_PASSWORD = st.secrets["admin_password"]
except: ADMIN_PASSWORD = "admin_password_not_set"

if st.session_state.is_admin:
    st.title("🔒 系統管理後台")
    if st.button("⬅️ 返回遊戲"): st.session_state.is_admin = False; st.rerun()
    admin_data = get_admin_data()
    k1, k2, k3 = st.columns(3)
    k1.metric("👁️ 總瀏覽", len(admin_data['traffic'])); k2.metric("💬 回饋數", len(admin_data['feedback']) if isinstance(admin_data['feedback'], list) else pd.read_csv(FILES["feedback"]).shape[0] if os.path.exists(FILES["feedback"]) else 0); k3.metric("🎮 遊戲場數", len(admin_data['leaderboard']))
    st.divider()
    if not admin_data['traffic'].empty:
        df_t = admin_data['traffic']; df_count = df_t.groupby(df_t['Time'].dt.date).size().reset_index(name='Visits')
        st.plotly_chart(px.line(df_count, x='Time', y='Visits', title='每日訪問'), use_container_width=True)
    c1, c2 = st.columns(2)
    with c1: 
        st.subheader("💬 意見回饋")
        if os.path.exists(FILES["feedback"]): st.dataframe(pd.read_csv(FILES["feedback"]), use_container_width=True)
    with c2: 
        st.subheader("🏆 英雄榜")
        if not admin_data['leaderboard'].empty: st.dataframe(admin_data['leaderboard'].sort_values(by="綜合戰力", ascending=False), use_container_width=True)

else:
    if not st.session_state.game_started:
        st.markdown("<h1 style='text-align: center;'>⚡ 交易挑戰賽，戰力積分版</h1>", unsafe_allow_html=True)
        st.markdown("""
        <div class='warning-text'>
        ⚠️ 純粹好玩，大家聖誕節快樂！<br>
        當沖賺得快，賠得也快，現實生活還是乖乖做波段吧。<br>
        不小心開發這程式到上頭，成就感滿滿，希望你們喜歡，我要去補眠了 😴<br>
        <br>
        歡迎脆追蹤按起來 <a href="https://www.threads.net/@wowwow31001" target="_blank">wowwow31001</a>!<br>
        <strong style='background-color: #ffffcc; color: #ff0000; padding: 2px 5px; border-radius: 4px;'>真正有料的是12/7日那個程式</strong><br>
        <br>
        如果畫面突然重啟，代表我正在修改程式，請見諒。
        </div>
        """, unsafe_allow_html=True)
        
        col_a, col_b, col_c = st.columns([1,2,1])
        with col_b:
            with st.form("login"):
                name = st.text_input("輸入你的綽號", "邊看盤邊大跳")
                show_hints = st.checkbox("🤖 啟用【AI 投顧提示】(K線圖顯示買賣訊號)")
                if st.form_submit_button("🔥 進入操盤室", use_container_width=True):
                    st.session_state.nickname = name
                    st.session_state.accumulate_mode = True
                    st.session_state.show_hints = show_hints
                    st.session_state.game_started = True
                    prepare_next_round(full_reset=True)
                    st.rerun()
        
        with st.sidebar:
            st.markdown("---")
            with st.expander("🔐 管理員登入"):
                pwd = st.text_input("密碼", type="password")
                if st.button("登入"):
                    if pwd == ADMIN_PASSWORD: st.session_state.is_admin = True; st.rerun()
                    else: st.error("錯誤")

    else:
        # [核心修復] 在主流程中檢測數據是否為空，如果是，則觸發加載
        # 這樣可以確保 UI 已經刷新，彈窗消失，然後才顯示載入動畫
        if st.session_state.data is None:
            with st.spinner('🎲 正在搜尋高波動、股價<200 的妖股...'):
                t, n, d = load_data()
                st.session_state.ticker = t; st.session_state.stock_name = n; st.session_state.data = d
                st.rerun() # 載入完成後再次刷新，顯示圖表

        df = st.session_state.data
        # 再次檢查確保 df 存在 (理論上上面的 if 會處理)
        if df is None:
             st.stop()

        if st.session_state.in_countdown:
            placeholder = st.empty()
            for i in range(3, 0, -1):
                placeholder.markdown(f"""<div class='reveal-overlay'></div><div class='countdown-box'>{i}</div>""", unsafe_allow_html=True)
                time.sleep(1)
            placeholder.empty()
            st.session_state.in_countdown = False
            st.session_state.auto_play = True
            st.rerun()

        if st.session_state.first_load:
            st.toast("👈 手機請點左上角「>」打開下單面板！", icon="💡")
            st.session_state.first_load = False

        curr_idx = st.session_state.step
        if curr_idx >= len(df): st.session_state.auto_play = False; curr_idx = len(df)-1
        curr_row = df.iloc[curr_idx]; curr_price = float(curr_row['Close'])
        
        masked_name = "❓❓❓❓"
        pos = st.session_state.position; avg = st.session_state.avg_cost
        unrealized = (curr_price - avg) * pos if pos > 0 else (avg - curr_price) * abs(pos) if pos < 0 else 0
        est_total = st.session_state.balance + (pos * curr_price if pos > 0 else (abs(pos)*avg + unrealized if pos < 0 else 0))
        roi = ((est_total - 10000000) / 10000000) * 100

        # 斷頭機制
        if est_total <= 0:
            st.session_state.auto_play = False
            real_name = st.session_state.stock_name
            real_ticker = st.session_state.ticker
            save_score(st.session_state.nickname, real_ticker, f"破產-{real_name}", 0, -100.0)
            
            st.markdown(f"""
            <div class='reveal-overlay'></div>
            <div class='margin-call-box' style='position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); z-index: 10000;'>
                💀 挑戰失敗！資金歸零<br>
                <div style='font-size: 18px; color: #555; margin-top: 10px;'>你在第 {st.session_state.round} 關陣亡了</div>
                <div style='font-size: 20px; color: #333; margin: 10px 0;'>真相：{real_name} ({real_ticker})</div>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("💸 重新挑戰", type="primary", use_container_width=True):
                prepare_next_round(full_reset=True)
                st.rerun()
            st.stop()

        with st.sidebar:
            st.markdown(f"#### 👤 {st.session_state.nickname}")
            st.info(f"🏆 目前關卡：Round {st.session_state.round} / 3")
            if st.session_state.show_hints: st.caption("🤖 AI 投顧提示 ON")
            
            pnl_color = "red" if unrealized >= 0 else "green"
            st.markdown(f"""
            <div class="asset-box">
                <div class="asset-label">總權益 / 報酬率</div>
                <div class="asset-value">{int(est_total/10000)}萬 ({roi:.2f}%)</div>
                <div class="asset-label" style="margin-top:5px;">未實現損益</div>
                <div class="asset-value" style="color: {pnl_color};">{int(unrealized)}</div>
            </div>
            """, unsafe_allow_html=True)

            if pos != 0: st.info(f"倉位: {'多單' if pos>0 else '空單'} {abs(pos)} 股 | 均价 {avg:.1f}")
            else: st.caption("目前無庫存")
            st.divider()

            c_price, c_qty = st.columns([1, 1.5])
            c_price.markdown(f"<div class='price-text'>{curr_price:.1f}</div>", unsafe_allow_html=True)
            qty = c_qty.number_input("股數", 1000, 50000, 1000, step=1000, label_visibility="collapsed")
            
            max_buy = int(st.session_state.balance // curr_price // 1000)
            if max_buy < 1: st.caption(f"⚠️ 資金不足買1張")
            else: st.caption(f"💰 可買: {max_buy} 張")

            b_col, s_col = st.columns(2)
            if b_col.button(f"買進", use_container_width=True): execute_trade("buy", curr_price, qty, curr_idx); st.rerun()
            if s_col.button(f"賣出", use_container_width=True): execute_trade("sell", curr_price, qty, curr_idx); st.rerun()

            st.divider()
            c_play, c_next, c_slow = st.columns([2, 1, 1])
            if st.session_state.auto_play:
                if c_play.button("⏸ 暫停", type="primary", use_container_width=True): st.session_state.auto_play = False; st.rerun()
            else:
                if c_play.button("▶ 播放", use_container_width=True): st.session_state.auto_play = True; st.rerun()
            if c_next.button("⏭", use_container_width=True):
                if st.session_state.step < len(df)-1: st.session_state.step += 1; st.rerun()
            if c_slow.button("🐢", help="減速", use_container_width=True): st.toast("無法減速！", icon="😈")

            st.divider()
            
            btn_text = "🏁 結算本局 (下一關)" if st.session_state.round < 3 else "🏆 最終結算 (上榜)"
            if st.button(btn_text, use_container_width=True):
                real_name = st.session_state.stock_name
                real_ticker = st.session_state.ticker
                st.session_state.last_equity = est_total
                st.balloons()
                
                if st.session_state.round >= 3:
                    save_score(st.session_state.nickname, "ALL_CLEAR", "三關制霸", est_total, roi)
                    msg_main = f"🎉 恭喜通關！最終資產：${int(est_total):,}"
                    st.session_state.nav_selection = "🏆 英雄榜 (戰力積分)"
                else:
                    msg_main = f"💰 Round {st.session_state.round} 完成！資產 ${int(est_total):,} 帶入下一關"

                st.markdown(f"""
                <div class='reveal-overlay'></div>
                <div class='reveal-box'>
                    <div class='reveal-title'>🎉 結算完成</div>
                    <div class='reveal-stock'>{real_name} ({real_ticker})</div>
                    <div class='reveal-stat'>{msg_main}</div>
                    <div style='margin-top: 15px; font-size: 14px; color: #888;'>請等待 3 秒...</div>
                </div>
                """, unsafe_allow_html=True)
                
                time.sleep(3)
                if st.session_state.round >= 3:
                    pass 
                else:
                    # 這裡只清空狀態，不下載數據，避免UI卡死
                    prepare_next_round(full_reset=False)
                st.rerun()

            with st.popover("💬 回饋"):
                with st.form("fb"):
                    t = st.text_area("內容"); submit = st.form_submit_button("送出")
                    if submit: save_feedback(st.session_state.nickname, t); st.toast("感謝")
            
            if st.session_state.show_hints:
                ma5 = curr_row['MA5']; ma22 = curr_row['MA22']; macd = curr_row['MACD']
                is_bull = curr_row['Signal_Bull']; is_bear = curr_row['Signal_Bear']; slope = curr_row['MA22_Slope']
                if is_bull: hint = "<span class='signal-bull'>🚀 攻擊訊號</span>：趨勢向上 + 動能增強！"
                elif is_bear: hint = "<span class='signal-bear'>📉 棄守訊號</span>：趨勢轉弱 + 動能翻空。"
                elif slope > 0: hint = "<span class='signal-wait'>🧘‍♀️ 多頭回檔</span>：月線向上，短線整理。"
                else: hint = "<span class='signal-wait'>👀 震盪觀望</span>：趨勢不明，耐心等待。"
                st.markdown(f"<div class='tip-box'>🤖 AI 觀點：<br>{hint}</div>", unsafe_allow_html=True)
        
        st.markdown("---")
        view_mode = st.radio("功能切換", ["📊 操盤室", "🏆 英雄榜 (戰力積分)", "📜 版本日誌"], horizontal=True, label_visibility="collapsed", key="nav_selection")

        if view_mode == "📊 操盤室":
            display_start = max(0, curr_idx - 100)
            display_df = df.iloc[display_start : curr_idx+1]
            chart_title = f"{masked_name} - {curr_price}"
            
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.65, 0.15, 0.2])
            fig.add_trace(go.Candlestick(x=display_df['Bar_Index'], open=display_df['Open'], high=display_df['High'], low=display_df['Low'], close=display_df['Close'], name="K線", increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
            
            if st.session_state.show_hints:
                bull_signals = display_df[display_df['Signal_Bull']]
                if not bull_signals.empty: fig.add_trace(go.Scatter(x=bull_signals['Bar_Index'], y=bull_signals['Low']*0.995, mode='markers', name='轉強', marker=dict(symbol='triangle-up', size=10, color='#d90000')), row=1, col=1)
                bear_signals = display_df[display_df['Signal_Bear']]
                if not bear_signals.empty: fig.add_trace(go.Scatter(x=bear_signals['Bar_Index'], y=bear_signals['High']*1.005, mode='markers', name='轉弱', marker=dict(symbol='triangle-down', size=10, color='#008000')), row=1, col=1)

            colors = {'MA5': '#FFD700', 'MA22': '#9370DB', 'MA60': '#2E8B57', 'MA240': '#A9A9A9'}
            widths = {'MA5': 1, 'MA22': 1, 'MA60': 1.5, 'MA240': 2}
            for ma in ['MA5', 'MA22', 'MA60', 'MA240']:
                fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df[ma], line=dict(color=colors[ma], width=widths[ma]), name=ma), row=1, col=1)
            
            visible = [t for t in st.session_state.trades_visual if display_start <= t['index'] <= curr_idx]
            bx = [t['index'] for t in visible if t['type']=='buy']; by = [t['price']*0.99 for t in visible if t['type']=='buy']
            sx = [t['index'] for t in visible if t['type']=='sell']; sy = [t['price']*1.01 for t in visible if t['type']=='sell']
            if bx: fig.add_trace(go.Scatter(x=bx, y=by, mode='markers', name='買', marker=dict(symbol='triangle-up', size=12, color='red')), row=1, col=1)
            if sx: fig.add_trace(go.Scatter(x=sx, y=sy, mode='markers', name='賣', marker=dict(symbol='triangle-down', size=12, color='green')), row=1, col=1)
            
            vol_colors = ['#ef5350' if r['Open'] < r['Close'] else '#26a69a' for i, r in display_df.iterrows()]
            fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['Volume'], marker_color=vol_colors, name="量"), row=2, col=1)
            
            hist_c = ['#ef5350' if v > 0 else '#26a69a' for v in display_df['MACD_Hist']]
            fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['MACD_Hist'], marker_color=hist_c, name="MACD"), row=3, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MACD'], line=dict(color='#ffc107', width=1)), row=3, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['Signal'], line=dict(color='#2196f3', width=1)), row=3, col=1)
            
            fig.update_layout(height=450, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, 
                            title=dict(text=chart_title, x=0.05, y=0.98, font=dict(color="white")),
                            xaxis_rangeslider_visible=False, dragmode=False,
                            paper_bgcolor='#0e1117', plot_bgcolor='#0e1117', font=dict(color='white'))
            
            fig.update_xaxes(showticklabels=False, row=1, col=1, fixedrange=True, gridcolor='#333')
            fig.update_yaxes(fixedrange=True, row=1, col=1, gridcolor='#333')
            fig.update_xaxes(showticklabels=False, row=2, col=1, fixedrange=True, gridcolor='#333')
            fig.update_yaxes(fixedrange=True, row=2, col=1, gridcolor='#333')
            fig.update_xaxes(showticklabels=False, row=3, col=1, fixedrange=True, gridcolor='#333')
            fig.update_yaxes(fixedrange=True, row=3, col=1, gridcolor='#333')
            
            st.plotly_chart(fig, use_container_width=True, config={'staticPlot': True}, theme=None)
            
            with st.expander("📝 交易紀錄 (倒序)"):
                for log in reversed(st.session_state.history[-10:]): st.caption(log)

        elif view_mode == "🏆 英雄榜 (戰力積分)":
            st.markdown("### 🏆 華爾街英雄榜")
            
            if st.button("🔥 再戰一場 (Restart)", type="primary", use_container_width=True):
                prepare_next_round(full_reset=True)
                st.rerun()
                
            st.markdown("""
            > **⚔️ 戰力公式**：
            > * **狙擊率 (40%)**：平均單筆交易報酬率，考驗你的精準度。
            > * **總報酬 (30%)**：本局總資產報酬率，考驗你的穩定性。
            > * **獲利力 (30%)**：絕對獲利金額，考驗你的部位管理。
            """)
            if os.path.exists(FILES["leaderboard"]):
                try: st.dataframe(pd.read_csv(FILES["leaderboard"]).sort_values(by="綜合戰力", ascending=False), use_container_width=True)
                except: st.write("無紀錄")
            else: st.info("尚無紀錄")

        elif view_mode == "📜 版本日誌":
            st.markdown("### 📜 版本日誌")
            st.markdown("""
            * **v4.23**: [BugFix] 修復結算視窗卡死問題，優化搜尋過程顯示。
            * **v4.22**: [UX] 通關後自動跳轉英雄榜。
            * **v4.21**: [GamePlay] 3關制生存戰。
            """)
        
        if st.session_state.auto_play:
            time.sleep(0.5); st.session_state.step += 1; st.rerun()
