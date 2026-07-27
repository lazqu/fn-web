import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import notion_helper as nh
import sheets_helper as sh
import components.cache as cache
import components.forms as fm
import div_yf as dyf
import datetime

def conditional_fragment(func):
    if hasattr(st, "fragment"):
        return st.fragment()(func)
    return func

@conditional_fragment
def render_integrated_action_panel(ticker, current_price):
    if "quick_active_form" not in st.session_state:
        st.session_state.quick_active_form = None
    col_wl, col_al = st.columns(2)

    # 1. 관심 종목 관리 (다중 그룹 소속 지원)
    with col_wl:
        st.markdown("##### ⭐ 관심 종목 설정")
        wl_details = cache.get_watchlist_details_cached()
        
        my_groups = wl_details[wl_details['symbol'] == ticker]['group_name'].tolist() if not wl_details.empty else []
        
        if my_groups:
            st.markdown(f"**현재 소속 그룹**: " + ", ".join([f"`{g}`" for g in my_groups]))
        else:
            st.caption("현재 관심 종목에 등록되어 있지 않습니다.")
            
        all_groups = sorted(wl_details['group_name'].dropna().unique().tolist()) if not wl_details.empty else []
        if "기본 그룹" not in all_groups:
            all_groups.insert(0, "기본 그룹")
            
        group_sel = st.selectbox("추가할 관심 그룹 선택", all_groups + ["+ 새 그룹 추가..."], key="quick_wl_group")
        
        if group_sel == "+ 새 그룹 추가...":
            new_group = st.text_input("새 그룹명 입력", "", key="quick_wl_new_group").strip()
            group_to_save = new_group
        else:
            group_to_save = group_sel

        c_wl_btn1, c_wl_btn2 = st.columns(2)
        with c_wl_btn1:
            if st.button("⭐ 관심 그룹 추가", width="stretch", key="wl_save_btn", type="primary"):
                if group_sel == "+ 새 그룹 추가..." and not group_to_save:
                    st.error("그룹명을 입력해주세요.")
                elif group_to_save in my_groups:
                    st.warning("⚠️ 이미 해당 관심 그룹에 속해 있습니다.")
                else:
                    sh.add_to_watchlist(ticker, group_to_save)
                    if "quick_wl_group" in st.session_state:
                        del st.session_state["quick_wl_group"]
                    if "quick_wl_new_group" in st.session_state:
                        del st.session_state["quick_wl_new_group"]
                    cache.get_watchlist_cached.clear()
                    cache.get_watchlist_details_cached.clear()
                    st.success(f"관심 그룹 '{group_to_save}'에 추가되었습니다!")
                    st.rerun()
        with c_wl_btn2:
            if my_groups:
                del_group_sel = st.selectbox("제거할 그룹 선택", my_groups, key="quick_wl_del_group")
                if st.button("🗑️ 그룹에서 해제", width="stretch", key="wl_del_btn"):
                    sh.remove_from_watchlist(ticker, del_group_sel)
                    cache.get_watchlist_cached.clear()
                    cache.get_watchlist_details_cached.clear()
                    st.success(f"'{del_group_sel}' 그룹에서 해제 완료!")
                    st.rerun()
            else:
                st.button("🗑️ 그룹에서 해제", width="stretch", disabled=True, key="wl_del_btn_dis")

    # 2. 조건부 타겟 관리
    with col_al:
        st.markdown("##### 🎯 조건부 타겟 설정")
        alerts_df = cache.get_alerts_cached()
        my_alerts = alerts_df[alerts_df['symbol'] == ticker]
        if not my_alerts.empty:
            alert_items = []
            for _, a_row in my_alerts.iterrows():
                op = a_row['condition_type']
                if op == "above":
                    cond_str = "상승 돌파 (above)"
                elif op == "below":
                    cond_str = "하락 돌파 (below)"
                else:
                    cond_str = op
                trig_str = "(도달완료)" if a_row['is_triggered'] else "(대기중)"
                alert_items.append(f"${a_row['target_price']:.2f} {cond_str} {trig_str}")
            st.caption("감시 중: " + ", ".join(alert_items))
        else:
            st.caption("설정된 타겟 가격이 없습니다.")

        cond_input = st.text_input("조건식 입력 (예: >= 150 또는 <= 50)", value=f">= {current_price:.2f}", key="quick_al_cond_text")

        c_al_btn1, c_al_btn2 = st.columns(2)
        with c_al_btn1:
            if st.button("🎯 타겟 등록", width="stretch", key="al_save_btn", type="primary"):
                import re
                cond_input = cond_input.strip()
                match = re.match(r"^([><]=?|==)\s*([0-9.]+)", cond_input)
                if match:
                    operator = match.group(1)
                    target_val = float(match.group(2))
                else:
                    try:
                        target_val = float(cond_input)
                        operator = ">=" if target_val >= current_price else "<="
                    except ValueError:
                        st.error("올바른 형식의 조건식을 입력해 주세요. (예: >= 150)")
                        st.stop()
                sh.save_alert(ticker, target_val, operator)
                if "quick_al_cond_text" in st.session_state:
                    del st.session_state["quick_al_cond_text"]
                cache.get_alerts_cached.clear()
                st.success(f"타겟({operator} {target_val}) 저장 완료!")
                st.rerun()
        with c_al_btn2:
            if not my_alerts.empty:
                if st.button("🗑️ 전체 삭제", width="stretch", key="al_del_btn"):
                    for _, a_row in my_alerts.iterrows():
                        sh.remove_alert(ticker, a_row['condition_type'])
                    cache.get_alerts_cached.clear()
                    st.success("타겟 조건 삭제 완료!")
                    st.rerun()
            else:
                st.button("🗑️ 전체 삭제", width="stretch", disabled=True, key="al_del_btn_dis")

    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    st.divider()

    # 3. 포트폴리오 관리 (다음 라인 배치)
    st.markdown("##### 💼 포트폴리오 관리")
    portfolio_df = cache.get_portfolio_cached()
    in_portfolio = ticker in portfolio_df['symbol'].values
    p_shares = 0.0
    p_price = 0.0
    p_entry_reason = ""
    p_pos_type = "LONG"
    if in_portfolio:
        p_row = portfolio_df[portfolio_df['symbol'] == ticker].iloc[0]
        p_shares = float(p_row['shares'])
        p_price = float(p_row['purchase_price'])
        p_entry_reason = str(p_row['entry_reason']) if pd.notna(p_row['entry_reason']) else ""
        p_pos_type = str(p_row.get('position_type', 'LONG')).upper()
        st.info(f"🟢 **현재 포지션 보유 중**: **{p_shares}주** (가중 평균 평단: **${p_price:.2f}** | 포지션 유형: **{p_pos_type}**)")
    else:
        st.caption("현재 이 종목의 포트폴리오 자산이 등록되어 있지 않습니다 (미보유 상태).")

    c_pf_btns = st.columns(2)
    with c_pf_btns[0]:
        buy_btn_label = "➕ 추가 진입" if in_portfolio else "🚀 신규 진입"
        if st.button(buy_btn_label, use_container_width=True, type="primary", key="quick_pf_buy_btn"):
            st.session_state.quick_active_form = "buy"
            st.rerun()
    with c_pf_btns[1]:
        if in_portfolio:
            if st.button("🗑️ 청산", use_container_width=True, key="quick_pf_sell_btn"):
                st.session_state.quick_active_form = "sell"
                st.rerun()
        else:
            st.button("🗑️ 포지션 청산", disabled=True, use_container_width=True, key="quick_pf_sell_dis")

    # 상호 배제형 동적 인라인 폼 렌더링
    if st.session_state.quick_active_form == "buy":
        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
        fm.render_purchase_inline_form(ticker, current_price, in_portfolio, p_shares, p_price, p_entry_reason, p_pos_type, state_key="quick_active_form")
    elif st.session_state.quick_active_form == "sell" and in_portfolio:
        st.markdown("<div style='margin-top:15px;'></div>", unsafe_allow_html=True)
        fm.render_liquidation_inline_form(ticker, current_price, p_shares, p_price, p_pos_type, state_key="quick_active_form")

    # 보유 중일 때 최근 체결 이력 취소 관리 패널 출력
    if in_portfolio:
        p_pos_id = str(p_row.get("position_id", "")).strip() if "position_id" in p_row else ""
        fm.render_order_history_panel(ticker, p_pos_type, p_pos_id)


