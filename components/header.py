import streamlit as st

def make_hdr_ticker_uppercase():
    if "hdr_ticker_input" in st.session_state:
        st.session_state.hdr_ticker_input = st.session_state.hdr_ticker_input.strip().upper()

def render_header():
    """상단 공통 플로팅 헤더(타이틀)를 렌더링합니다."""
    with st.container(border=False, key="top_header_container"):
        st.markdown("<h2 style='margin:0; padding:0;'>💰 배당 모니터링 시스템</h2>", unsafe_allow_html=True)

def render_sidebar_search():
    """사이드바 신속 조회 검색 바를 렌더링합니다."""
    st.markdown("### 🔍 종목 검색")
    
    # 외부(종목 리스트 등)에서 st.session_state.ticker가 변경되었을 때 헤더 입력 필드 값을 동기화
    if "prev_ticker" not in st.session_state:
        st.session_state.prev_ticker = st.session_state.ticker
        st.session_state.hdr_ticker_input = st.session_state.ticker

    if st.session_state.ticker != st.session_state.prev_ticker:
        st.session_state.hdr_ticker_input = st.session_state.ticker
        st.session_state.prev_ticker = st.session_state.ticker

    hdr_ticker_input = st.text_input(
        "🔍 종목 신속 조회 (티커 입력)", 
        placeholder="예: AAPL, SCHD",
        label_visibility="collapsed", 
        key="hdr_ticker_input",
        on_change=make_hdr_ticker_uppercase
    ).strip().upper()
    
    hdr_query_btn = st.button("조회", use_container_width=True, key="hdr_query_btn")

    if hdr_query_btn or (hdr_ticker_input and hdr_ticker_input != st.session_state.ticker):
        st.session_state.ticker = hdr_ticker_input
        st.session_state.menu = "📊 개별 종목 분석"
        st.cache_data.clear()
        st.rerun()
