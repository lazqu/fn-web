import streamlit as st
import re
import pandas as pd
import sheets_helper as sh
import notion_helper as nh
import components.cache as cache

def clear_form_state_keys(ticker):
    keys = [
        f"dlg_purchase_pos_{ticker}",
        f"dlg_purchase_shares_{ticker}",
        f"dlg_purchase_price_{ticker}",
        f"dlg_purchase_reason_{ticker}",
        f"dlg_liq_shares_{ticker}",
        f"dlg_liq_price_{ticker}",
        f"dlg_liq_reason_{ticker}",
        f"dlg_al_cond_{ticker}",
        f"dlg_wl_pos_sel_{ticker}",
        f"dlg_wl_shares_{ticker}",
        f"dlg_wl_price_{ticker}",
        f"dlg_wl_reason_{ticker}",
        f"form_error_{ticker}"
    ]
    for k in keys:
        if k in st.session_state:
            del st.session_state[k]

def on_cancel_callback(ticker, state_key):
    clear_form_state_keys(ticker)
    st.session_state[state_key] = None

def on_purchase_submit_callback(ticker, current_price, in_portfolio, p_shares, p_price, p_entry_reason, p_pos_type, state_key, trigger_global_rerun):
    shares_add = st.session_state.get(f"dlg_purchase_shares_{ticker}", 0.0)
    price_add = st.session_state.get(f"dlg_purchase_price_{ticker}", 0.0)
    reason_in = st.session_state.get(f"dlg_purchase_reason_{ticker}", "")
    
    if not in_portfolio:
        pos_in = st.session_state.get(f"dlg_purchase_pos_{ticker}", "LONG")
    else:
        pos_in = p_pos_type
        
    if shares_add > 0:
        action_in = "SELL" if pos_in == "SHORT" else "BUY"
        sh.record_order(ticker, action_in, shares_add, price_add, reason_in, pos_in)
        
        # 가중 평균 단가 및 합산 수량 연산
        portfolio_df = sh.get_portfolio()
        match_rows = portfolio_df[(portfolio_df['symbol'] == ticker) & (portfolio_df['position_type'] == pos_in)]
        if not match_rows.empty:
            p_row = match_rows.iloc[0]
            final_shares = float(p_row['shares']) + shares_add
            final_price = ((float(p_row['shares']) * float(p_row['purchase_price'])) + (shares_add * price_add)) / final_shares
        else:
            final_shares = p_shares + shares_add
            if final_shares > 0:
                final_price = ((p_shares * p_price) + (shares_add * price_add)) / final_shares
            else:
                final_price = price_add
                
        nh.sync_entry_to_notion(
            ticker=ticker,
            entry_price=price_add,
            entry_shares=shares_add,
            final_price=final_price,
            final_shares=final_shares,
            entry_reason=reason_in,
            position_type=pos_in
        )
        
        cache.clear_all_caches()
        clear_form_state_keys(ticker)
        st.session_state[state_key] = None
        if trigger_global_rerun:
            st.session_state.toast_message = f"🚀 {ticker} 포지션 진입 완료!"
            st.rerun()
        else:
            st.toast(f"🚀 {ticker} 포지션 진입 완료!")
    else:
        st.session_state[f"form_error_{ticker}"] = "수량을 0보다 크게 입력해주세요."