@conditional_fragment
def render_chart_section(ticker, df_price, df_stat, df_div_period, df_com, start_date, end_date):
    tab1, tab2 = st.tabs(["📊 분석 차트", "📜 배당 상세 내역"])
    with tab1:
        period_options = {
            "전체": None,
            "5년": pd.Timedelta(days=365 * 5),
            "1년": pd.Timedelta(days=365),
            "6개월": pd.Timedelta(days=180),
            "3개월": pd.Timedelta(days=90)
        }

        selected_label = st.radio(
            "조회 기간 (Quick Selector)",
            options=list(period_options.keys()),
            index=0,
            horizontal=True
        )

        actual_end_date = pd.to_datetime(end_date)
        if period_options[selected_label] is not None:
            actual_start_date = actual_end_date - period_options[selected_label]
            actual_start_date = max(actual_start_date, df_price.index.min())
        else:
            actual_start_date = pd.to_datetime(start_date)

        df_filtered = df_price.loc[actual_start_date:actual_end_date]
        df_stat_filtered = df_stat[
            (df_stat['Date'] >= actual_start_date) & 
            (df_stat['Date'] <= actual_end_date)
        ]
        df_com_filtered = df_com[
            (df_com['start_date'] >= actual_start_date) & 
            (df_com['start_date'] <= actual_end_date)
        ].copy()

        if not df_filtered.empty:
            time_buffer = (actual_end_date - actual_start_date) * 0.05
            buffer_date = actual_end_date + time_buffer

            last_row = df_filtered.tail(1).copy()
            last_row.index = [buffer_date]
            last_row.iloc[0] = None
            df_filtered_buffered = pd.concat([df_filtered, last_row]).sort_index()

            if not df_stat_filtered.empty:
                last_row_stat = df_stat_filtered.tail(1).copy()
                last_row_stat.index = [len(df_stat_filtered)]
                last_row_stat.iloc[0] = None
                last_row_stat.loc[last_row_stat.index[0], 'Date'] = buffer_date
                df_stat_filtered_buffered = pd.concat([df_stat_filtered, last_row_stat], ignore_index=True)
            else:
                new_row_stat = pd.DataFrame(columns=df_stat_filtered.columns, index=[0])
                new_row_stat.loc[0, 'Date'] = buffer_date
                df_stat_filtered_buffered = pd.concat([df_stat_filtered, new_row_stat], ignore_index=True)

            df_stat_filtered_buffered = df_stat_filtered_buffered.sort_values('Date').reset_index(drop=True)
        else:
            df_filtered_buffered = df_filtered
            df_stat_filtered_buffered = df_stat_filtered

        fig = make_subplots(
            rows=5, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.07,
            subplot_titles=(
                f"{ticker} 주가 (종가)", 
                "배당수익률(DFS)", 
                "배당금 (Adjusted Dividend)", 
                "배당 성장률 (Dividend Growth)",
                "주가 비교 (Close vs Adj Close)"
            ),
            row_heights=[0.2, 0.2, 0.2, 0.2, 0.2]
        )

        fig.add_trace(
            go.Scatter(x=df_filtered_buffered.index, y=df_filtered_buffered['Close'], name="주가 (종가)", line=dict(color='royalblue', width=1), hovertemplate="%{y}<extra></extra>"),
            row=1, col=1
        )

        fig.add_trace(
            go.Scatter(x=df_stat_filtered_buffered.Date, y=df_stat_filtered_buffered['dfs'], name="배당수익률(DFS)", line=dict(color='firebrick', width=1, dash='solid'), hovertemplate="%{y}<extra></extra>"),
            row=2, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df_stat_filtered_buffered.Date, 
                y=df_stat_filtered_buffered['adj_div'], 
                name="배당금 ($)", 
                line=dict(color='darkorange', width=1.5, shape='hv'),
                hovertemplate="%{y}<extra></extra>"
            ),
            row=3, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df_stat_filtered_buffered.Date,
                y=df_stat_filtered_buffered['div_change'] * 100,
                name="배당 성장률 (%)",
                line=dict(color='rgba(46, 204, 113, 1)', width=1.5, shape='hv'),
                fill='tozeroy',
                fillcolor='rgba(46, 204, 113, 0.15)',
                hovertemplate="%{y}<extra></extra>"
            ),
            row=4, col=1
        )

        fig.add_trace(
            go.Scatter(
                x=df_filtered_buffered.index, 
                y=df_filtered_buffered['Close'], 
                name="Close", 
                line=dict(color='royalblue', width=1),
                hovertemplate="%{y}<extra></extra>"
            ),
            row=5, col=1
        )
        fig.add_trace(
            go.Scatter(
                x=df_filtered_buffered.index, 
                y=df_filtered_buffered['Adj Close'], 
                name="Adj Close", 
                line=dict(color='limegreen', width=1),
                hovertemplate="%{y}<extra></extra>"
            ),
            row=5, col=1
        )

        fig.add_hline(
            y=0,
            line_dash="dash",
            line_color="rgba(255, 255, 255, 0.3)",
            line_width=1,
            row=4,
            col=1
        )

        if not df_div_period.empty and 'Date' in df_div_period.columns and 'period' in df_div_period.columns:
            import plotly.io as pio
            try:
                template = pio.templates.get("plotly_dark")
                grid_color = None
                if template and hasattr(template, "layout"):
                    yaxis = getattr(template.layout, "yaxis", None)
                    if yaxis:
                        grid_color = getattr(yaxis, "gridcolor", None)
                if not grid_color:
                    grid_color = "#444"
            except Exception:
                grid_color = "#444"

            df_div_period_temp = df_div_period.copy()
            df_div_period_temp['Date'] = pd.to_datetime(df_div_period_temp['Date']).dt.tz_localize(None)
            df_div_period_temp['period_changed'] = df_div_period_temp['period'] != df_div_period_temp['period'].shift()

            df_div_period_filtered = df_div_period_temp[
                (df_div_period_temp['Date'] >= pd.to_datetime(actual_start_date)) & 
                (df_div_period_temp['Date'] <= pd.to_datetime(actual_end_date))
            ]

            tick_vals = []
            for _, row in df_div_period_filtered.iterrows():
                date_val = row['Date']
                date_val_dt = pd.to_datetime(date_val).to_pydatetime()
                is_period_changed = row['period_changed']
                line_style = dict(
                    width=1.5 if is_period_changed else 1,
                    dash="solid" if is_period_changed else "dot",
                    color="rgba(128, 128, 128, 0.4)"
                )

                for r in range(1, 6):
                    fig.add_shape(
                        type="line",
                        x0=date_val_dt, x1=date_val_dt,
                        y0=0, y1=1,
                        xref=f"x{r}" if r > 1 else "x",
                        yref=f"y{r} domain" if r > 1 else "y domain",
                        line=line_style,
                        layer="below"
                    )

                if is_period_changed:
                    tick_vals.append(date_val_dt)

            if tick_vals:
                tick_vals_dt = [pd.to_datetime(d).to_pydatetime() for d in tick_vals]
                tick_text = [pd.to_datetime(d).strftime('%Y-%m') for d in tick_vals]
                fig.update_xaxes(
                    tickmode="array",
                    tickvals=tick_vals_dt,
                    ticktext=tick_text,
                    showticklabels=True,
                    tickangle=-45
                )
            else:
                fig.update_xaxes(showticklabels=True, tickangle=-45)

        fig.update_layout(
            title=dict(
                text=f"{ticker} 주가 및 배당 분석",
                x=0.5,
                xanchor="center",
                y=0.965,
                yanchor="top"
            ),
            hovermode="x unified",
            template="plotly_dark",
            height=2000,
            showlegend=False,
            margin=dict(l=50, r=20, t=120, b=50),
            hoverlabel=dict(
                bgcolor="rgba(33, 37, 41, 0.3)",
                font_color="white",
                font_size=11,
                bordercolor="rgba(255, 255, 255, 0.1)"
            )
        )

        for annotation in fig.layout.annotations:
            annotation.font.size = 12
            annotation.y = annotation.y + 0.007

        fig.add_annotation(
            text="<span style='color:royalblue'>■</span> Close &nbsp;&nbsp;&nbsp;&nbsp; <span style='color:limegreen'>■</span> Adj Close",
            xref="x5 domain", yref="y5 domain",
            x=0.01, y=0.95,
            showarrow=False,
            font=dict(size=11, color="white"),
            bgcolor="rgba(30, 30, 30, 0.75)",
            bordercolor="rgba(128, 128, 128, 0.3)",
            borderwidth=1,
            borderpad=4,
            xanchor="left", yanchor="top",
            row=5, col=1
        )

        fig.update_yaxes(
            fixedrange=True,
            showline=True,
            linewidth=1,
            linecolor='rgba(255, 255, 255, 0.3)',
            mirror=False
        )

        fig.update_xaxes(
            type="date",
            showline=True, 
            linewidth=1, 
            linecolor='rgba(255, 255, 255, 0.8)', 
            mirror=False,
            ticks="outside",
            ticklen=5,
            tickwidth=1,
            tickcolor="grey",
            rangeslider=dict(visible=False)
        )

        fig.update_xaxes(
            showspikes=True,
            spikethickness=1,
            spikedash="dot",
            spikecolor="grey",
            spikemode="across",
            spikesnap="data",
            hoverformat="%Y-%m-%d"
        )

        fig.update_yaxes(
            showspikes=True,
            spikethickness=1,
            spikedash="dot",
            spikecolor="grey",
            spikemode="across",
            spikesnap="data"
        )

        st.plotly_chart(fig, width="stretch", config={'scrollZoom': True, 'doubleClick': 'reset'})

    with tab2:
        st.markdown("### 📜 배당 변동 주기별 상세 내역")
        st.markdown("각 배당금 지급 주기별 주요 통계 및 배당성장률 요약표입니다. (최신 주기 순 정렬)")
        
        if not df_com_filtered.empty:
            latest_row = df_com_filtered.iloc[-1]
            latest_div = latest_row['adj_div']
            latest_growth = latest_row['div_change'] * 100 if pd.notnull(latest_row['div_change']) else 0
            avg_growth = df_com_filtered['div_change'].mean() * 100 if df_com_filtered['div_change'].notnull().any() else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("현재 연간 배당금 (환산)", f"${latest_div:.4f}")
            m2.metric("최근 배당 성장률", f"{latest_growth:+.2f}%" if pd.notnull(latest_row['div_change']) else "-")
            m3.metric("평균 배당 성장률", f"{avg_growth:+.2f}%")
            
            st.divider()
            
            df_display = df_com_filtered.copy()
            df_display = df_display.sort_values('period', ascending=False)
            
            df_display = df_display.rename(columns={
                'period': '주기 ID',
                'start_date': '시작일',
                'end_date': '종료일',
                'count': '지급 횟수',
                'dividend_mean': '주당 배당금 (평균)',
                'adj_div': '연간 환산 배당금',
                'div_change': '배당 성장률'
            })
            
            cols_to_show = ['시작일', '종료일', '주당 배당금 (평균)', '지급 횟수', '연간 환산 배당금', '배당 성장률']
            df_display = df_display[cols_to_show]
            df_display['배당 성장률'] = df_display['배당 성장률'] * 100
            
            st.dataframe(
                df_display,
                width="stretch",
                hide_index=True,
                column_config={
                    "시작일": st.column_config.DateColumn("시작일", format="YYYY-MM-DD"),
                    "종료일": st.column_config.DateColumn("종료일", format="YYYY-MM-DD"),
                    "주당 배당금 (평균)": st.column_config.NumberColumn("주당 배당금 (평균)", format="$%.4f"),
                    "지급 횟수": st.column_config.NumberColumn("지급 횟수", format="%d회"),
                    "연간 환산 배당금": st.column_config.NumberColumn("연간 환산 배당금", format="$%.4f"),
                    "배당 성장률": st.column_config.NumberColumn("배당 성장률", format="%.2f%%")
                }
            )
        else:
            st.info("선택한 기간 동안의 배당 변동 데이터가 없습니다.")


