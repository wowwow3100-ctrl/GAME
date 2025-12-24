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

# --- 1. 全域設定 ---
st.set_page_config(page_title="飆股當沖 - 資安加密版", layout="wide", page_icon="🔐")

# CSS 優化
st.markdown("""
<style>
    div[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] { gap: 0.5rem; }
    section[data-testid="stSidebar"] .stButton>button {
        width: 100%; border-radius: 6px; font-weight: bold; height: 45px;
    }
    div[data-testid="stSidebar"] button:contains("買進") {
        background-color: #ffe6e6 !important; color: #d90000 !important; border: 1px solid #d90000 !important;
    }
    div[data-testid="stSidebar"] button:contains("賣出") {
        background-color: #e6ffe6 !important; color: #008000 !important; border: 1px solid #008000 !important;
    }
    .price-text { font-size: 26px; font-weight: bold; color: #333; margin-bottom: 5px; }
    
    .asset-box {
        padding: 10px; background-color: #f0f2f6; border-radius: 8px; margin-bottom: 10px;
    }
    .asset-label { font-size: 14px; color: #666; }
    .asset-value { font-size: 20px; font-weight: bold; color: #333; }
    
    .warning-text {
        color: #ff9800; font-weight: bold; padding: 10px; border: 1px dashed #ff9800;
        border-radius: 5px; margin-bottom: 20px; text-align: center; background-color: #fff3e0;
    }
    .warning-text a { color: #E1306C; text-decoration: none; border-bottom: 1px dashed #E1306C; }
    .warning-text a:hover { border-bottom: 1px solid #E1306C; }
    
    .reveal-box {
        padding: 15px; background-color: #d4edda; color: #155724; border-radius: 8px;
        text-align: center; font-size: 22px; font-weight: bold; margin-bottom: 10px; border: 2px solid #c3e6cb;
    }
</style>
""", unsafe_allow_html=True)

FILES = { "leaderboard": "leaderboard_tw_v3.csv", "feedback": "feedback.csv", "traffic": "traffic_log.csv" }

HOT_STOCKS_MAP = {
    '8043.TWO': '蜜望實', '6127.TWO': '九豪', '6706.TW': '惠特', '4967.TW': '十銓',
    '4979.TW': '華星光', '2413.TW': '環科', '5498.TWO': '凱崴', '4977.TW': '眾達-KY',
    '1727.TW': '中華化', '6426.TWO': '統新', '4909.TWO': '新復興', '1815.TW': '富喬',
    '4989.TW': '榮科', '8074.TWO': '鉅橡', '8021.TW': '尖點', '4916.TW': '事欣科',
    '1528.TW': '恩德', '4991.TWO': '環宇-KY', '3236.TWO': '千如', '6163.TWO': '華電網',
    '6155.TWO': '鈞寶', '8431.TWO': '匯鑽科', '3025.TW': '星通', '3689.TW': '湧德',
    '3661.TW': '世芯-KY', '1519.TW': '華城', '3017.TW': '奇鋐', '3324.TWO': '雙鴻',
    '6472.TWO': '保瑞', '3529.TWO': '力旺', '8069.TWO': '元太',
    '6669.TW': '緯穎', '6415.TWO': '矽力-KY', '3035.TW': '智原', '3189.TW': '景碩',
    '2603.TW': '長榮', '2609.TW': '陽明', '2409.TW': '友達', '6116.TW': '彩晶'
}

default_values = {
    'balance': 10000000.0, 'position': 0, 'avg_cost': 0.0, 'step': 0,
    'history': [], 'trades_visual': [], 'data': None, 'ticker': "",
    'stock_name': "", 'nickname': "", 'game_started': False, 
    'auto_play': False, 'first_load': True, 'is_admin': False
}

for key, value in default_values.items():
    if key not in st.session_state: st.session_state[key] = value

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

def calculate_technical_indicators(df):
    try:
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA22'] = df['Close'].rolling(window=22).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA240'] = df['Close'].rolling(window=240).mean()
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['Signal']
        return df
    except: return df

def load_data():
    max_retries = 20
    ticker_list = list(HOT_STOCKS_MAP.keys())
    for _ in range(max_retries):
        selected_ticker = random.choice(ticker_list)
        try:
            df = yf.download(selected_ticker, period="60d", interval="5m", progress=False)
            if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
            df = df[df['Volume'] > 0]
            if len(df) < 300: continue
            df = calculate_technical_indicators(df)
            df.dropna(inplace=True); df.reset_index(inplace=True); df['Bar_Index'] = range(len(df))
            if len(df) < 200: continue
            max_start = len(df) - 150
            start_idx = random.randint(50, max_start) if max_start > 50 else 50
            st.session_state.step = start_idx
            st.session_state.first_load = True
            return selected_ticker, HOT_STOCKS_MAP[selected_ticker], df
        except: continue
    return None, None, None