def on_liquidation_submit_callback(ticker, current_price, p_shares, p_price, p_pos_type, state_key, trigger_global_rerun):
    exit_shares = st.session_state.get(f"dlg_liq_shares_{ticker}", 0.0)
    exit_price = st.session_state.get(f"dlg_liq_price_{ticker}", 0.0)
    exit_reason = st.session_state.get(f"dlg_liq_reason_{ticker}", "")
    
    if exit_shares > 0:
        sh.liquidate_portfolio(ticker, exit_shares, exit_price, exit_reason)
        
        nh.sync_exit_to_notion(
            ticker=ticker,
            exit_price=exit_price,
            exit_shares=exit_shares,
            exit_reason=exit_reason,
            position_type=p_pos_type,
            purchase_price=p_price,
            current_shares=p_shares
        )
        
        cache.clear_all_caches()
        clear_form_state_keys(ticker)
        st.session_state[state_key] = None
        if trigger_global_rerun:
            st.session_state.toast_message = f"🗑️ {ticker} 포지션 {exit_shares}주 청산 완료!"
            st.rerun()
        else:
            st.toast(f"🗑️ {ticker} 포지션 {exit_shares}주 청산 완료!")
    else:
        st.session_state[f"form_error_{ticker}"] = "청산할 수량을 0보다 크게 입력해주세요."

def on_alert_submit_callback(ticker, current_price, state_key, trigger_global_rerun):
    cond_in = st.session_state.get(f"dlg_al_cond_{ticker}", "").strip()
    match = re.match(r"^([><]=?|==)\s*([0-9.]+)", cond_in)
    if match:
        operator = match.group(1)
        target_val = float(match.group(2))
    else:
        try:
            target_val = float(cond_in)
            operator = ">=" if target_val >= current_price else "<="
        except ValueError:
            st.session_state[f"form_error_{ticker}"] = "올바른 형식의 조건식을 입력해 주세요. (예: >= 150)"
            return
            
    sh.save_alert(ticker, target_val, operator)
    cache.get_alerts_cached.clear()
    clear_form_state_keys(ticker)
    st.session_state[state_key] = None
    if trigger_global_rerun:
        st.session_state.toast_message = f"🎯 {ticker} 타겟({operator} {target_val}) 설정 완료!"
        st.rerun()
    else:
        st.toast(f"🎯 {ticker} 타겟({operator} {target_val}) 설정 완료!")

def on_wl_pf_submit_callback(ticker, current_price, state_key, trigger_global_rerun):
    pos_in = st.session_state.get(f"dlg_wl_pos_sel_{ticker}", "LONG")
    shares_in = st.session_state.get(f"dlg_wl_shares_{ticker}", 0.0)
    price_in = st.session_state.get(f"dlg_wl_price_{ticker}", 0.0)
    reason_in = st.session_state.get(f"dlg_wl_reason_{ticker}", "")
    
    if shares_in > 0:
        action_in = "SELL" if pos_in == "SHORT" else "BUY"
        sh.record_order(ticker, action_in, shares_in, price_in, reason_in, pos_in)
        
        nh.sync_entry_to_notion(
            ticker=ticker,
            entry_price=price_in,
            entry_shares=shares_in,
            final_price=price_in,
            final_shares=shares_in,
            entry_reason=reason_in,
            position_type=pos_in
        )
        
        cache.clear_all_caches()
        clear_form_state_keys(ticker)
        st.session_state[state_key] = None
        if trigger_global_rerun:
            st.session_state.toast_message = f"🚀 {ticker} 포지션 진입 완료!"
            st.rerun()
        else:
            st.toast(f"🚀 {ticker} 포지션 진입 완료!")
    else:
        st.session_state[f"form_error_{ticker}"] = "수량을 0보다 크게 입력해주세요."


