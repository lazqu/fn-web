import streamlit as st
import pandas as pd
import yfinance as yf
import sheets_helper as sh
import notion_helper as nh
import components.cache as cache
import components.forms as fm
import datetime

def conditional_fragment(func):
    if hasattr(st, "fragment"):
        return st.fragment()(func)
    return func

@conditional_fragment
def render_hub_portfolio_panel(sel_ticker, sel_pos, val, cost, sel_price, curr_price, gain_loss, gain_loss_pct, annual_div, sel_shares, sel_reason, sel_pos_id):
    if "hub_active_form" not in st.session_state:
        st.session_state.hub_active_form = None
    if "hub_port_prev_key" not in st.session_state:
        st.session_state.hub_port_prev_key = f"{sel_ticker}_{sel_pos}"
        
    current_key = f"{sel_ticker}_{sel_pos}"
    if st.session_state.hub_port_prev_key != current_key:
        prev_ticker = st.session_state.hub_port_prev_key.split("_")[0]
        fm.clear_form_state_keys(prev_ticker)
        st.session_state.hub_port_prev_key = current_key
        st.session_state.hub_active_form = None

    with st.container(border=True):
        st.markdown(f"### 💼 **{sel_ticker} 자산 상세 지표 ({sel_pos})**")
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.markdown(f"**현재 평가액**: `${val:,.2f}`  \n**투자 원금**: `${cost:,.2f}`  \n**평균 단가**: `${sel_price:,.2f}`")
        with col_d2:
            st.markdown(f"**현재가**: `${curr_price:,.2f}`  \n**평가 손익**: `${gain_loss:+,.2f} ({gain_loss_pct:+.2f}%)`  \n**예상 연간 배당금**: `${annual_div:,.2f}`")
        
    c_act1, c_act2, c_act3 = st.columns(3)
    with c_act1:
        if st.button("📊 상세 분석 차트로 이동", use_container_width=True, key=f"hub_pf_goto_chart_{current_key}", type="primary"):
            st.session_state.ticker = sel_ticker
            st.session_state.menu = "📊 개별 종목 분석"
            st.rerun()
    with c_act2:
        if st.button("➕ 포지션 추가 진입", use_container_width=True, type="primary", key=f"hub_pf_buy_btn_{current_key}"):
            st.session_state.hub_active_form = "buy"
    with c_act3:
        if st.button("🗑️ 포지션 청산", use_container_width=True, key=f"hub_pf_sell_btn_{current_key}"):
            st.session_state.hub_active_form = "sell"

    # 상호 배제 인라인 폼 렌더링
    if st.session_state.hub_active_form == "buy":
        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
        fm.render_purchase_inline_form(sel_ticker, curr_price, True, sel_shares, sel_price, sel_reason, sel_pos, state_key="hub_active_form")
    elif st.session_state.hub_active_form == "sell":
        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
        fm.render_liquidation_inline_form(sel_ticker, curr_price, sel_shares, sel_price, sel_pos, state_key="hub_active_form")

    fm.render_order_history_panel(sel_ticker, sel_pos, sel_pos_id)