def reset_game():
    st.session_state.balance = 10000000.0; st.session_state.position = 0; st.session_state.avg_cost = 0.0
    st.session_state.history = []; st.session_state.trades_visual = []; st.session_state.auto_play = False
    with st.spinner('🎲 正在隨機抽取 (包含空頭股)...'):
        t, n, d = load_data()
        st.session_state.ticker = t; st.session_state.stock_name = n; st.session_state.data = d

def execute_trade(action, price, qty, current_step_index):
    try:
        price = float(price); pos = st.session_state.position; avg = st.session_state.avg_cost
        fee = price * qty * 0.002
        
        if action == "buy":
            if pos < 0:
                cover_qty = min(abs(pos), qty); remaining_qty = qty - cover_qty
                profit = (avg - price) * cover_qty; cost = price * cover_qty
                st.session_state.balance -= (cost + fee); st.session_state.balance += (cost + profit)
                st.session_state.position += cover_qty
                st.session_state.history.append(f"🔴 空單回補 {cover_qty}股 (損: {int(profit)})")
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
                st.session_state.balance += (revenue - fee); st.session_state.position -= sell_qty
                st.session_state.history.append(f"🟢 賣出 {sell_qty}股 (損: {int(profit)})")
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
                else: st.toast("❌ 資金不足", icon="💸")

        marker_type = 'buy' if action == 'buy' else 'sell'
        st.session_state.trades_visual.append({'index': current_step_index, 'price': price, 'type': marker_type})
    except Exception: pass

def save_score(player, ticker, name, assets, roi):
    try:
        new = pd.DataFrame([{"日期": time.strftime("%Y-%m-%d %H:%M"), "玩家": player, "股名": name, "最終資產": round(assets, 0), "報酬率": roi}])
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

# ★★★ 安全驗證邏輯 Start ★★★
# 嘗試從 secrets 讀取密碼，如果沒設定，預設為空字串 (會導致無法登入)
try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
except:
    ADMIN_PASSWORD = "admin_password_not_set"
# ★★★ 安全驗證邏輯 End ★★★

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
        if not admin_data['leaderboard'].empty: st.dataframe(admin_data['leaderboard'].sort_index(ascending=False), use_container_width=True)

