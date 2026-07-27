import streamlit as st
import gspread
from gspread_dataframe import set_with_dataframe, get_as_dataframe
import pandas as pd
import datetime

STOCKS_COLUMNS = [
    "symbol",
    "companyName",
    "lastDividend",
    "stock_type",
    "group",
    "weight",
    "marketCap",
    "dividendYield",
    "updated_at",
]

# 구글 스프레드 시트 연결 인스턴스 지연 초기화 (Lazy loading)
gc = None
sh = None
connection_error = None

def get_sh():
    global gc, sh, connection_error
    if sh is not None:
        return sh
    try:
        creds = dict(st.secrets["gcp_service_account"])
        # private_key가 JSON에서 개행 문자가 \n 문자열로 들어가 있을 수 있으므로 처리
        if "private_key" in creds:
            creds["private_key"] = creds["private_key"].replace("\\n", "\n")

        gc = gspread.service_account_from_dict(creds)
        spreadsheet_url = st.secrets["google_sheets"]["spreadsheet_url"]
        sh = gc.open_by_url(spreadsheet_url)
        connection_error = None
        return sh
    except Exception as e:
        connection_error = f"구글 시트 연결 실패: secrets.toml 설정 및 공유 상태를 확인해 주세요. 에러: {e}"
        sh = None
        return None



def _normalize_stocks_df(df):
    if df is None or df.empty:
        return pd.DataFrame(columns=STOCKS_COLUMNS)

    safe_df = df.copy()
    for col in STOCKS_COLUMNS:
        if col not in safe_df.columns:
            safe_df[col] = ""

    safe_df = safe_df[STOCKS_COLUMNS]
    safe_df = safe_df.dropna(subset=["symbol"])
    safe_df["symbol"] = safe_df["symbol"].astype(str).str.strip().str.upper()
    safe_df = safe_df[safe_df["symbol"] != ""]
    safe_df["companyName"] = safe_df["companyName"].fillna("").astype(str).str.strip()
    safe_df["stock_type"] = safe_df["stock_type"].fillna("STOCK").astype(str).str.strip().str.upper()
    safe_df["group"] = safe_df["group"].fillna("").astype(str).str.strip()
    safe_df["weight"] = pd.to_numeric(safe_df["weight"], errors="coerce")
    safe_df["marketCap"] = pd.to_numeric(safe_df["marketCap"], errors="coerce")
    safe_df["dividendYield"] = pd.to_numeric(safe_df["dividendYield"], errors="coerce")
    safe_df["updated_at"] = safe_df["updated_at"].fillna("").astype(str)
    return safe_df


def _ensure_sheet_schema(sheet_name, expected_columns):
    """지정한 시트의 컬럼이 기대하는 스키마를 따르도록 보정하고, 누락된 열을 추가합니다."""
    sh = get_sh()
    if not sh:
        return

    ws = sh.worksheet(sheet_name)
    all_values = ws.get_all_values()

    if not all_values:
        ws.append_row(expected_columns)
        return

    headers = [h.strip() for h in all_values[0] if h.strip()]
    missing_cols = [col for col in expected_columns if col not in headers]
    if not missing_cols:
        return

    # 누락된 컬럼이 있으면 시트를 DataFrame으로 읽어서 보정
    df = get_as_dataframe(ws, evaluate_formulas=True)
    df = df.dropna(how='all') # 빈 행 제거
    
    # 누락 컬럼 추가
    for col in missing_cols:
        df[col] = ""
        
    # 기대하는 컬럼만 남기고 순서대로 정렬
    df = df[[c for c in expected_columns if c in df.columns]]
    
    ws.clear()
    set_with_dataframe(ws, df, row=1, col=1, include_index=False, resize=True)