@conditional_fragment
def render_hub_watchlist_panel(sel_ticker, sel_group, comments_list, curr_price, all_wl_groups):
    if "hub_active_form" not in st.session_state:
        st.session_state.hub_active_form = None
    if "hub_wl_prev_ticker" not in st.session_state:
        st.session_state.hub_wl_prev_ticker = sel_ticker
        
    if st.session_state.hub_wl_prev_ticker != sel_ticker:
        fm.clear_form_state_keys(st.session_state.hub_wl_prev_ticker)
        st.session_state.hub_wl_prev_ticker = sel_ticker
        st.session_state.hub_active_form = None

    st.subheader(f"⚙️ 선택된 관심종목 제어: {sel_ticker}")
    
    if comments_list:
        if len(comments_list) == 1:
            st.info(f"💬 **관심 종목 코멘트**: {comments_list[0]['content']}")
        else:
            with st.expander(f"💬 전체 코멘트 이력 ({len(comments_list)}개)", expanded=False):
                for idx, c_item in enumerate(comments_list):
                    c_date = c_item['created_at'][:16] if len(c_item['created_at']) >= 16 else c_item['created_at']
                    st.markdown(f"**📅 {c_date}**  \n{c_item['content']}")
                    if idx < len(comments_list) - 1:
                        st.markdown("---")

    c_wl_act1, c_wl_act2, c_wl_act3, c_wl_act4 = st.columns(4)
    
    with c_wl_act1:
        if st.button("📊 상세 차트 분석 이동", use_container_width=True, key=f"hub_wl_goto_chart_{sel_ticker}", type="primary"):
            st.session_state.ticker = sel_ticker
            st.session_state.menu = "📊 개별 종목 분석"
            st.rerun()
            
    with c_wl_act2:
        if st.button("🎯 조건부 타겟 설정", use_container_width=True, key=f"hub_wl_alert_btn_{sel_ticker}"):
            st.session_state.hub_active_form = "alert"
            
    with c_wl_act3:
        if st.button("🚀 포지션 진입", use_container_width=True, key=f"hub_wl_pf_btn_{sel_ticker}"):
            st.session_state.hub_active_form = "wl_pf"
            
    with c_wl_act4:
        if st.button("🗑️ 관심 해제", use_container_width=True, key=f"hub_wl_remove_btn_{sel_ticker}"):
            sh.remove_from_watchlist(sel_ticker, sel_group)
            cache.get_watchlist_cached.clear()
            cache.get_watchlist_details_cached.clear()
            st.session_state.toast_message = f"⭐ {sel_ticker} 관심 해제 완료!"
            st.rerun()

    # 상호 배제 인라인 폼 렌더링
    if st.session_state.hub_active_form == "alert":
        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
        fm.render_alert_inline_form(sel_ticker, curr_price, state_key="hub_active_form")
    elif st.session_state.hub_active_form == "wl_pf":
        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
        fm.render_wl_pf_inline_form(sel_ticker, curr_price, state_key="hub_active_form")
            
    with st.expander("📁 관심 그룹 이동/변경 및 신규 추가"):
        with st.form(f"wl_group_change_form_{sel_ticker}", clear_on_submit=True):
            new_grp_select = st.selectbox("이동할 그룹 선택", all_wl_groups + ["+ 새 그룹 추가..."], key=f"hub_wl_grp_sel_{sel_ticker}")
            new_grp_text = ""
            if new_grp_select == "+ 새 그룹 추가...":
                new_grp_text = st.text_input("새 그룹 이름 입력", "", key=f"hub_wl_grp_text_{sel_ticker}").strip()
            
            grp_change_submit = st.form_submit_button("관심 그룹 변경 적용")
            if grp_change_submit:
                target_group = new_grp_text if new_grp_select == "+ 새 그룹 추가..." else new_grp_select
                if target_group:
                    sh.remove_from_watchlist(sel_ticker, sel_group)
                    sh.add_to_watchlist(sel_ticker, target_group)
                    st.cache_data.clear()
                    st.success(f"{sel_ticker}의 관심 그룹이 '{sel_group}'에서 '{target_group}'으로 변경되었습니다.")
                    st.rerun()
                else:
                    st.error("그룹 이름을 입력해 주세요.")

