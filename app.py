import streamlit as st
import pandas as pd
import yfinance as yf
import notion_helper as nh
import sheets_helper as sh
import components.cache as cache
import components.header as header
import views.investment_hub as investment_hub
import views.stock_list as stock_list
import views.stock_analysis as stock_analysis

# --- 1. Streamlit Page Configuration ---
st.set_page_config(
    page_title="배당 모니터링 시스템",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CSS 스타일 시트 로드 ---
try:
    with open("assets/style.css", "r", encoding="utf-8") as f:
        css_content = f.read()
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
except Exception as e:
    st.warning(f"CSS 로드 실패: {e}")

# --- 3. 전역 세션 상태 초기화 ---
if "menu" not in st.session_state:
    st.session_state.menu = "💼 내 투자 관리"
if "ticker" not in st.session_state:
    st.session_state.ticker = "AAPL"
if "toast_message" not in st.session_state:
    st.session_state.toast_message = None

# 상단 토스트 알림 감지 및 표출
if st.session_state.toast_message:
    st.toast(st.session_state.toast_message)
    st.session_state.toast_message = None


# --- 4. 알림 조건 실시간 백그라운드 검사 ---
def check_price_alerts():
    """설정된 조건부 타겟 가격 알림 중, 도달한 것이 있는지 yfinance 최신 주가와 비교하여 toast로 띄웁니다."""
    if "alerts_checked" not in st.session_state:
        st.session_state.alerts_checked = {}

    try:
        alerts_df = cache.get_alerts_cached()
    except Exception:
        return

    if alerts_df.empty:
        return

    alert_tickers = alerts_df["symbol"].dropna().unique().tolist()
    if not alert_tickers:
        return

    try:
        price_df = cache.get_alert_prices_cached(alert_tickers)
        if price_df.empty:
            return

        current_prices = {}
        if len(alert_tickers) == 1:
            current_prices[alert_tickers[0]] = float(price_df['Close'].squeeze().iloc[-1])
        else:
            for t in alert_tickers:
                try:
                    current_prices[t] = float(price_df['Close'][t].iloc[-1])
                except Exception:
                    current_prices[t] = 0.0

        for _, row in alerts_df.iterrows():
            sym = row["symbol"]
            target = float(row["target_price"])
            cond = row["condition_type"]
            is_trig = bool(row["is_triggered"])
            
            curr_price = current_prices.get(sym, 0.0)
            if curr_price <= 0.0 or is_trig:
                continue

            alert_key = f"{sym}_{cond}_{target}"
            if st.session_state.alerts_checked.get(alert_key):
                continue

            triggered = False
            if cond == "above" and curr_price >= target:
                triggered = True
            elif cond == "below" and curr_price <= target:
                triggered = True
            elif cond == ">=" and curr_price >= target:
                triggered = True
            elif cond == "<=" and curr_price <= target:
                triggered = True
            elif cond == "==" and abs(curr_price - target) < 0.001:
                triggered = True

            if triggered:
                st.session_state.alerts_checked[alert_key] = True
                sh.trigger_alert(sym, target, cond)
                cache.get_alerts_cached.clear()
                st.toast(f"🎯 [타겟 도달 알림] {sym}의 주가가 ${curr_price:,.2f}에 도달했습니다! (설정조건: {cond} ${target:.2f})")

    except Exception:
        pass


# --- 5. 사이드바 내비게이션 렌더링 ---
with st.sidebar:
    st.markdown("### 🧭 메뉴 이동")
    menu = st.radio(
        "이동할 페이지 선택",
        ["💼 내 투자 관리", "📋 전체 종목 리스트", "📊 개별 종목 분석"],
        label_visibility="collapsed",
        key="menu_radio"
    )
    if menu != st.session_state.menu:
        st.session_state.menu = menu
        st.rerun()

    st.divider()
    check_price_alerts()


# --- 6. 상단 공통 헤더 렌더링 ---
header.render_header()


# --- 7. 라우터에 따른 화면 분할 렌더링 위임 ---
if st.session_state.menu == "💼 내 투자 관리":
    investment_hub.render_page()
elif st.session_state.menu == "📋 전체 종목 리스트":
    stock_list.render_page()
elif st.session_state.menu == "📊 개별 종목 분석":
    stock_analysis.render_page()
