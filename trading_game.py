import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import random
import time
import os

# --- 1. 全域設定 ---

st.set_page_config(page_title="飆股當沖 - 聖誕特別版", layout="wide", page_icon="🎄")

# CSS 優化：按鈕與介面
st.markdown("""
<style>
    section[data-testid="stSidebar"] .stButton>button {
        width: 100%;
        border-radius: 8px;
        font-weight: bold;
        height: 50px;
    }
    /* 買賣按鈕顏色 */
    section[data-testid="stSidebar"] button:contains("買進") {
        background-color: #ffe6e6;
        color: #d90000;
        border: 2px solid #d90000;
    }
    section[data-testid="stSidebar"] button:contains("賣出") {
        background-color: #e6ffe6;
        color: #008000;
        border: 2px solid #008000;
    }
    /* 播放按鈕特別色 */
    section[data-testid="stSidebar"] button:contains("播放") {
        background-color: #e3f2fd;
        color: #1565c0;
        border: 2px solid #1565c0;
    }
    [data-testid="stMetricValue"] { font-size: 20px; }
    
    /* 警語樣式 */
    .warning-text {
        color: #ff9800;
        font-weight: bold;
        padding: 10px;
        border: 1px dashed #ff9800;
        border-radius: 5px;
        margin-bottom: 20px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

FILES = {"leaderboard": "leaderboard_tw_v3.csv", "feedback": "feedback.csv"}

# --- 2. 飆股名單 (IP/重電/散熱/光通訊) ---
HOT_STOCKS_MAP = {
    '3661.TW': '世芯-KY', '3035.TW': '智原', '3443.TW': '創意',
    '1519.TW': '華城', '1513.TW': '中興電', '1503.TW': '士電',
    '3017.TW': '奇鋐', '3324.TWO': '雙鴻', '8996.TWO': '高力',
    '8069.TWO': '元太', '3529.TWO': '力旺', '6531.TW': '愛普',
    '1605.TW': '華新', '4979.TW': '華星光', '3217.TWO': '優群',
    '6472.TWO': '保瑞', '4763.TWO': '材料-KY', '6274.TWO': '台燿',
    '2383.TW': '台光電', '3583.TW': '辛耘', '3131.TW': '弘塑',
    '2609.TW': '陽明', '2615.TW': '萬海', '3037.TW': '欣興',
    '2368.TW': '金像電', '9958.TW': '世紀鋼'
}

# --- 3. 初始化 Session State ---
default_values = {
    'balance': 10000000.0, # 升級：1000萬本金
    'position': 0,
    'avg_cost': 0.0,
    'step': 0,
    'history': [],
    'trades_visual': [],
    'data': None,
    'ticker': "",
    'stock_name': "",
    'nickname': "",
    'game_started': False,
    'auto_play': False,
    'first_load': True # 用於顯示引導提示
}

for key, value in default_values.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 4. 核心邏輯 ---

def calculate_technical_indicators(df):
    try:
        df['MA5'] = df['Close'].rolling(window=5).mean()
        df['MA22'] = df['Close'].rolling(window=22).mean()
        df['MA60'] = df['Close'].rolling(window=60).mean()
        df['MA240'] = df['Close'].rolling(window=240).mean()
        
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
    except Exception as e:
        return df # 若計算失敗回傳原df，後續檢查會濾掉

def load_data():
    max_retries = 15
    ticker_list = list(HOT_STOCKS_MAP.keys())
    
    for _ in range(max_retries):
        selected_ticker = random.choice(ticker_list)
        try:
            df = yf.download(selected_ticker, period="1mo", interval="5m", progress=False)
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            
            # 資料清理：移除成交量為0的時段 (盤後或暫停交易)
            df = df[df['Volume'] > 0]
            
            # 檢查資料長度
            if len(df) < 300: continue

            df = calculate_technical_indicators(df)
            df.dropna(inplace=True) # 移除均線計算造成的 NaN
            df.reset_index(inplace=True)
            df['Bar_Index'] = range(len(df))
            
            # 確保有足夠K棒
            if len(df) < 200: continue
            
            # 隨機切入點
            max_start = len(df) - 150
            start_idx = random.randint(50, max_start) if max_start > 50 else 50
            
            st.session_state.step = start_idx
            st.session_state.first_load = True # 重置引導標記
            return selected_ticker, HOT_STOCKS_MAP[selected_ticker], df
            
        except Exception:
            continue
            
    return None, None, None

def reset_game():
    st.session_state.balance = 10000000.0
    st.session_state.position = 0
    st.session_state.avg_cost = 0.0
    st.session_state.history = []
    st.session_state.trades_visual = []
    st.session_state.auto_play = False
    
    with st.spinner('🎄 聖誕老人正在幫你挑禮物 (搜尋飆股中)...'):
        t, n, d = load_data()
        st.session_state.ticker = t
        st.session_state.stock_name = n
        st.session_state.data = d

def execute_trade(action, price, qty, current_step_index):
    try:
        price = float(price)
        pos = st.session_state.position
        avg = st.session_state.avg_cost
        direction = 1 if action == "buy" else -1
        
        fee_rate = 0.002
        fee = price * qty * fee_rate
        trade_qty = qty * direction 

        # 資金檢查
        if action == "buy" and st.session_state.balance < (price * qty):
            st.toast("❌ 錢不夠啦！(雖然已經給你一千萬了...)", icon="💸")
            return
        
        # 加碼邏輯
        if (pos >= 0 and action == "buy") or (pos <= 0 and action == "sell"):
            cost = price * qty
            st.session_state.balance -= (cost + fee)
            total_cost = (avg * abs(pos)) + cost
            new_pos_size = abs(pos) + qty
            st.session_state.avg_cost = total_cost / new_pos_size
            st.session_state.position += trade_qty
            tag = "🔴 加碼做多" if action == "buy" else "🟢 加碼放空"
            st.session_state.history.append(f"{tag} {qty}股 @ {price:.2f}")

        # 平倉/反手邏輯
        else:
            cover_qty = min(abs(pos), qty)
            remaining_qty = qty - cover_qty
            
            # 平倉
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
            st.session_state.history.append(f"{tag_close} {cover_qty}股 (損益: {profit:.0f})")

            # 反手
            if remaining_qty > 0:
                cost = price * remaining_qty
                if st.session_state.balance >= cost:
                    st.session_state.balance -= (cost + fee)
                    st.session_state.position += (remaining_qty * direction)
                    st.session_state.avg_cost = price
                    tag_new = "🔴 反手做多" if action == "buy" else "🟢 反手放空"
                    st.session_state.history.append(f"{tag_new} {remaining_qty}股 @ {price:.2f}")
                else:
                    st.toast("⚠️ 餘額不足建立反手部位", icon="🛑")

        marker_type = 'buy' if action == 'buy' else 'sell'
        st.session_state.trades_visual.append({'index': current_step_index, 'price': price, 'type': marker_type})
        
    except Exception as e:
        st.error(f"交易執行發生錯誤: {e}")

def save_score(player, ticker, name, assets, roi):
    try:
        new_entry = pd.DataFrame([{
            "日期": time.strftime("%Y-%m-%d %H:%M"), "玩家": player,
            "股名": name, "最終資產": round(assets, 0), "報酬率": f"{roi:.2f}%"
        }])
        header = not os.path.exists(FILES["leaderboard"])
        new_entry.to_csv(FILES["leaderboard"], mode='a', header=header, index=False)
    except:
        st.toast("無法寫入排行榜，請檢查檔案權限", icon="⚠️")

def save_feedback(name, text):
    try:
        with open(FILES["feedback"], "a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d')}] {name}: {text}\n")
    except: pass

# --- 5. 介面呈現 (Try-Except 全局防護) ---

try:
    if not st.session_state.game_started:
        st.markdown("<h1 style='text-align: center;'>🎄 飆股當沖 - 聖誕熬夜版 💤</h1>", unsafe_allow_html=True)
        
        # 警語區塊
        st.markdown("""
        <div class='warning-text'>
        ⚠️ 純粹好玩，大家聖誕節快樂！<br>
        當沖賺得快，賠得也快，現實生活還是乖乖做波段吧。<br>
        不小心熬夜開發，我要去補眠了 😴<br>
        如果畫面突然重啟，代表我正在修改程式，請見諒。<br>
        如果你喜歡，歡迎脆追蹤按起來 wowwow31001!<br>
        但真正有料的是12/12日那篇XD
        </div>
        """, unsafe_allow_html=True)
        
        with st.sidebar:
            st.header("🎅 登入")
            name = st.text_input("你的綽號", "邊看盤邊大跳")
            if st.button("🎁 開始挑戰", use_container_width=True):
                st.session_state.nickname = name
                st.session_state.game_started = True
                reset_game()
                st.rerun()

    else:
        # 檢查資料是否載入成功
        df = st.session_state.data
        if df is None:
            st.error("😭 抱歉，資料讀取失敗 (可能是API連線問題)，請按側邊欄的「重開」再試一次。")
            if st.sidebar.button("🔄 重開一局"): reset_game(); st.rerun()
            st.stop()

        # 引導提示 (只在剛載入時顯示一次)
        if st.session_state.first_load:
            st.toast("👈 遊戲開始！請先點擊左側的「▶️ 播放」讓盤勢動起來！", icon="💡")
            st.session_state.first_load = False

        # 取得當前數據
        curr_idx = st.session_state.step
        # 防呆：防止索引超出範圍
        if curr_idx >= len(df):
            st.session_state.auto_play = False
            curr_idx = len(df) - 1
        
        curr_row = df.iloc[curr_idx]
        curr_price = float(curr_row['Close'])

        # 名稱馬賽克
        full_name = st.session_state.stock_name
        masked_name = f"{full_name[0]}ＯＯ" if len(full_name) > 1 else full_name

        # 資產計算
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

        est_total_assets = st.session_state.balance
        if pos > 0: est_total_assets += (pos * curr_price)
        elif pos < 0: est_total_assets += (abs(pos) * avg) + unrealized
        
        roi = ((est_total_assets - 10000000) / 10000000) * 100

        # --- 左側控制板 ---
        with st.sidebar:
            st.header(f"👤 {st.session_state.nickname}")
            
            with st.expander("💼 資產損益 (千萬本金)", expanded=True):
                st.metric("💰 總權益", f"NT$ {int(est_total_assets):,}", f"{roi:.2f}%")
                st.metric("💵 現金", f"NT$ {int(st.session_state.balance):,}")
                st.divider()
                st.info(pos_label)
                if pos != 0:
                    st.metric("均價", f"{avg:.2f}")
                    st.metric("未實現", f"{int(unrealized):,}", delta_color="normal")

            st.markdown("### ⚡ 下單 (單位: 股)")
            st.caption(f"目前標的: {masked_name} (波動大請小心)")
            st.write(f"現價: **{curr_price:.2f}**")
            qty = st.number_input("股數 (1張=1000)", 1000, 100000, 1000, step=1000)
            
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

            st.markdown("### ⏩ 盤勢控制")
            # 這裡加個提示，如果還沒播放
            if not st.session_state.auto_play and st.session_state.step < len(df)-1:
                st.caption("👇 點擊播放開始看盤")
            
            if st.session_state.auto_play:
                if st.button("⏸️ 暫停", type="primary", use_container_width=True):
                    st.session_state.auto_play = False
                    st.rerun()
            else:
                col_p, col_n = st.columns(2)
                if col_p.button("▶️ 播放", use_container_width=True):
                    st.session_state.auto_play = True
                    st.rerun()
                if col_n.button("⏭️ 下一根", use_container_width=True):
                    if st.session_state.step < len(df) - 1:
                        st.session_state.step += 1
                        st.rerun()
            
            # ★★★ 新增：放慢速度按鈕 (惡搞功能) ★★★
            if st.button("🐢 放慢速度", use_container_width=True):
                st.toast("現實中可是沒辦法減速的喔！請跟上節奏！", icon="😈")

            st.divider()
            if st.button("🏁 結算 / 換一檔", use_container_width=True):
                save_score(st.session_state.nickname, st.session_state.ticker, st.session_state.stock_name, est_total_assets, roi)
                st.balloons() # 結算放氣球
                st.success("紀錄已保存！")
                time.sleep(1)
                reset_game()
                st.rerun()
                
            with st.popover("💬 意見回饋"):
                with st.form("fb"):
                    txt = st.text_area("建議/Bug回報", height=100)
                    if st.form_submit_button("送出"): 
                        save_feedback(st.session_state.nickname, txt)
                        st.toast("收到回饋！我去修bug了...", icon="👨‍💻")

        # --- 主畫面 ---
        tab_g, tab_r, tab_v = st.tabs(["📊 飆股操盤室(點擊左側撥放開始遊戲)", "🏆 英雄榜", "📜 版本日誌"])

        with tab_g:
            # 確保顯示範圍不會報錯
            display_start = max(0, curr_idx - 100)
            display_df = df.iloc[display_start : curr_idx+1]
            
            fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, 
                              row_heights=[0.6, 0.2, 0.2], specs=[[{}],[{}],[{}]])
            
            # K線
            fig.add_trace(go.Candlestick(
                x=display_df['Bar_Index'], open=display_df['Open'], high=display_df['High'],
                low=display_df['Low'], close=display_df['Close'], name="K線",
                increasing_line_color='#ef5350', decreasing_line_color='#26a69a'
            ), row=1, col=1)
            
            # 均線
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA5'], line=dict(color='#FFD700', width=1), name='5MA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA22'], line=dict(color='#9370DB', width=1.5), name='22MA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA60'], line=dict(color='#2E8B57', width=1.5), name='60MA'), row=1, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MA240'], line=dict(color='#A9A9A9', width=2), name='240MA'), row=1, col=1)

            # 買賣點
            visible = [t for t in st.session_state.trades_visual if display_start <= t['index'] <= curr_idx]
            bx = [t['index'] for t in visible if t['type']=='buy']
            by = [t['price']*0.99 for t in visible if t['type']=='buy']
            sx = [t['index'] for t in visible if t['type']=='sell']
            sy = [t['price']*1.01 for t in visible if t['type']=='sell']
            
            if bx: fig.add_trace(go.Scatter(x=bx, y=by, mode='markers', name='買', marker=dict(symbol='triangle-up', size=12, color='red')), row=1, col=1)
            if sx: fig.add_trace(go.Scatter(x=sx, y=sy, mode='markers', name='賣', marker=dict(symbol='triangle-down', size=12, color='green')), row=1, col=1)

            # 成交量
            colors = ['#ef5350' if r['Open'] < r['Close'] else '#26a69a' for i, r in display_df.iterrows()]
            fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['Volume'], marker_color=colors, name="量"), row=2, col=1)
            
            # MACD
            hist_c = ['#ef5350' if v > 0 else '#26a69a' for v in display_df['MACD_Hist']]
            fig.add_trace(go.Bar(x=display_df['Bar_Index'], y=display_df['MACD_Hist'], marker_color=hist_c, name="MACD"), row=3, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['MACD'], line=dict(color='#ffc107', width=1)), row=3, col=1)
            fig.add_trace(go.Scatter(x=display_df['Bar_Index'], y=display_df['Signal'], line=dict(color='#2196f3', width=1)), row=3, col=1)

            # 標題
            fig.update_layout(height=750, margin=dict(l=10, r=10, t=30, b=10), showlegend=True, 
                            title=f"{masked_name} (代號隱藏) - 現價: {curr_price}",
                            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig.update_xaxes(showticklabels=False, row=1, col=1)
            fig.update_xaxes(showticklabels=False, row=2, col=1)
            st.plotly_chart(fig, use_container_width=True)
            
            with st.expander("📝 交易流水帳"):
                for log in reversed(st.session_state.history):
                    st.text(log)
                if st.session_state.auto_play:
                    time.sleep(0.5)
                    st.session_state.step += 1
                    st.rerun()

        with tab_r:
            st.markdown("### 🏆 英雄榜")
            if os.path.exists(FILES["leaderboard"]):
                try:
                    lb = pd.read_csv(FILES["leaderboard"])
                    st.dataframe(lb.sort_index(ascending=False), use_container_width=True)
                except: st.write("讀取紀錄失敗")
            else:
                st.info("尚無紀錄")

        with tab_v:
            st.markdown("""
            ### v3.2 現實殘酷版 🐢
            * **[New]** 新增「放慢速度」按鈕，但......點了就知道。
            * **[Info]** 聖誕快樂！新增社群追蹤與彩蛋。
            """)

except Exception as e:
    st.error(f"系統發生未預期的錯誤: {e}")
    st.info("請重新整理網頁，或點擊側邊欄的「重開一局」。")