def render_purchase_inline_form(ticker, current_price, in_portfolio, p_shares=0.0, p_price=0.0, p_entry_reason="", p_pos_type="LONG", state_key="quick_active_form", trigger_global_rerun=True):
    with st.form(f"purchase_inline_form_{ticker}", clear_on_submit=True):
        st.markdown("##### 🚀 신규 진입 / 추가 진입")
        err_msg = st.session_state.get(f"form_error_{ticker}")
        if err_msg:
            st.error(err_msg)
            
        if not in_portfolio:
            pos_in = st.selectbox("포지션 구분", ["LONG", "SHORT"], index=0, key=f"dlg_purchase_pos_{ticker}")
        else:
            pos_in = p_pos_type
            st.info(f"현재 보유 중인 {pos_in} 포지션에 추가 진입합니다.")
        
        st.number_input("진입 수량 (주)", min_value=0.0, value=0.0, step=1.0, key=f"dlg_purchase_shares_{ticker}")
        st.number_input("진입 단가 ($)", min_value=0.0, value=current_price, step=0.01, key=f"dlg_purchase_price_{ticker}")
        st.text_area("상세 진입 근거 및 메모", value="", height=80, key=f"dlg_purchase_reason_{ticker}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.form_submit_button(
                "진입 실행", 
                use_container_width=True, 
                type="primary",
                on_click=on_purchase_submit_callback,
                args=(ticker, current_price, in_portfolio, p_shares, p_price, p_entry_reason, p_pos_type, state_key, trigger_global_rerun)
            )
        with c2:
            st.form_submit_button(
                "❌ 취소", 
                use_container_width=True,
                on_click=on_cancel_callback,
                args=(ticker, state_key)
            )

def render_liquidation_inline_form(ticker, current_price, p_shares, p_price, p_pos_type, state_key="quick_active_form", trigger_global_rerun=True):
    with st.form(f"liq_inline_form_{ticker}", clear_on_submit=True):
        st.markdown("##### 🗑️ 포지션 청산")
        err_msg = st.session_state.get(f"form_error_{ticker}")
        if err_msg:
            st.error(err_msg)
            
        st.info(f"현재 보유: {p_shares}주 (평단 ${p_price:.2f}, {p_pos_type})")
        st.number_input("청산할 수량 (주)", min_value=0.0, max_value=p_shares, value=p_shares, step=1.0, key=f"dlg_liq_shares_{ticker}")
        st.number_input("청산 단가 ($)", min_value=0.0, value=current_price, step=0.01, key=f"dlg_liq_price_{ticker}")
        st.text_area("청산 사유 / 기록", value="", height=80, key=f"dlg_liq_reason_{ticker}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.form_submit_button(
                "청산 실행", 
                use_container_width=True, 
                type="primary",
                on_click=on_liquidation_submit_callback,
                args=(ticker, current_price, p_shares, p_price, p_pos_type, state_key, trigger_global_rerun)
            )
        with c2:
            st.form_submit_button(
                "❌ 취소", 
                use_container_width=True,
                on_click=on_cancel_callback,
                args=(ticker, state_key)
            )

def render_alert_inline_form(ticker, current_price, state_key="quick_active_form", trigger_global_rerun=True):
    with st.form(f"alert_inline_form_{ticker}", clear_on_submit=True):
        st.markdown(f"##### 🎯 {ticker} 조건부 타겟 설정 (현재가: ${current_price:.2f})")
        err_msg = st.session_state.get(f"form_error_{ticker}")
        if err_msg:
            st.error(err_msg)
            
        st.text_input("조건식 입력 (예: >= 150 또는 <= 50)", value=f">= {current_price:.2f}", key=f"dlg_al_cond_{ticker}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.form_submit_button(
                "타겟 등록", 
                use_container_width=True, 
                type="primary",
                on_click=on_alert_submit_callback,
                args=(ticker, current_price, state_key, trigger_global_rerun)
            )
        with c2:
            st.form_submit_button(
                "❌ 취소", 
                use_container_width=True,
                on_click=on_cancel_callback,
                args=(ticker, state_key)
            )