def init_sheets():
    """앱 구동 시 필요한 6개의 시트가 없으면 생성하고 스키마를 보정합니다."""
    sh = get_sh()
    if not sh:
        return

    required_sheets = {
        "stocks": STOCKS_COLUMNS,
        "comments": ["symbol", "content", "updated_at"],
        "watchlist": ["symbol", "group_name", "created_at"],
        "portfolio": ["symbol", "shares", "purchase_price", "entry_reason", "position_type", "created_at", "position_id"],
        "alerts": ["symbol", "target_price", "condition_type", "is_triggered", "created_at"],
        "trading_history": ["symbol", "shares", "purchase_price", "sell_price", "entry_reason", "exit_reason", "position_type", "trade_date", "created_at", "position_id"],
        "order_history": ["symbol", "action_type", "shares", "price", "reason", "position_type", "trade_date", "position_id"]
    }

    existing_sheets = [ws.title for ws in sh.worksheets()]

    for sheet_name, headers in required_sheets.items():
        if sheet_name not in existing_sheets:
            ws = sh.add_worksheet(title=sheet_name, rows=1000, cols=len(headers) + 2)
            ws.append_row(headers)
            print(f"구글 시트 생성 완료: {sheet_name}")
        else:
            _ensure_sheet_schema(sheet_name, headers)


# --- 1. 종목 캐시 (stocks) 관련 ---
def get_stocks():
    """stocks 시트에서 전체 종목 데이터를 DataFrame으로 조회합니다."""
    sh = get_sh()
    if not sh:
        return pd.DataFrame(columns=STOCKS_COLUMNS)

    _ensure_sheet_schema("stocks", STOCKS_COLUMNS)
    ws = sh.worksheet("stocks")
    df = get_as_dataframe(ws, evaluate_formulas=True)
    return _normalize_stocks_df(df)


def save_stocks(df):
    """stocks 시트에 새로운 종목 리스트를 덮어씁니다."""
    sh = get_sh()
    if not sh:
        return

    _ensure_sheet_schema("stocks", STOCKS_COLUMNS)
    safe_df = _normalize_stocks_df(df)

    ws = sh.worksheet("stocks")
    ws.clear()  # 기존 데이터 초기화

    # gspread_dataframe을 이용해 일괄 쓰기
    set_with_dataframe(ws, safe_df, row=1, col=1, include_index=False, resize=True)

    # weight 열(F)은 숫자 서식으로 고정해야 4.5가 날짜(1900-01-03 12:00:00)로 보존되지 않습니다.
    try:
        ws.format(
            "F:F",
            {
                "numberFormat": {
                    "type": "NUMBER",
                    "pattern": "0.00",
                }
            },
        )
    except Exception:
        # 서식 지정 실패 시에도 저장 자체는 완료되도록 무시
        pass


# --- 2. 코멘트 (comments) 관련 ---
def get_comment(symbol):
    """특정 종목의 최신 코멘트를 구글 시트에서 가져옵니다."""
    sh = get_sh()
    if not sh:
        return ""
    ws = sh.worksheet("comments")
    data = ws.get_all_records()
    for row in reversed(data):
        if str(row.get("symbol")).strip().upper() == symbol.strip().upper():
            return row.get("content", "")
    return ""


def save_comment(symbol, content):
    """코멘트를 항상 새로 추가하여 누적 저장합니다."""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("comments")
    
    # 헤더 자동 확장 보정
    try:
        headers = ws.row_values(1)
        if len(headers) < 4:
            ws.update_cell(1, 3, "created_at")
            ws.update_cell(1, 4, "updated_at")
    except Exception:
        pass

    symbol = symbol.strip().upper()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.append_row([symbol, content, now_str, now_str])


def get_comments_list(symbol):
    """특정 종목의 모든 코멘트 리스트를 최초 작성일 최신순으로 가져옵니다 (시트 행 번호 포함)."""
    sh = get_sh()
    if not sh:
        return []
    ws = sh.worksheet("comments")
    data = ws.get_all_values()
    if not data or len(data) <= 1:
        return []
    
    comments = []
    for i, row in enumerate(data[1:]):
        row_num = i + 2  # 헤더가 1행이므로 +2
        if len(row) > 0 and row[0].strip().upper() == symbol.strip().upper():
            created_at = row[2] if len(row) > 2 else ""
            updated_at = row[3] if len(row) > 3 and row[3].strip() else created_at
            comments.append({
                "row_num": row_num,
                "content": row[1] if len(row) > 1 else "",
                "created_at": created_at,
                "updated_at": updated_at
            })
    # 최초 작성일(created_at) 내림차순 정렬
    comments.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
    return comments


