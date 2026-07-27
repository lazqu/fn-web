import streamlit as st
import pandas as pd
import yfinance as yf
import sheets_helper as sh
import components.cache as cache
import components.dialogs as dlg

def render_page():
    with st.spinner("종목 리스트 불러오는 중..."):
        stocks_df = cache.get_stocks_cached().copy()

    st.header("📋 전체 배당 종목 리스트")
    
    group_times = {g: "-" for g in ["S&P", "Nasdaq", "SCHD", "VIG", "DGRO"]}
    
    if not stocks_df.empty:
        if "group" in stocks_df.columns and "updated_at" in stocks_df.columns:
            temp_groups = stocks_df["group"].fillna("").astype(str).str.strip()
            for g in group_times.keys():
                g_df_times = stocks_df[temp_groups == g]["updated_at"]
                if not g_df_times.empty:
                    raw_time = g_df_times.max()
                    group_times[g] = str(raw_time) if pd.notna(raw_time) else "-"
    
    st.markdown("구글 시트와 연동된 주요 배당주 목록입니다.")
    
    if stocks_df.empty:
        st.warning("구글 시트에 저장된 종목 데이터가 없습니다. 아래 업데이트 버튼을 눌러 데이터를 수집해 주세요.")
    else:
        if "group" not in stocks_df.columns:
            stocks_df["group"] = ""
        if "weight" not in stocks_df.columns:
            stocks_df["weight"] = pd.NA
        if "marketCap" not in stocks_df.columns:
            stocks_df["marketCap"] = pd.NA
        if "dividendYield" not in stocks_df.columns:
            stocks_df["dividendYield"] = pd.NA

        stocks_df["group"] = stocks_df["group"].fillna("").astype(str).str.strip()
        stocks_df["weight"] = pd.to_numeric(stocks_df["weight"], errors="coerce")
        stocks_df["marketCap"] = pd.to_numeric(stocks_df["marketCap"], errors="coerce")
        stocks_df["dividendYield"] = pd.to_numeric(stocks_df["dividendYield"], errors="coerce")

        total_tracked = stocks_df["symbol"].nunique()
        sp500_count = stocks_df[stocks_df["group"] == "S&P"]["symbol"].nunique()
        nasdaq_count = stocks_df[stocks_df["group"] == "Nasdaq"]["symbol"].nunique()

        c1, c2, c3 = st.columns(3)
        c1.metric("총 수집 배당자산", f"{total_tracked}개")
        c2.metric("S&P 500 배당주", f"{sp500_count}개")
        c3.metric("Nasdaq 100 배당주", f"{nasdaq_count}개")
        st.markdown("<div style='padding-top: 15px;'></div>", unsafe_allow_html=True)

        col_search, col_group, col_sort = st.columns([3, 2, 2])
        with col_search:
            search_query = st.text_input("🔍 종목 검색 (티커 또는 회사명)", "").strip().upper()
        with col_group:
            preferred = ["S&P", "Nasdaq", "SCHD", "VIG", "DGRO"]
            groups = [g for g in stocks_df["group"].dropna().unique().tolist() if str(g).strip()]
            group_ordered = [g for g in preferred if g in groups] + sorted([g for g in groups if g not in preferred])
            group_filter = st.selectbox("그룹 필터", ["전체"] + group_ordered)

        etf_groups = ["SCHD", "VIG", "DGRO"]

        sort_options = ["시가총액 순", "배당률 순", "티커 순"]
        if group_filter in etf_groups:
            sort_options.insert(2, "비중 순")

        with col_sort:
            sort_by = st.selectbox("정렬 기준", sort_options)

        filtered_df = stocks_df.copy()

        if group_filter != "전체":
            filtered_df = filtered_df[filtered_df["group"] == group_filter]

        if search_query:
            filtered_df = filtered_df[
                filtered_df["symbol"].astype(str).str.contains(search_query, case=False, na=False)
                | filtered_df["companyName"].astype(str).str.contains(search_query, case=False, na=False)
            ]

        inspector_placeholder = st.empty()
        st.markdown("<div style='padding-top: 5px;'></div>", unsafe_allow_html=True)

        st.markdown(f"**🔍 조건에 맞는 {len(filtered_df)}개의 배당 자산이 조회되었습니다.**")
        
        PRIORITY = {"SCHD": 1, "VIG": 2, "DGRO": 3, "S&P": 4, "Nasdaq": 5}

        if group_filter == "전체":
            grouped = filtered_df.groupby("symbol").agg({
                "companyName": "first",
                "lastDividend": "max",
                "marketCap": "max",
                "dividendYield": "max",
                "weight": "max",
                "group": lambda x: list(set(str(val).strip() for val in x if str(val).strip()))
            }).reset_index()

            def format_group_display(g_list):
                if not g_list:
                    return "-"
                sorted_g = sorted(g_list, key=lambda x: PRIORITY.get(x, 99))
                rep = sorted_g[0]
                if len(sorted_g) > 1:
                    return f"{rep} 외 {len(sorted_g) - 1}"
                return rep

            grouped["group_full"] = grouped["group"].apply(lambda x: ", ".join(sorted(x, key=lambda val: PRIORITY.get(val, 99))))
            grouped["group"] = grouped["group"].apply(format_group_display)
            display_df = grouped
        else:
            display_df = filtered_df.copy()
            display_df["group_full"] = display_df["group"]

        if sort_by == "시가총액 순":
            display_df = display_df.sort_values(by="marketCap", ascending=False, na_position="last")
        elif sort_by == "배당률 순":
            display_df = display_df.sort_values(by="dividendYield", ascending=False, na_position="last")
        elif sort_by == "비중 순":
            display_df = display_df.sort_values(by="weight", ascending=False, na_position="last")
        elif sort_by == "티커 순":
            display_df = display_df.sort_values(by="symbol", ascending=True)

        def format_market_cap(val):
            if pd.isna(val) or val <= 0:
                return "-"
            if val >= 1e12:
                return f"${val / 1e12:.2f}T"
            if val >= 1e9:
                return f"${val / 1e9:.2f}B"
            if val >= 1e6:
                return f"${val / 1e6:.2f}M"
            return f"${val:,.0f}"

        def format_dividend_yield(val):
            if pd.isna(val) or val <= 0:
                return "-"
            return f"{val:.2f}%"

        display_df["formatted_cap"] = display_df["marketCap"].apply(format_market_cap)
        display_df["formatted_yield"] = display_df["dividendYield"].apply(format_dividend_yield)

        display_df.insert(0, "선택", False)
        
        display_df = display_df.rename(columns={
            "symbol": "티커",
            "companyName": "회사명",
            "group": "그룹",
            "formatted_cap": "시가총액",
            "formatted_yield": "배당률",
            "weight": "비중(%)",
        })

        columns_to_show = ["선택", "티커", "회사명", "그룹", "시가총액", "배당률"]
        if group_filter in etf_groups:
            columns_to_show.insert(6, "비중(%)")

        edited_df = st.data_editor(
            display_df[columns_to_show],
            width="stretch",
            hide_index=True,
            height=320,
            column_config={
                "선택": st.column_config.CheckboxColumn("", width=40, default=False),
                "티커": st.column_config.TextColumn("티커", width=60),
                "회사명": st.column_config.TextColumn("회사명", width="medium"),
                "그룹": st.column_config.TextColumn("그룹", width=100),
                "시가총액": st.column_config.TextColumn("시가총액", width=90),
                "배당률": st.column_config.TextColumn("배당률", width=80),
                "비중(%)": st.column_config.NumberColumn("비중(%)", format="%.4f%%", width=70),
            },
            disabled=["티커", "회사명", "그룹", "시가총액", "배당률", "비중(%)"],
            key="stocks_list_editor"
        )

        selected_rows = edited_df[edited_df["선택"] == True]
        
        with inspector_placeholder.container():
            st.markdown('<span class="inspector-marker" style="display:none;">m</span>', unsafe_allow_html=True)
            if not selected_rows.empty:
                st.markdown("<h4 style='font-size: 1.05rem; font-weight: 700; margin: 0 0 10px 0; color: #1e3a8a;'>🔍 선택 종목 상세 제어 패널 (Inspector)</h4>", unsafe_allow_html=True)
                
                selected_stock = selected_rows.iloc[-1]
                sel_ticker = selected_stock["티커"]
                sel_name = selected_stock["회사명"]
                
                sel_group_full = selected_stock["group_full"] if "group_full" in selected_stock else selected_stock["그룹"]
                sel_groups = [g.strip() for g in str(sel_group_full).split(",") if g.strip()]

                BADGE_STYLES = {
                    "SCHD": "background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;",
                    "VIG": "background-color: #f3e8ff; color: #6b21a8; border: 1px solid #e9d5ff;",
                    "DGRO": "background-color: #ecfdf5; color: #065f46; border: 1px solid #a7f3d0;",
                    "S&P": "background-color: #ffedd5; color: #9a3412; border: 1px solid #fed7aa;",
                    "Nasdaq": "background-color: #f1f5f9; color: #334155; border: 1px solid #e2e8f0;"
                }

                badge_htmls = []
                for g in sel_groups:
                    style = BADGE_STYLES.get(g, "background-color: #f1f5f9; color: #334155; border: 1px solid #e2e8f0;")
                    badge_htmls.append(f'<span style="{style} padding: 2px 10px; border-radius: 20px; font-size: 0.68rem; font-weight: 700; margin-right: 4px; margin-bottom: 4px; display: inline-block;">{g}</span>')
                badges_combined = "".join(badge_htmls)

                sel_market_cap = selected_stock["시가총액"]
                sel_yield = selected_stock["배당률"]

                portfolio_df = cache.get_portfolio_cached()
                in_portfolio = sel_ticker in portfolio_df['symbol'].values
                p_shares = 0.0
                p_price = 0.0
                p_entry_reason = ""
                p_pos_type = "LONG"
                
                if in_portfolio:
                    p_row = portfolio_df[portfolio_df['symbol'] == sel_ticker].iloc[0]
                    p_shares = float(p_row['shares'])
                    p_price = float(p_row['purchase_price'])
                    p_entry_reason = str(p_row['entry_reason']) if pd.notna(p_row['entry_reason']) else ""
                    p_pos_type = str(p_row.get('position_type', 'LONG')).upper()

                try:
                    price_data = yf.download(sel_ticker, period="1d", progress=False)
                    if not price_data.empty:
                        sel_curr_price = float(price_data['Close'].squeeze().iloc[-1])
                    else:
                        sel_curr_price = p_price if p_price > 0 else 0.0
                except Exception:
                    sel_curr_price = p_price if p_price > 0 else 0.0

                c_ins1, c_ins2, c_ins3 = st.columns([1, 1, 1])
                
                with c_ins1:
                    st.caption("🏷️ 종목 요약 프로필")
                    st.markdown(f"""
                    <div style="text-align: left; padding: 0; margin: 0;">
                        <h3 style="margin: 0; padding: 0; color: #0f172a; font-weight: 800; font-size: 1.5rem; letter-spacing: -0.01em; line-height: 1.1;">{sel_ticker}</h3>
                        <p style="margin: 5px 0 6px 0; font-size: 0.8rem; font-weight: 500; color: #475569; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; height: 32px; line-height: 1.25;">{sel_name}</p>
                        <div style="font-size: 0.72rem; font-weight: 600; color: #64748b; margin-bottom: 2px;">🏛️ 시가총액: <span style="color: #0f172a; font-weight: 700;">{sel_market_cap}</span></div>
                        <div style="font-size: 0.72rem; font-weight: 600; color: #64748b; margin-bottom: 8px;">💰 배당수익률: <span style="color: #16a34a; font-weight: 700;">{sel_yield}</span></div>
                        <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin: 0; padding: 0;">
                            {badges_combined}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                with c_ins2:
                    st.caption("📝 신속 제어 및 분석")
                    st.markdown("<div style='padding-top: 5px;'></div>", unsafe_allow_html=True)
                    
                    if st.button("📊 상세 차트 분석 이동", width="stretch", type="primary", key="ins_goto_chart"):
                        st.session_state.ticker = sel_ticker
                        st.session_state.menu = "📊 개별 종목 분석"
                        st.cache_data.clear()
                        st.rerun()
                    
                    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
                    wl_details = cache.get_watchlist_details_cached()
                    my_groups = wl_details[wl_details['symbol'] == sel_ticker]['group_name'].tolist() if not wl_details.empty else []
                    
                    if my_groups:
                        st.markdown(f"⭐ **소속 그룹**: " + ", ".join([f"`{g}`" for g in my_groups]))
                    else:
                        st.caption("현재 관심 종목에 등록되어 있지 않습니다.")
                        
                    all_groups = sorted(wl_details['group_name'].dropna().unique().tolist()) if not wl_details.empty else []
                    if "기본 그룹" not in all_groups:
                        all_groups.insert(0, "기본 그룹")
                        
                    group_sel = st.selectbox("추가할 관심 그룹 선택", all_groups + ["+ 새 그룹 추가..."], key="ins_wl_group_sel")
                    if group_sel == "+ 새 그룹 추가...":
                        new_group = st.text_input("새 그룹명 입력", "", key="ins_wl_new_group_text").strip()
                        group_to_save = new_group
                    else:
                        group_to_save = group_sel

                    c_wl_btn1, c_wl_btn2 = st.columns(2)
                    with c_wl_btn1:
                        if st.button("⭐ 관심 추가", width="stretch", key="ins_wl_save_btn", type="primary"):
                            if group_sel == "+ 새 그룹 추가..." and not group_to_save:
                                st.error("그룹명을 입력해주세요.")
                            elif group_to_save in my_groups:
                                st.warning("⚠️ 이미 해당 그룹에 존재합니다.")
                            else:
                                sh.add_to_watchlist(sel_ticker, group_to_save)
                                if "ins_wl_group_sel" in st.session_state:
                                    del st.session_state["ins_wl_group_sel"]
                                if "ins_wl_new_group_text" in st.session_state:
                                    del st.session_state["ins_wl_new_group_text"]
                                cache.get_watchlist_cached.clear()
                                cache.get_watchlist_details_cached.clear()
                                st.success(f"관심 그룹 '{group_to_save}'에 추가 완료!")
                                st.rerun()
                    with c_wl_btn2:
                        if my_groups:
                            del_group_sel = st.selectbox("제거할 그룹 선택", my_groups, key="ins_wl_del_group_sel")
                            if st.button("🗑️ 그룹 해제", width="stretch", key="ins_wl_del_btn"):
                                sh.remove_from_watchlist(sel_ticker, del_group_sel)
                                cache.get_watchlist_cached.clear()
                                cache.get_watchlist_details_cached.clear()
                                st.success(f"'{del_group_sel}' 그룹에서 해제 완료!")
                                st.rerun()
                        else:
                            st.button("🗑️ 그룹 해제", width="stretch", disabled=True, key="ins_wl_del_btn_dis")
                            
                with c_ins3:
                    st.caption("💼 포트폴리오 자산 관리")
                    
                    if in_portfolio:
                        status_tag = f"<span style='font-size:0.75rem;color:#059669;font-weight:700;'>(보유: {p_shares}주 @${p_price:.2f}, {p_pos_type})</span>"
                    else:
                        status_tag = "<span style='font-size:0.75rem;color:#64748b;font-weight:700;'>(미보유)</span>"
                    
                    st.markdown(f"<div style='font-size: 0.8rem; color: #475569; margin-bottom: 8px;'>현황: {status_tag}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='font-size: 0.8rem; color: #475569; margin-bottom: 8px;'>최신가: <b>${sel_curr_price:,.2f}</b></div>", unsafe_allow_html=True)
                    
                    c_pf_btns = st.columns(2)
                    with c_pf_btns[0]:
                        buy_btn_label = "➕ 추가 진입" if in_portfolio else "🚀 신규 진입"
                        if st.button(buy_btn_label, use_container_width=True, type="primary", key="ins_pf_buy_btn"):
                            dlg.show_purchase_dialog(sel_ticker, sel_curr_price, in_portfolio, p_shares, p_price, p_entry_reason, p_pos_type)
                    with c_pf_btns[1]:
                        if in_portfolio:
                            if st.button("🗑️ 청산", use_container_width=True, key="ins_pf_sell_btn"):
                                dlg.show_liquidation_dialog(sel_ticker, sel_curr_price, p_shares, p_price, p_pos_type)
                        else:
                            st.button("🗑️ 포지션 청산", disabled=True, use_container_width=True, key="ins_pf_sell_dis")
            else:
                st.markdown('''
                <div class="inspector-guide-text" style="width: 100% !important; max-width: 100% !important; white-space: normal !important; word-break: break-all !important; overflow-wrap: break-word !important; box-sizing: border-box !important;">
                    💡 아래 표에서 종목의 '선택' 체크박스를 누르시면 이곳에 상세 분석 및 제어 패널(차트이동, 관심종목 토글, 자산 입력)이 즉시 펼쳐집니다.
                </div>
                ''', unsafe_allow_html=True)

    st.divider()
    st.subheader("🔄 데이터 실시간 강제 동기화")
    st.markdown("Wikipedia와 무료 소스를 참조하여 S&P 500, 나스닥 100, SCHD/VIG/DGRO 구성종목 데이터를 동기화합니다.")
    
    with st.form("sync_form", clear_on_submit=False):
        st.markdown("##### ⚙️ 동기화 대상 그룹 선택")
        c_sync1, c_sync2, c_sync3 = st.columns(3)
        with c_sync1:
            sync_sp = st.checkbox("S&P 500 지수", value=True, help="약 500개 종목, 약 2분 소요")
            st.caption(f"🕒 최근 동기화: {group_times.get('S&P', '-')}")
            st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
            sync_nas = st.checkbox("Nasdaq 100 지수", value=True, help="약 100개 종목, 약 30초 소요")
            st.caption(f"🕒 최근 동기화: {group_times.get('Nasdaq', '-')}")
        with c_sync2:
            sync_schd = st.checkbox("SCHD ETF", value=True, help="약 100개 종목, 약 30초 소요")
            st.caption(f"🕒 최근 동기화: {group_times.get('SCHD', '-')}")
            st.markdown("<div style='padding-top: 10px;'></div>", unsafe_allow_html=True)
            sync_vig = st.checkbox("VIG ETF", value=True, help="약 300개 종목, 약 1분 소요")
            st.caption(f"🕒 최근 동기화: {group_times.get('VIG', '-')}")
        with c_sync3:
            sync_dgro = st.checkbox("DGRO ETF", value=True, help="약 400개 종목, 약 1분 소요")
            st.caption(f"🕒 최근 동기화: {group_times.get('DGRO', '-')}")
            
        submit_sync = st.form_submit_button("🔄 선택된 그룹 배당 정보 수동 업데이트", width="stretch")

    if submit_sync:
        selected_sync_groups = []
        if sync_sp: selected_sync_groups.append("S&P")
        if sync_nas: selected_sync_groups.append("Nasdaq")
        if sync_schd: selected_sync_groups.append("SCHD")
        if sync_vig: selected_sync_groups.append("VIG")
        if sync_dgro: selected_sync_groups.append("DGRO")

        if not selected_sync_groups:
            st.warning("동기화할 그룹을 하나 이상 선택해 주세요.")
        else:
            with st.spinner("웹 스크레이퍼 및 yfinance를 실행하여 구글 시트 데이터를 동기화하는 중..."):
                try:
                    import fetch_dividend_stocks as fds
                    fds.run_update(target_groups=selected_sync_groups)

                    success_groups = getattr(fds, "LAST_SUCCESS_GROUPS", [])
                    failed_groups = getattr(fds, "LAST_FAILED_GROUPS", [])

                    if success_groups:
                        st.info(f"성공 그룹: {', '.join(success_groups)}")
                    if failed_groups:
                        st.warning(f"실패 그룹: {', '.join(failed_groups)}")

                    if success_groups:
                        st.cache_data.clear()
                        st.success("구글 시트 동기화가 성공적으로 완료되었습니다!")
                        st.rerun()
                    else:
                        st.error("모든 선택 그룹의 동기화에 실패했습니다.")
                except Exception as e:
                    st.error(f"동기화 중 오류 발생: {e}")