@conditional_fragment
def render_comments_section(ticker):
    if "active_edit_row" not in st.session_state:
        st.session_state.active_edit_row = None

    st.markdown("##### ✍️ 투자 메모 및 코멘트")
    
    comment_in = st.text_area(
        "이 종목에 대한 분석이나 진입 근거 등의 기록을 남겨보세요.", 
        value="", 
        height=120, 
        key="quick_comment_input"
    )

    if st.button("➕ 구글 시트에 새 코멘트 추가 저장", use_container_width=True, type="primary"):
        if not comment_in.strip():
            st.warning("추가할 코멘트 내용을 입력해주세요.")
        else:
            sh.save_comment(ticker, comment_in)
            if "quick_comment_input" in st.session_state:
                del st.session_state["quick_comment_input"]
            st.cache_data.clear()
            st.success("새 코멘트가 성공적으로 구글 시트에 추가 저장되었습니다.")
            st.rerun()

    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    comments_history = cache.get_comments_list_cached(ticker)
    if comments_history:
        with st.expander(f"💬 {ticker} 코멘트 히스토리 ({len(comments_history)}건)", expanded=True):
            for i, c in enumerate(comments_history):
                row_num = c['row_num']
                is_editing = (st.session_state.active_edit_row == row_num)

                h_col1, h_col2 = st.columns([5, 2])
                with h_col1:
                    created_val = c.get('created_at', '')
                    updated_val = c.get('updated_at', '')
                    if created_val == updated_val or not updated_val:
                        st.markdown(f"🗓️ **{created_val}**")
                    else:
                        st.markdown(f"🗓️ **{created_val}** *(수정됨: {updated_val})*")
                with h_col2:
                    btn_col1, btn_col2 = st.columns(2)
                    if is_editing:
                        with btn_col1:
                            if st.button("💾 완료", key=f"done_btn_{row_num}", use_container_width=True):
                                new_val = st.session_state.get(f"edit_cmt_txt_{row_num}", "").strip()
                                if new_val:
                                    sh.update_comment_by_row(row_num, new_val)
                                    st.session_state.active_edit_row = None
                                    st.cache_data.clear()
                                    st.success("코멘트가 성공적으로 수정되었습니다.")
                                    st.rerun()
                                else:
                                    st.warning("코멘트 내용을 입력해주세요.")
                        with btn_col2:
                            if st.button("❌ 취소", key=f"cancel_btn_{row_num}", use_container_width=True):
                                st.session_state.active_edit_row = None
                    else:
                        with btn_col1:
                            if st.button("✏️ 수정", key=f"edit_btn_{row_num}", use_container_width=True):
                                st.session_state.active_edit_row = row_num
                        with btn_col2:
                            if st.button("🗑️ 삭제", key=f"del_btn_{row_num}", use_container_width=True):
                                sh.delete_comment_by_row(row_num)
                                st.cache_data.clear()
                                st.success("코멘트가 성공적으로 삭제되었습니다.")
                                st.rerun()
                
                if is_editing:
                    st.text_area(
                        "코멘트 수정 입력창",
                        value=c['content'],
                        height=100,
                        key=f"edit_cmt_txt_{row_num}",
                        label_visibility="collapsed"
                    )
                else:
                    st.write(c['content'])
                
                if i < len(comments_history) - 1:
                    st.divider()
    else:
        st.caption("아직 기록된 코멘트가 없습니다. 위에 새 코멘트를 추가해 보세요.")