def update_comment_by_row(row_num, new_content):
    """특정 행 번호의 코멘트 내용을 수정합니다 (최초 작성일은 보존하고 수정일만 갱신)."""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("comments")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.update_cell(row_num, 2, new_content)
    ws.update_cell(row_num, 4, now_str)


def delete_comment_by_row(row_num):
    """특정 행 번호의 코멘트 행을 삭제합니다."""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("comments")
    ws.delete_rows(row_num)


# --- 3. 관심 종목 (watchlist) 관련 ---
def get_watchlist():
    """관심 종목 리스트를 단순히 티커 목록만 가져옵니다 (호환성 유지)."""
    sh = get_sh()
    if not sh:
        return []
    ws = sh.worksheet("watchlist")
    data = ws.get_all_records()
    watchlist = []
    for row in data:
        symbol = str(row.get("symbol")).strip().upper()
        if symbol:
            watchlist.append(symbol)
    return watchlist


def get_watchlist_details():
    """관심 종목 리스트를 상세 정보(그룹 포함) DataFrame으로 가져옵니다."""
    sh = get_sh()
    if not sh:
        return pd.DataFrame(columns=["symbol", "group_name", "created_at"])
    ws = sh.worksheet("watchlist")
    df = get_as_dataframe(ws).dropna(subset=["symbol"])
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    if "group_name" in df.columns:
        df["group_name"] = df["group_name"].fillna("기본 그룹").astype(str).str.strip()
    else:
        df["group_name"] = "기본 그룹"
    return df


def add_to_watchlist(symbol, group_name="기본 그룹"):
    """관심 종목의 특정 그룹에 추가합니다. (다중 그룹 소속 지원)"""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("watchlist")
    symbol = symbol.strip().upper()
    group_name = group_name.strip() if group_name else "기본 그룹"
    data = ws.get_all_values()

    # 이미 동일한 symbol과 group_name 쌍이 존재하는지 확인
    exists = False
    for i, row in enumerate(data):
        if i == 0:
            continue
        row_sym = row[0].strip().upper()
        row_grp = row[1].strip() if len(row) > 1 else ""
        if row_sym == symbol and row_grp.upper() == group_name.upper():
            exists = True
            # 시간 업데이트
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ws.update_cell(i + 1, 3, now_str)
            break

    if not exists:
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ws.append_row([symbol, group_name, now_str])


def remove_from_watchlist(symbol, group_name=None):
    """관심 종목에서 제거합니다. group_name이 지정되면 특정 그룹에서만 제거하고, 없으면 모든 그룹에서 제거합니다."""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("watchlist")
    symbol = symbol.strip().upper()
    data = ws.get_all_values()

    rows_to_delete = []
    for i, row in enumerate(data):
        if i == 0:
            continue
        row_sym = row[0].strip().upper()
        row_grp = row[1].strip() if len(row) > 1 else ""
        
        if row_sym == symbol:
            if group_name is None or row_grp.strip().upper() == group_name.strip().upper():
                rows_to_delete.append(i + 1)

    # 행 인덱스 변화를 예방하기 위해 역순으로 삭제 실행
    for r in sorted(rows_to_delete, reverse=True):
        ws.delete_rows(r)


# --- 4. 포트폴리오 (portfolio) 관련 ---
def get_portfolio():
    """포트폴리오 리스트를 DataFrame으로 가져옵니다."""
    expected_cols = ["symbol", "shares", "purchase_price", "entry_reason", "position_type", "created_at", "position_id"]
    sh = get_sh()
    if not sh:
        return pd.DataFrame(columns=expected_cols)
    ws = sh.worksheet("portfolio")
    df = get_as_dataframe(ws).dropna(subset=["symbol"])
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    if "entry_reason" in df.columns:
        df["entry_reason"] = df["entry_reason"].fillna("").astype(str).str.strip()
    else:
        df["entry_reason"] = ""
    if "position_type" in df.columns:
        df["position_type"] = df["position_type"].fillna("LONG").astype(str).str.strip().str.upper()
    else:
        df["position_type"] = "LONG"
    if "position_id" not in df.columns:
        df["position_id"] = ""
    return df