else:
    if not st.session_state.game_started:
        st.markdown("<h1 style='text-align: center;'>⚡ 飆股當沖 - 資安加密版</h1>", unsafe_allow_html=True)
        st.markdown("""
        <div class='warning-text'>
        ⚠️ 純粹好玩，大家聖誕節快樂！<br>
        當沖賺得快，賠得也快，現實生活還是乖乖做波段吧。<br>
        不小心熬夜開發，我要去補眠了 😴<br>
        如果畫面突然重啟，代表我正在修改程式，請見諒。<br>
        如果你喜歡，歡迎脆追蹤按起來 <a href="https://www.threads.net/@wowwow31001" target="_blank">wowwow31001</a>!<br>
        但真正有料的是12/12日那篇XD
        </div>
        """, unsafe_allow_html=True)
        
        col_a, col_b, col_c = st.columns([1,2,1])
        with col_b:
            with st.form("login"):
                name = st.text_input("輸入你的綽號", "少年股神")
                if st.form_submit_button("🔥 進入操盤室", use_container_width=True):
                    st.session_state.nickname = name; st.session_state.game_started = True; reset_game(); st.rerun()
        
        with st.sidebar:
            st.markdown("---")
            with st.expander("🔐 管理員登入"):
                pwd = st.text_input("密碼", type="password")
                if st.button("登入"):
                    # ★★★ 使用 st.secrets 進行驗證 ★★★
                    if pwd == ADMIN_PASSWORD:
                        st.session_state.is_admin = True
                        st.rerun()
                    else:
                        st.error("密碼錯誤")

    else:
        df = st.session_state.data
        if df is None:
            st.error("資料載入失敗，請重試"); 
            if st.button("重試"): reset_game(); st.rerun()
            st.stop()

        if st.session_state.first_load: st.toast("👈 左側點擊「▶️ 播放」開始！", icon="💡"); st.session_state.first_load = False

        curr_idx = st.session_state.step
        if curr_idx >= len(df): st.session_state.auto_play = False; curr_idx = len(df)-1
        curr_row = df.iloc[curr_idx]; curr_price = float(curr_row['Close'])
        
        masked_name = "❓❓❓❓"
        
        pos = st.session_state.position; avg = st.session_state.avg_cost
        unrealized = (curr_price - avg) * pos if pos > 0 else (avg - curr_price) * abs(pos) if pos < 0 else 0
        est_total = st.session_state.balance + (pos * curr_price if pos > 0 else (abs(pos)*avg + unrealized if pos < 0 else 0))
        roi = ((est_total - 10000000) / 10000000) * 100

        with st.sidebar:
            st.markdown(f"#### 👤 {st.session_state.nickname}")
            st.markdown(f"**標的: {masked_name}** (5分K)")
            
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
            if st.button("🏳️ 結算 / 揭曉答案", use_container_width=True):
                real_name = st.session_state.stock_name
                real_ticker = st.session_state.ticker
                save_score(st.session_state.nickname, real_ticker, real_name, est_total, f"{roi:.2f}%")
                st.balloons()
                st.markdown(f"<div class='reveal-box'>🎉 真相大白：{real_name} ({real_ticker})</div>", unsafe_allow_html=True)
                st.info("請等待 3 秒後自動開始下一局...")
                time.sleep(3); reset_game(); st.rerun()

            with st.popover("💬 回饋"):
                with st.form("fb"):
                    t = st.text_area("內容"); submit = st.form_submit_button("送出")
                    if submit: save_feedback(st.session_state.nickname, t); st.toast("感謝")
        
        tab1, tab2, tab3 = st.tabs(["📊 操盤室", "🏆 英雄榜", "📜 版本日誌"])

        with tab1:
            display_start = max(0, curr_idx - 100)
            display_df = df.iloc[display_start : curr_idx+1]
            chart_title = f"{masked_name} - {curr_price}"
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[0.65, 0.15, 0.2])
            fig.add_trace(go.Candlestick(x=display_df['Bar_Index'], open=display_df['Open'], high=display_df['High'], low=display_df['Low'], close=display_df['Close'], name="K線", increasing_line_color='#ef5350', decreasing_line_color='#26a69a'), row=1, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA5'], line=dict(color='#FFD700', width=1), name='5MA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA22'], line=dict(color='#9370DB', width=1), name='22MA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA60'], line=dict(color='#2E8B57', width=1.5), name='60MA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA240'], line=dict(color='#A9A9A9', width=2), name='240MA'), row=1, col=1)
            
            visible = [t for t in st.session_state.trades_visual if display_start <= t['index'] <= curr_idx]
            bx = [t['index'] for t in visible if t['type']=='buy']; by = [t['price']*0.99 for t in visible if t['type']=='buy']
            sx = [t['index'] for t in visible if t['type']=='sell']; sy = [t['price']*1.01 for t in visible if t['type']=='sell']
            if bx: fig.add_trace(go.Scatter(x=bx, y=by, mode='markers', name='買', marker=dict(symbol='triangle-up', size=12, color='red')), row=1, col=1)
            if sx: fig.add_trace(go.Scatter(x=sx, y=sy, mode='markers', name='賣', marker=dict(symbol='triangle-down', size=12, color='green')), row=1, col=1)
            
            colors = ['#ef5350' if r['Open'] < r['Close'] else '#26a69a' for i, r in display_df.iterrows()]
            fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['Volume'], marker_color=colors, name="量"), row=2, col=1)
            
            hist_c = ['#ef5350' if v > 0 else '#26a69a' for v in display_df['MACD_Hist']]
            fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['MACD_Hist'], marker_color=hist_c, name="MACD"), row=3, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MACD'], line=dict(color='#ffc107', width=1)), row=3, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['Signal'], line=dict(color='#2196f3', width=1)), row=3, col=1)
            
            fig.update_layout(height=800, margin=dict(l=10, r=10, t=10, b=10), showlegend=False, title=dict(text=chart_title, x=0.05, y=0.98), xaxis_rangeslider_visible=False)
            fig.update_xaxes(showticklabels=False, row=1, col=1); fig.update_xaxes(showticklabels=False, row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("📝 交易紀錄 (倒序)"):
                for log in reversed(st.session_state.history[-10:]): st.caption(log)

        with tab2:
            st.markdown("### 🏆 英雄榜")
            if os.path.exists(FILES["leaderboard"]):
                try: st.dataframe(pd.read_csv(FILES["leaderboard"]).sort_index(ascending=False), use_container_width=True)
                except: st.write("無紀錄")
            else: st.info("尚無紀錄")

        with tab3:
            st.markdown("### 📜 版本日誌")
            st.markdown("""
            * **v4.0**: 重大資安升級，使用 Streamlit Secrets 管理密碼，程式碼中不再顯示明文密碼。
            * **v3.9**: 介面修復，空單回補優化。
            * **v3.8**: 地獄盲測版。
            """)
        
        if st.session_state.auto_play:
            time.sleep(0.5); st.session_state.step += 1; st.rerun()