def render_page():
    ticker = st.session_state.ticker
    if not ticker:
        st.info("사이드바의 '🔍 종목 신속 조회' 입력창에 분석할 티커를 입력해 주세요. (예: QCOM, KO, PG)")
        st.stop()

    with st.spinner("데이터 로딩 및 차트 작성 중..."):
        try:
            df_price, df_stat, df_div_period, df_com = cache.get_stock_data(ticker)
        except Exception as e:
            st.error(f"데이터 조회에 실패했습니다. 올바른 티커명이거나 배당 내역이 존재하는지 확인해 주세요. 에러: {e}")
            st.stop()

    min_date = df_price.index.min().to_pydatetime().date()
    max_date = df_price.index.max().to_pydatetime().date()

    default_start = max(min_date, pd.to_datetime("2010-01-01").date())

    if "start_date" in st.session_state:
        st.session_state.start_date = max(min_date, min(st.session_state.start_date, max_date))
    else:
        st.session_state.start_date = default_start

    if "end_date" in st.session_state:
        st.session_state.end_date = max(min_date, min(st.session_state.end_date, max_date))
    else:
        st.session_state.end_date = max_date

    start_date = st.session_state.start_date
    end_date = st.session_state.end_date

    try:
        current_price = float(df_price['Close'].iloc[-1])
        latest_div = float(df_com.iloc[-1]['adj_div']) if not df_com.empty else 0.0
        current_yield = latest_div / current_price if current_price > 0 else 0.0
    except Exception:
        current_price = 0.0
        current_yield = 0.0

    m1, m2 = st.columns(2)
    m1.metric("현재 주가", f"${current_price:,.2f}")
    m2.metric("예상 연간 배당수익률", f"{current_yield * 100:.2f}%")

    st.divider()
    st.subheader(f"🛠️ {ticker} 통합 액션 패널")

    render_integrated_action_panel(ticker, current_price)

    render_comments_section(ticker)

    st.divider()

    with st.expander("📅 상세 기간 직접 설정 (날짜 지정)", expanded=False):
        with st.form(key="date_range_form"):
            col1, col2 = st.columns(2)
            with col1:
                start_input = st.date_input(
                    "시작일 입력",
                    value=st.session_state.start_date,
                    min_value=min_date,
                    max_value=max_date
                )
            with col2:
                end_input = st.date_input(
                    "종료일 입력",
                    value=st.session_state.end_date,
                    min_value=min_date,
                    max_value=max_date
                )
            submitted = st.form_submit_button(label="기간 적용 및 조회", width="stretch")

    if submitted:
        if start_input > end_input:
            st.error("시작일은 종료일보다 이전이어야 합니다.")
        else:
            st.session_state.start_date = start_input
            st.session_state.end_date = end_input
            st.rerun()

    render_chart_section(ticker, df_price, df_stat, df_div_period, df_com, start_date, end_date)