def save_portfolio(symbol, shares, purchase_price, entry_reason="", position_type="LONG", position_id=None):
    """포트폴리오 아이템을 추가하거나 수정합니다."""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("portfolio")
    symbol = symbol.strip().upper()
    position_type = position_type.strip().upper() if position_type else "LONG"
    data = ws.get_all_values()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    found_idx = -1

    for i, row in enumerate(data):
        if i == 0:
            continue
        row_pos_type = row[4].strip().upper() if len(row) > 4 else "LONG"
        if row and row[0].strip().upper() == symbol and row_pos_type == position_type:
            found_idx = i
            break

    if found_idx != -1:
        row_num = found_idx + 1
        ws.update_cell(row_num, 2, float(shares))
        ws.update_cell(row_num, 3, float(purchase_price))
        ws.update_cell(row_num, 4, entry_reason)
        ws.update_cell(row_num, 5, position_type)
        # 최초 진입일(6열)은 기존값을 보존해야 하므로 업데이트하지 않습니다.
        if position_id:
            ws.update_cell(row_num, 7, position_id)
    else:
        if not position_id:
            position_id = f"pos_{symbol.lower()}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        ws.append_row([symbol, float(shares), float(purchase_price), entry_reason, position_type, now_str, position_id])


def remove_from_portfolio(symbol, position_type="LONG"):
    """포트폴리오에서 아이템을 제거합니다."""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("portfolio")
    symbol = symbol.strip().upper()
    position_type = position_type.strip().upper() if position_type else "LONG"
    data = ws.get_all_values()

    for i, row in enumerate(data):
        if i == 0:
            continue
        row_pos_type = row[4].strip().upper() if len(row) > 4 else "LONG"
        if row and row[0].strip().upper() == symbol and row_pos_type == position_type:
            ws.delete_rows(i + 1)
            break


# --- 5. 조건부 타겟 (alerts) 관련 ---
def get_alerts():
    """조건부 타겟 가격 알림 설정 목록을 DataFrame으로 조회합니다."""
    sh = get_sh()
    if not sh:
        return pd.DataFrame(columns=["symbol", "target_price", "condition_type", "is_triggered", "created_at"])
    ws = sh.worksheet("alerts")
    df = get_as_dataframe(ws).dropna(subset=["symbol"])
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    df["target_price"] = pd.to_numeric(df["target_price"], errors="coerce")
    df["condition_type"] = df["condition_type"].fillna("above").astype(str).str.strip()
    
    # 불리언 형식 마이그레이션 및 파싱
    if "is_triggered" in df.columns:
        df["is_triggered"] = df["is_triggered"].astype(str).str.upper() == "TRUE"
    else:
        df["is_triggered"] = False
    return df


def save_alert(symbol, target_price, condition_type="above"):
    """조건부 타겟을 설정/저장합니다. (동일 조건이 이미 존재하면 덮어씀)"""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("alerts")
    symbol = symbol.strip().upper()
    condition_type = condition_type.strip()
    data = ws.get_all_values()

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    found_idx = -1

    for i, row in enumerate(data):
        if i == 0:
            continue
        if row and len(row) >= 3 and row[0].strip().upper() == symbol and row[2].strip() == condition_type:
            found_idx = i
            break

    if found_idx != -1:
        row_num = found_idx + 1
        ws.update_cell(row_num, 2, float(target_price))
        ws.update_cell(row_num, 4, "FALSE")  # 새로 설정 시 트리거 여부 초기화
        ws.update_cell(row_num, 5, now_str)
    else:
        ws.append_row([symbol, float(target_price), condition_type, "FALSE", now_str])


def remove_alert(symbol, condition_type):
    """특정 조건부 타겟을 감시 목록에서 삭제합니다."""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("alerts")
    symbol = symbol.strip().upper()
    condition_type = condition_type.strip()
    data = ws.get_all_values()

    for i, row in enumerate(data):
        if i == 0:
            continue
        if row and len(row) >= 3 and row[0].strip().upper() == symbol and row[2].strip() == condition_type:
            ws.delete_rows(i + 1)
            break


def set_alert_triggered(symbol, condition_type, is_triggered=True):
    """알림이 트리거되었음을 마킹합니다."""
    sh = get_sh()
    if not sh:
        return
    ws = sh.worksheet("alerts")
    symbol = symbol.strip().upper()
    condition_type = condition_type.strip()
    data = ws.get_all_values()

    for i, row in enumerate(data):
        if i == 0:
            continue
        if row and len(row) >= 3 and row[0].strip().upper() == symbol and row[2].strip() == condition_type:
            val_str = "TRUE" if is_triggered else "FALSE"
            ws.update_cell(i + 1, 4, val_str)
            break