def render_page():
    st.header("💼 내 투자 관리 (My Investment Hub)")
    
    tab_pf, tab_wl, tab_al, tab_th = st.tabs([
        "💼 내 포트폴리오", 
        "⭐ 관심 종목 & 그룹", 
        "🎯 조건부 타겟", 
        "📝 매매 기록"
    ])
    
    stocks_df = cache.get_stocks_cached()
    
    # ------------------ Tab 1: 내 포트폴리오 ------------------
    with tab_pf:
        st.subheader("보유 자산 현황")
        portfolio_df = cache.get_portfolio_cached()
        
        if portfolio_df.empty:
            st.info("포트폴리오가 현재 비어 있습니다. 사이드바 검색창이나 관심 종목 탭에서 자산을 추가해 주세요.")
        else:
            pf_tickers = portfolio_df['symbol'].tolist()
            close_prices = {}
            
            with st.spinner("보유 종목의 최신 주가 정보를 조회 중..."):
                try:
                    price_data = yf.download(pf_tickers, period="5d", interval="1d")
                    if len(pf_tickers) == 1:
                        close_prices[pf_tickers[0]] = float(price_data['Close'].squeeze().iloc[-1])
                    else:
                        for t in pf_tickers:
                            try:
                                close_prices[t] = float(price_data['Close'][t].iloc[-1])
                            except Exception:
                                close_prices[t] = 0.0
                except Exception as e:
                    st.error(f"실시간 주가 로딩 실패 (이전 평단가로 대체): {e}")
                    close_prices = {t: 0.0 for t in pf_tickers}
            
            total_invested = 0.0
            total_current_val = 0.0
            total_annual_div = 0.0
            rows = []
            
            for _, row in portfolio_df.iterrows():
                sym = row['symbol']
                shares = float(row['shares'])
                avg_cost = float(row['purchase_price'])
                entry_reason = row['entry_reason'] if pd.notna(row['entry_reason']) else ""
                pos_type = str(row.get('position_type', 'LONG')).upper()
                
                curr_price = close_prices.get(sym, 0.0)
                if curr_price == 0.0:
                    curr_price = avg_cost
                    
                stock_info = stocks_df[stocks_df['symbol'] == sym]
                name = stock_info.iloc[0]['companyName'] if not stock_info.empty else sym
                
                last_div = float(stock_info.iloc[0]['lastDividend']) if not stock_info.empty else 0.0
                annual_div_per_share = last_div * 4
                
                cost = shares * avg_cost
                
                if pos_type == "SHORT":
                    gain_loss = shares * (avg_cost - curr_price)
                    val = cost + gain_loss
                    annual_div = -shares * annual_div_per_share
                else:
                    gain_loss = shares * (curr_price - avg_cost)
                    val = shares * curr_price
                    annual_div = shares * annual_div_per_share
                
                total_invested += cost
                total_current_val += val
                total_annual_div += annual_div
                
                gain_loss_pct = (gain_loss / cost * 100) if cost > 0 else 0.0
                
                rows.append({
                    '티커': sym,
                    '포지션': pos_type,
                    '종목명': name,
                    '수량': shares,
                    '평균 단가': avg_cost,
                    '현재가': curr_price,
                    '투자 원금 ($)': cost,
                    '현재 평가액 ($)': val,
                    '수익률 (%)': gain_loss_pct,
                    '예상 연간 배당금 ($)': annual_div,
                    '배당수익률(평단 기준)': (annual_div_per_share / avg_cost * 100) if avg_cost > 0 else 0.0,
                    '진입 근거': entry_reason
                })
                
            m1, m2 = st.columns(2)
            m1.metric("총 투자원금", f"${total_invested:,.2f}")
            
            total_gain = total_current_val - total_invested
            total_gain_pct = (total_gain / total_invested * 100) if total_invested > 0 else 0.0
            m2.metric("총 평가금액", f"${total_current_val:,.2f}", f"{total_gain_pct:+.2f}%")
            
            st.divider()
            
            pf_display_df = pd.DataFrame(rows)
            event_pf = st.dataframe(
                pf_display_df[['티커', '포지션', '현재가', '수량', '수익률 (%)']],
                width="stretch",
                hide_index=True,
                column_config={
                    "현재가": st.column_config.NumberColumn("현재가", format="$%,.2f"),
                    "수량": st.column_config.NumberColumn("수량", format="%.1f"),
                    "수익률 (%)": st.column_config.NumberColumn("수익률", format="%+.2f%%")
                },
                selection_mode="single-row",
                on_select="rerun",
                key="pf_dataframe"
            )
            
            selected_rows = event_pf.selection.rows
            if selected_rows:
                selected_idx = selected_rows[0]
                if selected_idx < len(pf_display_df):
                    sel_ticker = pf_display_df.iloc[selected_idx]['티커']
                    sel_row = portfolio_df[portfolio_df['symbol'] == sel_ticker].iloc[0]
                    sel_shares = float(sel_row['shares'])
                    sel_price = float(sel_row['purchase_price'])
                    sel_reason = str(sel_row['entry_reason']) if pd.notna(sel_row['entry_reason']) else ""
                    sel_pos = str(sel_row.get('position_type', 'LONG')).upper()
                    sel_pos_id = str(sel_row.get('position_id', '')).strip()
                    
                    curr_price = close_prices.get(sel_ticker, 0.0)
                    if curr_price == 0.0:
                        curr_price = sel_price
                    cost = sel_shares * sel_price
                    
                    if sel_pos == "SHORT":
                        gain_loss = sel_shares * (sel_price - curr_price)
                        val = cost + gain_loss
                    else:
                        gain_loss = sel_shares * (curr_price - sel_price)
                        val = sel_shares * curr_price
                    gain_loss_pct = (gain_loss / cost * 100) if cost > 0 else 0.0
                    
                    stock_info = stocks_df[stocks_df['symbol'] == sel_ticker]
                    last_div = float(stock_info.iloc[0]['lastDividend']) if not stock_info.empty else 0.0
                    annual_div_per_share = last_div * 4
                    if sel_pos == "SHORT":
                        annual_div = -sel_shares * annual_div_per_share
                    else:
                        annual_div = sel_shares * annual_div_per_share
                    
                render_hub_portfolio_panel(sel_ticker, sel_pos, val, cost, sel_price, curr_price, gain_loss, gain_loss_pct, annual_div, sel_shares, sel_reason, sel_pos_id)
            else:
                st.info("💡 위의 포트폴리오 표에서 자산 행을 클릭하시면 즉시 상세 차트 분석 이동 및 추가 진입/청산 처리를 할 수 있는 제어 패널이 나타납니다.")

    # ------------------ Tab 2: 관심 종목 & 그룹 ------------------
    with tab_wl:
        st.subheader("⭐ 내 관심 종목 목록")
        watchlist_details = cache.get_watchlist_details_cached()
        
        with st.expander("📁 관심 그룹 신규 생성 및 정리"):
            with st.form("wl_new_group_form"):
                st.markdown("**새 관심 그룹 및 종목 동시 생성**")
                g_ticker = st.text_input("그룹에 최초 등록할 종목 티커 입력 (예: APPL)", "").strip().upper()
                g_name = st.text_input("새로 생성할 그룹 이름 입력", "").strip()
                g_submit = st.form_submit_button("그룹 생성 및 종목 배정")
                if g_submit:
                    if g_ticker and g_name:
                        sh.add_to_watchlist(g_ticker, g_name)
                        st.cache_data.clear()
                        st.success(f"새 관심 그룹 '{g_name}'에 '{g_ticker}' 등록 완료!")
                        st.rerun()
                    else:
                        st.error("티커와 그룹 이름을 모두 입력해 주세요.")

        if watchlist_details.empty:
            st.info("관심 등록된 종목이 없습니다. 사이드바 검색창이나 우측 그룹 관리를 통해 추가해 주세요.")
        else:
            stocks_unique_df = stocks_df.drop_duplicates(subset=['symbol'])
            
            wl_display_df = watchlist_details.merge(stocks_unique_df, on='symbol', how='left')
            wl_display_df['companyName'] = wl_display_df['companyName'].fillna("").astype(str)
            wl_display_df['lastDividend'] = pd.to_numeric(wl_display_df['lastDividend'], errors='coerce').fillna(0.0)
            wl_display_df['stock_type'] = wl_display_df['stock_type'].fillna("STOCK").astype(str).str.upper()
            
            all_wl_groups = sorted(wl_display_df['group_name'].dropna().unique().tolist())
            wl_group_filter = st.selectbox("관심 그룹별 필터", ["전체"] + all_wl_groups, key="wl_group_filter_box")
            
            if wl_group_filter != "전체":
                wl_filtered_df = wl_display_df[wl_display_df['group_name'] == wl_group_filter]
            else:
                wl_filtered_df = wl_display_df
                
            wl_rows = []
            for _, row in wl_filtered_df.iterrows():
                sym = row['symbol']
                grp = row['group_name']
                name = row['companyName'] if row['companyName'] else sym
                last_div = float(row['lastDividend'])
                annual_div_per_share = last_div * 4
                asset_type = row['stock_type']
                
                wl_rows.append({
                    '티커': sym,
                    '관심 그룹': grp,
                    '회사명': name,
                    '최근 주당 배당금 ($)': last_div,
                    '예상 연배당금 ($)': annual_div_per_share,
                    '자산 분류': asset_type
                })
            
            wl_table_df = pd.DataFrame(wl_rows)
            
            event_wl = st.dataframe(
                wl_table_df,
                width="stretch",
                hide_index=True,
                column_config={
                    "최근 주당 배당금 ($)": st.column_config.NumberColumn("주당 배당금 (분기)", format="$%.4f"),
                    "예상 연배당금 ($)": st.column_config.NumberColumn("연 환산 배당금", format="$%.4f")
                },
                selection_mode="single-row",
                on_select="rerun",
                key="wl_dataframe_table"
            )
            
            selected_wl_rows = event_wl.selection.rows
            if selected_wl_rows:
                selected_idx = selected_wl_rows[0]
                if selected_idx < len(wl_table_df):
                    sel_ticker = wl_table_df.iloc[selected_idx]['티커']
                    sel_group = wl_table_df.iloc[selected_idx]['관심 그룹']
                    
                try:
                    price_data = yf.download(sel_ticker, period="1d", progress=False)
                    if not price_data.empty:
                        curr_price = float(price_data['Close'].squeeze().iloc[-1])
                    else:
                        curr_price = 0.0
                except Exception:
                    curr_price = 0.0

                comments_list = cache.get_comments_list_cached(sel_ticker)
                render_hub_watchlist_panel(sel_ticker, sel_group, comments_list, curr_price, all_wl_groups)
            else:
                st.info("💡 위의 관심 종목 표에서 종목 행을 클릭하시면 차트 이동, 알림 등록, 자산 진입(포폴 등록), 관심 해제 등의 단축 연동 제어가 가능합니다.")

    # ------------------ Tab 3: 조건부 타겟 ------------------
    with tab_al:
        st.subheader("🎯 조건부 타겟 감시 현황")
        alerts_df = cache.get_alerts_cached()
        if alerts_df.empty:
            st.info("감시 중인 조건부 타겟 가격이 없습니다. 사이드바 '종목 신속 조회' 후 개별 분석 페이지에서 등록해 주세요.")
        else:
            al_display = alerts_df.copy().rename(columns={
                'symbol': '티커',
                'target_price': '목표가 ($)',
                'condition_type': '조건 설정',
                'is_triggered': '도달 여부',
                'created_at': '등록 일시'
            })
            al_display['도달 여부'] = al_display['도달 여부'].map(lambda x: "🎯 도달완료" if x else "⏳ 대기중")
            al_display['조건 설정'] = al_display['조건 설정'].map(lambda x: "상승 돌파 (above)" if x == "above" else ("하락 돌파 (below)" if x == "below" else x))
            
            event_al = st.dataframe(
                al_display[['티커', '목표가 ($)', '조건 설정', '도달 여부', '등록 일시']],
                width="stretch",
                hide_index=True,
                selection_mode="single-row",
                on_select="rerun",
                key="al_dataframe_table"
            )
            
            selected_al_rows = event_al.selection.rows
            if selected_al_rows:
                sel_idx = selected_al_rows[0]
                if sel_idx < len(al_display):
                    sel_ticker = al_display.iloc[sel_idx]['티커']
                    sel_cond = alerts_df.iloc[sel_idx]['condition_type']
                
                c_al_act1, c_al_act2 = st.columns(2)
                with c_al_act1:
                    if st.button("📊 상세 분석 이동", key="al_tab_goto_chart", use_container_width=True):
                        st.session_state.ticker = sel_ticker
                        st.session_state.menu = "📊 개별 종목 분석"
                        st.rerun()
                with c_al_act2:
                    if st.button("🗑️ 선택된 알림 삭제", key="al_tab_delete_btn", type="primary", use_container_width=True):
                        sh.remove_alert(sel_ticker, sel_cond)
                        cache.get_alerts_cached.clear()
                        st.session_state.toast_message = f"🎯 {sel_ticker} 알림 삭제 완료!"
                        st.rerun()
            else:
                st.info("💡 위의 표에서 알림 행을 선택하시면 즉시 상세 분석으로 이동하거나 개별 삭제 처리를 할 수 있습니다.")

    # ------------------ Tab 4: 매매 기록 ------------------
    with tab_th:
        st.subheader("📝 청산 및 매매 완료 기록")
        history_df = cache.get_trading_history_cached()
        if history_df.empty:
            st.info("완료된 포지션 청산(매매) 기록이 아직 없습니다. 포트폴리오 탭이나 개별 종목 탭에서 포지션 청산을 실행해 주세요.")
        else:
            history_df['profit'] = history_df.apply(
                lambda r: float(r['shares']) * (float(r['purchase_price']) - float(r['sell_price'])) if str(r.get('position_type', 'LONG')).upper() == 'SHORT'
                else float(r['shares']) * (float(r['sell_price']) - float(r['purchase_price'])),
                axis=1
            )
            history_df['weight_sell_val'] = history_df['shares'] * history_df['sell_price']
            
            agg_df = history_df.groupby(['symbol', 'position_type', 'position_id']).agg(
                total_shares=('shares', 'sum'),
                entry_price=('purchase_price', 'first'),
                sum_weight_sell_val=('weight_sell_val', 'sum'),
                total_profit=('profit', 'sum'),
                final_exit_date=('trade_date', 'max'),
                created_at=('created_at', 'first')
            ).reset_index()
            
            agg_df['weighted_exit_price'] = agg_df['sum_weight_sell_val'] / agg_df['total_shares']
            agg_df['total_profit_pct'] = agg_df.apply(
                lambda r: (r['total_profit'] / (r['total_shares'] * r['entry_price']) * 100) if r['entry_price'] > 0 else 0.0,
                axis=1
            )
            
            def format_date_range(r):
                try:
                    dt_entry = pd.to_datetime(r['created_at'])
                    dt_exit = pd.to_datetime(r['final_exit_date'])
                    holding_days = (dt_exit - dt_entry).total_seconds() / 86400.0
                    holding_days_val = max(0.1, round(holding_days, 1))
                    return f"{dt_entry.strftime('%y.%m.%d')} ~ {dt_exit.strftime('%y.%m.%d')} ({holding_days_val}일)"
                except Exception:
                    return f"{r['created_at']} ~ {r['final_exit_date']}"
                    
            agg_df['거래 기간'] = agg_df.apply(format_date_range, axis=1)
            
            rows_display = []
            total_profit = agg_df['total_profit'].sum()
            for _, row in agg_df.iterrows():
                sym = row['symbol']
                pos_type = row['position_type']
                shares = row['total_shares']
                entry_p = row['entry_price']
                exit_p = row['weighted_exit_price']
                profit = row['total_profit']
                profit_pct = row['total_profit_pct']
                date_range = row['거래 기간']
                
                status_emoji = "🟢 수익" if profit > 0 else ("🔴 손실" if profit < 0 else "⚪ 본전")
                
                rows_display.append({
                    '결과': status_emoji,
                    '티커': sym,
                    '포지션': pos_type,
                    '거래 기간 (보유일)': date_range,
                    '총 수량': shares,
                    '진입 단가 ($)': entry_p,
                    '평균 청산가 ($)': exit_p,
                    '누적 실현손익 ($)': profit,
                    '수익률 (%)': profit_pct,
                    'created_at': row['created_at'],
                    'position_id': row['position_id']
                })
                
            hist_display_df = pd.DataFrame(rows_display)
            if not hist_display_df.empty:
                hist_display_df = hist_display_df.sort_values(by='created_at', ascending=False)
                
            st.metric("💰 총 누적 실현손익", f"${total_profit:,.2f}", delta=f"{total_profit:+.2f}")
            
            l_col1, l_col2 = st.columns([3, 1])
            with l_col1:
                try:
                    notion_db_id = st.secrets["notion"]["database_id"].replace("-", "")
                    st.link_button("📓 내 노션 투자 저널 전체 보기", f"https://notion.so/{notion_db_id}", use_container_width=True)
                except Exception:
                    st.link_button("📓 내 노션 투자 저널 전체 보기", "https://notion.so", use_container_width=True)
            with l_col2:
                if st.button("🔄 기록 새로고침", use_container_width=True, key="refresh_th_tab"):
                    st.cache_data.clear()
                    st.rerun()
                    
            st.divider()
            
            event_th = st.dataframe(
                hist_display_df[['티커', '포지션', '누적 실현손익 ($)', '수익률 (%)']],
                width="stretch",
                hide_index=True,
                column_config={
                    "누적 실현손익 ($)": st.column_config.NumberColumn("실현 손익", format="$%.2f"),
                    "수익률 (%)": st.column_config.NumberColumn("수익률 (%)", format="%+.2f%%")
                },
                selection_mode="single-row",
                on_select="rerun",
                key="th_dataframe_table"
            )
            
            selected_th_rows = event_th.selection.rows
            if selected_th_rows:
                sel_idx = selected_th_rows[0]
                if sel_idx < len(hist_display_df):
                    sel_row = hist_display_df.iloc[sel_idx]
                    sel_ticker = sel_row['티커']
                    sel_created = sel_row['created_at']
                    sel_pos = sel_row['포지션']
                    sel_pos_id = sel_row.get('position_id', '')
                    
                    sel_shares = sel_row['총 수량']
                    sel_entry_p = sel_row['진입 단가 ($)']
                    sel_exit_p = sel_row['평균 청산가 ($)']
                    sel_date_range = sel_row['거래 기간 (보유일)']
                    sel_profit = sel_row['누적 실현손익 ($)']
                    sel_profit_pct = sel_row['수익률 (%)']
                    
                    order_df = cache.get_order_history_cached()
                    
                    if sel_pos_id and str(sel_pos_id).strip():
                        entry_df = order_df[
                            (order_df['position_id'] == sel_pos_id) &
                            (order_df['action_type'] == ("BUY" if sel_pos == "LONG" else "SELL"))
                        ].copy()
                    else:
                        entry_df = order_df[
                            (order_df['symbol'] == sel_ticker) &
                            (order_df['position_type'] == sel_pos) &
                            (order_df['action_type'] == ("BUY" if sel_pos == "LONG" else "SELL")) &
                            (order_df['trade_date'] >= sel_created) &
                            (order_df['trade_date'] <= str(sel_row['created_at']))
                        ].copy()
                        
                    if sel_pos_id and str(sel_pos_id).strip():
                        exit_df = history_df[
                            (history_df['symbol'] == sel_ticker) &
                            (history_df['position_type'] == sel_pos) &
                            (history_df['position_id'] == sel_pos_id)
                        ].copy()
                    else:
                        exit_df = history_df[
                            (history_df['symbol'] == sel_ticker) &
                            (history_df['position_type'] == sel_pos) &
                            (history_df['created_at'] == sel_created)
                        ].copy()

                    timeline_records = []
                    
                    for _, r in entry_df.iterrows():
                        o_shares = float(r['shares'])
                        o_price = float(r['price'])
                        timeline_records.append({
                            'type': 'ENTRY',
                            'date': r['trade_date'],
                            'shares': o_shares,
                            'price': o_price,
                            'entry_price': o_price,
                            'cost': o_shares * o_price,
                            'profit': 0.0,
                            'profit_pct': 0.0,
                            'memo': str(r['reason']) if pd.notna(r['reason']) else ""
                        })
                        
                    for _, r in exit_df.iterrows():
                        o_shares = float(r['shares'])
                        o_s_price = float(r['sell_price'])
                        o_p_price = float(r['purchase_price'])
                        o_profit = float(r['profit'])
                        o_profit_pct = (o_profit / (o_shares * o_p_price) * 100) if o_p_price > 0 else 0.0
                        timeline_records.append({
                            'type': 'EXIT',
                            'date': r['trade_date'],
                            'shares': o_shares,
                            'price': o_s_price,
                            'entry_price': o_p_price,
                            'cost': o_shares * o_p_price,
                            'profit': o_profit,
                            'profit_pct': o_profit_pct,
                            'memo': str(r['exit_reason']) if pd.notna(r['exit_reason']) else ""
                        })
                        
                    timeline_records.sort(key=lambda x: str(x['date']))

                    st.subheader(f"🔍 포지션 거래 이력 상세 타임라인: {sel_ticker} ({sel_pos})")
                    
                    closed_page_id = nh.get_closed_position_page_id(sel_ticker, sel_created, sel_pos)
                    if closed_page_id:
                        notion_page_uuid = closed_page_id.replace("-", "")
                        st.link_button(
                            f"📓 {sel_ticker} ({sel_pos}) 노션 투자 저널 바로가기",
                            f"https://notion.so/{notion_page_uuid}",
                            use_container_width=True
                        )
                    else:
                        st.caption("ℹ️ 해당 거래의 상세 노션 투자 저널 페이지를 찾을 수 없습니다.")
                        
                    with st.container(border=True):
                        st.markdown(f"📊 **{sel_ticker} 포지션 최종 실현 성적**")
                        col_h1, col_h2 = st.columns(2)
                        with col_h1:
                            st.markdown(f"**거래 기간**: `{sel_date_range}`  \n**진입 단가**: `${sel_entry_p:,.2f}`  \n**평균 청산가**: `${sel_exit_p:,.2f}`")
                        with col_h2:
                            st.markdown(f"**총 청산 수량**: `{sel_shares:,.1f}주`  \n**누적 실현손익**: `${sel_profit:+,.2f}`  \n**실현 수익률**: `{sel_profit_pct:+.2f}%`")
                            
                    st.markdown("⛓️ **상세 체결 타임라인 (주문 DB 기록)**")
                    
                    for r in timeline_records:
                        o_type = r['type']
                        o_date = r['date']
                        o_shares = r['shares']
                        o_price = r['price']
                        o_memo = r['memo']
                        
                        if o_type == 'ENTRY':
                            emoji = "🟢" if sel_pos.upper() == "LONG" else "🔴"
                            expander_title = f"{emoji} [{sel_pos.upper()} 진입] 📅 {o_date} | 수량 {o_shares:,.1f}주 (@${o_price:,.2f})"
                            with st.expander(expander_title, expanded=False):
                                c1, c2 = st.columns(2)
                                with c1:
                                    st.markdown(f"**진입 단가**: `${o_price:,.2f}`  \n**체결 수량**: `{o_shares:,.1f}주`")
                                with c2:
                                    st.markdown(f"**투자 원금**: `${r['cost']:,.2f}`")
                                if o_memo:
                                    st.info(f"💬 **진입 근거 (메모)**: {o_memo}")
                        else:
                            emoji = "🔴" if sel_pos.upper() == "LONG" else "🟢"
                            expander_title = f"{emoji} [{sel_pos.upper()} 청산] 📅 {o_date} | 청산 {o_shares:,.1f}주 (@${o_price:,.2f})"
                            with st.expander(expander_title, expanded=False):
                                c1, c2 = st.columns(2)
                                with c1:
                                    st.markdown(f"**진입 평단가**: `${r['entry_price']:,.2f}`  \n**청산 단가**: `${o_price:,.2f}`")
                                with c2:
                                    st.markdown(f"**실현 손익**: `${r['profit']:+,.2f}`  \n**수익률 (%)**: `{r['profit_pct']:+.2f}%`")
                                if o_memo:
                                    st.info(f"🏁 **청산 사유**: {o_memo}")
            else:
                st.info("💡 위의 표에서 청산 완료된 포지션 행을 클릭하시면, 하단에 상세 매매 이력과 노션 투자 저널 바로가기 링크가 출력됩니다.")