def render_wl_pf_inline_form(ticker, current_price, state_key="quick_active_form", trigger_global_rerun=True):
    with st.form(f"wl_pf_inline_form_{ticker}", clear_on_submit=True):
        st.markdown(f"##### 🚀 {ticker} 포지션 신규 진입 (현재가: ${current_price:.2f})")
        err_msg = st.session_state.get(f"form_error_{ticker}")
        if err_msg:
            st.error(err_msg)
            
        st.selectbox("포지션", ["LONG", "SHORT"], key=f"dlg_wl_pos_sel_{ticker}")
        st.number_input("진입 수량 (주)", min_value=0.0, value=10.0, step=1.0, key=f"dlg_wl_shares_{ticker}")
        st.number_input("진입 단가 ($)", min_value=0.0, value=current_price, step=0.01, key=f"dlg_wl_price_{ticker}")
        st.text_area("진입 사유", value="", height=80, key=f"dlg_wl_reason_{ticker}")
        
        c1, c2 = st.columns(2)
        with c1:
            st.form_submit_button(
                "포지션 진입 실행", 
                use_container_width=True, 
                type="primary",
                on_click=on_wl_pf_submit_callback,
                args=(ticker, current_price, state_key, trigger_global_rerun)
            )
        with c2:
            st.form_submit_button(
                "❌ 취소", 
                use_container_width=True,
                on_click=on_cancel_callback,
                args=(ticker, state_key)
            )


def render_order_history_panel(ticker, pos_type, position_id):
    """지정된 포지션 ID의 주문 체결 이력을 렌더링하고 취소(오기 수정) 기능을 제공합니다."""
    try:
        df_ord = cache.get_order_history_cached().copy()
    except Exception as e:
        st.error(f"주문 내역 로드 실패: {e}")
        return

    if df_ord.empty:
        return

    df_ord["row_num"] = df_ord.index + 2
    df_ord["symbol"] = df_ord["symbol"].astype(str).str.strip().str.upper()
    df_ord["position_type"] = df_ord["position_type"].fillna("LONG").astype(str).str.strip().str.upper()
    df_ord["position_id"] = df_ord["position_id"].fillna("").astype(str).str.strip()
    
    df_match = df_ord[
        (df_ord["symbol"] == ticker.upper()) & 
        (df_ord["position_type"] == pos_type.upper()) &
        (df_ord["position_id"] == str(position_id).strip())
    ].copy()
    
    if df_match.empty:
        return

    df_match = df_match.sort_values(by="trade_date", ascending=False)

    with st.expander("⏳ 최근 체결 이력 (정정/취소 가능)", expanded=False):
        st.info("💡 입력 실수로 잘못 기입된 주문이 있다면 아래 '삭제' 버튼을 눌러 취소할 수 있습니다. (잔고 및 노션이 자동 정정 계산됩니다)")

        for idx, r in df_match.iterrows():
            r_num = int(r["row_num"])
            action = str(r["action_type"]).strip().upper()
            shares = float(r["shares"])
            price = float(r["price"])
            date_str = r["trade_date"]
            reason = str(r["reason"]) if pd.notna(r["reason"]) else ""
            
            date_display = str(date_str)[5:16] if len(str(date_str)) >= 16 else str(date_str)
            
            is_entry = (pos_type.upper() == "LONG" and action == "BUY") or (pos_type.upper() == "SHORT" and action == "SELL")
            if pos_type.upper() == "LONG":
                badge = "🟢 [LONG 진입]" if is_entry else "🔴 [LONG 청산]"
            else:
                badge = "🔴 [SHORT 진입]" if is_entry else "🟢 [SHORT 청산]"
            
            c1, c2, c3 = st.columns([2.5, 7.0, 2.5])
            with c1:
                st.markdown(f"**{badge}**  \n`{date_display}`")
            with c2:
                st.markdown(f"**수량**: `{shares:,.1f}주` | **단가**: `${price:,.2f}` | **원금**: `${shares*price:,.2f}`  \n💬 *{reason if reason else '메모 없음'}*")
            with c3:
                if st.button("🗑️ 삭제", key=f"btn_del_ord_{r_num}", use_container_width=True):
                    if sh.remove_order_by_row(ticker, pos_type, r_num):
                        try:
                            page_id = nh.get_active_position(ticker, pos_type)
                            if page_id:
                                nh.add_order_to_journal(page_id, "취소", shares, price, f"체결 오기입 주문 삭제 (행 번호 {r_num})")
                        except Exception:
                            pass
                        
                        cache.clear_all_caches()
                        st.success("체결 내역이 정상 삭제 및 재산출되었습니다.")
                        st.rerun()