# --- 6. 매매 기록 (trading_history) 관련 ---
def get_trading_history():
    """청산 완료된 매매기록 목록을 DataFrame으로 조회합니다."""
    expected_cols = ["symbol", "shares", "purchase_price", "sell_price", "entry_reason", "exit_reason", "position_type", "trade_date", "created_at"]
    sh = get_sh()
    if not sh:
        return pd.DataFrame(columns=expected_cols)
    ws = sh.worksheet("trading_history")
    df = get_as_dataframe(ws).dropna(subset=["symbol"])
    df["symbol"] = df["symbol"].astype(str).str.strip().str.upper()
    if "position_type" in df.columns:
        df["position_type"] = df["position_type"].fillna("LONG").astype(str).str.strip().str.upper()
    else:
        df["position_type"] = "LONG"
    return df


def liquidate_portfolio(symbol, exit_shares, exit_price, exit_reason=""):
    """포트폴리오 자산을 일부 또는 전부 청산하고 매매기록(trading_history)으로 이관하며 주문 원장에 기록하여 잔고를 재계산합니다."""
    sh = get_sh()
    if not sh:
        return False

    symbol = symbol.strip().upper()
    exit_shares = float(exit_shares)
    exit_price = float(exit_price)

    # 1. 포트폴리오에서 자산 정보 확인
    portfolio_df = get_portfolio()
    match_rows = portfolio_df[portfolio_df["symbol"] == symbol]
    if match_rows.empty:
        return False

    row = match_rows.iloc[0]
    current_shares = float(row["shares"])
    purchase_price = float(row["purchase_price"])
    entry_reason = str(row["entry_reason"]) if pd.notna(row["entry_reason"]) else ""
    position_type = str(row.get("position_type", "LONG")).strip().upper()

    if exit_shares > current_shares:
        exit_shares = current_shares

    # 2. 매매기록(trading_history)에 저장 (시트 컬럼 스키마 유지를 위해 기존 순서대로 매핑 기입)
    ws_hist = sh.worksheet("trading_history")
    trade_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    created_at = str(row["created_at"]) if ("created_at" in row and pd.notna(row["created_at"])) else trade_date
    position_id = str(row["position_id"]).strip() if ("position_id" in row and pd.notna(row["position_id"])) else ""
    ws_hist.append_row([symbol, exit_shares, purchase_price, exit_price, entry_reason, exit_reason, position_type, trade_date, created_at, position_id])

    # 3. 주문 원장(order_history)에 청산 주문 적재 (이를 통해 잔고가 자동 재계산됨)
    # LONG 포지션의 청산 액션은 SELL, SHORT 포지션의 청산 액션은 BUY
    action_type = "BUY" if position_type == "SHORT" else "SELL"
    record_order(symbol, action_type, exit_shares, exit_price, exit_reason, position_type, position_id=position_id)

    return True


