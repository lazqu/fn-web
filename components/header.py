import streamlit as st

def make_hdr_ticker_uppercase():
    if "hdr_ticker_input" in st.session_state:
        st.session_state.hdr_ticker_input = st.session_state.hdr_ticker_input.strip().upper()

def render_header():
    """상단 공통 플로팅 헤더 및 신속 조회 검색 바를 렌더링합니다."""
    with st.container(border=False, key="top_header_container"):
        col_hdr_title, col_inp, col_btn = st.columns([4, 3, 1])
        with col_hdr_title:
            st.markdown("<h2 style='margin:0; padding:0; line-height: 40px;'>💰 배당 모니터링 시스템</h2>", unsafe_allow_html=True)
        with col_inp:
            hdr_ticker_input = st.text_input(
                "🔍 종목 신속 조회 (티커 입력)", 
                value=st.session_state.ticker, 
                placeholder="예: AAPL, SCHD",
                label_visibility="collapsed", 
                key="hdr_ticker_input",
                on_change=make_hdr_ticker_uppercase
            ).strip().upper()
        with col_btn:
            hdr_query_btn = st.button("조회", use_container_width=True, key="hdr_query_btn")

    if hdr_query_btn or (hdr_ticker_input and hdr_ticker_input != st.session_state.ticker):
        st.session_state.ticker = hdr_ticker_input
        st.session_state.menu = "📊 개별 종목 분석"
        st.cache_data.clear()
        st.rerun()

    st.divider()