def recalculate_position(symbol, position_type):
    """주문 내역(order_history)의 모든 건을 시간순으로 누적 롤업 가중평균하여 portfolio 및 notion 정보를 동기화 재계산합니다."""
    sh = get_sh()
    if not sh:
        return False

    symbol = symbol.strip().upper()
    position_type = position_type.strip().upper()

    # 1. order_history 로딩
    ws_ord = sh.worksheet("order_history")
    df_ord = get_as_dataframe(ws_ord).dropna(subset=["symbol"])
    df_ord["symbol"] = df_ord["symbol"].astype(str).str.strip().str.upper()
    df_ord["position_type"] = df_ord["position_type"].fillna("LONG").astype(str).str.strip().str.upper()
    df_ord["shares"] = pd.to_numeric(df_ord["shares"], errors="coerce").fillna(0.0)
    df_ord["price"] = pd.to_numeric(df_ord["price"], errors="coerce").fillna(0.0)

    # 해당 종목 및 포지션의 주문 필터링
    df_match = df_ord[(df_ord["symbol"] == symbol) & (df_ord["position_type"] == position_type)].copy()
    
    # 시간 순(trade_date) 정렬
    if not df_match.empty:
        df_match = df_match.sort_values(by="trade_date", ascending=True)

    shares = 0.0
    purchase_price = 0.0
    entry_reason = ""
    pos_id = None

    # 포지션 구분(LONG/SHORT)에 따른 수량 증감 거래 성격 분류
    up_action = "SELL" if position_type == "SHORT" else "BUY"
    down_action = "BUY" if position_type == "SHORT" else "SELL"

    for _, row in df_match.iterrows():
        action = str(row["action_type"]).upper()
        o_shares = float(row["shares"])
        o_price = float(row["price"])
        o_reason = str(row["reason"]) if pd.notna(row["reason"]) else ""
        
        # 주문에서 position_id 획득
        if "position_id" in row and pd.notna(row["position_id"]) and str(row["position_id"]).strip():
            pos_id = str(row["position_id"]).strip()

        if action == up_action:
            new_shares = shares + o_shares
            if new_shares > 0:
                purchase_price = ((shares * purchase_price) + (o_shares * o_price)) / new_shares
            shares = new_shares
            if not entry_reason and o_reason:
                entry_reason = o_reason
        elif action == down_action:
            shares = max(0.0, shares - o_shares)
            if shares <= 0.0001:
                shares = 0.0
                purchase_price = 0.0
                entry_reason = ""
                pos_id = None

    # 2. 결과에 따른 포트폴리오 업데이트
    if shares > 0.0001:
        save_portfolio(symbol, shares, purchase_price, entry_reason, position_type, position_id=pos_id)
    else:
        remove_from_portfolio(symbol, position_type)

    # 3. 노션 동기화
    try:
        import notion_helper as nh
        page_id = nh.get_active_position(symbol, position_type)
        if page_id:
            if shares > 0.0001:
                nh.update_position_properties(page_id, avg_price=purchase_price, shares=shares, status="진입중")
            else:
                nh.close_position_journal(page_id, return_rate=0.0, return_val=0.0, feedback="주문 취소에 따른 포지션 자동 전량 롤백 해제")
    except Exception as ne:
        import streamlit as st
        st.warning(f"재계산 중 노션 동기화 실패 (속성 또는 세션 오류): {ne}")

    return True


def remove_order_by_row(symbol, position_type, row_num):
    """order_history 시트에서 잘못 기입된 특정 행(row_num, 1-indexed)을 제거하고 포지션을 재연산합니다."""
    sh = get_sh()
    if not sh:
        return False

    ws_ord = sh.worksheet("order_history")
    
    # gspread delete_rows는 1-indexed 행 번호 기준
    ws_ord.delete_rows(int(row_num))
    
    # 잔고 재계산 실행
    recalculate_position(symbol, position_type)
    return True


def record_order(symbol, action_type, shares, price, reason="", position_type="LONG", position_id=None):
    """주문 원장(order_history) 시트에 체결 이력을 기록합니다. 이후 해당 포지션을 즉시 자동 재연산합니다."""
    sh = get_sh()
    if not sh:
        return False
    
    symbol = symbol.strip().upper()
    action_type = action_type.strip().upper()
    shares = float(shares)
    price = float(price)
    reason = reason.strip() if reason else ""
    position_type = position_type.strip().upper()
    trade_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # position_id 처리
    if not position_id:
        portfolio_df = get_portfolio()
        match_rows = portfolio_df[(portfolio_df["symbol"] == symbol) & (portfolio_df["position_type"] == position_type)]
        if not match_rows.empty and "position_id" in match_rows.columns:
            existing_pos_id = match_rows.iloc[0]["position_id"]
            if pd.notna(existing_pos_id) and str(existing_pos_id).strip():
                position_id = str(existing_pos_id).strip()
        
        # 여전히 발급 안 된 경우 (신규 진입)
        if not position_id:
            position_id = f"pos_{symbol.lower()}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"

    ws = sh.worksheet("order_history")
    ws.append_row([symbol, action_type, shares, price, reason, position_type, trade_date, position_id])
    
    # 백엔드가 즉시 해당 티커/포지션의 잔고를 자동 재연산
    recalculate_position(symbol, position_type)
    return True
