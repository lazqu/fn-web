import os
import toml
import gspread
import requests

# 1. secrets.toml 파일 로드
secrets_path = ".streamlit/secrets.toml"
if not os.path.exists(secrets_path):
    print("Error: secrets.toml not found. (.streamlit/secrets.toml 경로를 확인해 주세요)")
    exit(1)

with open(secrets_path, "r", encoding="utf-8") as f:
    config = toml.load(f)

# GCP & Google Sheets 설정
gcp_creds = config["gcp_service_account"]
if "private_key" in gcp_creds:
    gcp_creds["private_key"] = gcp_creds["private_key"].replace("\\n", "\n")

spreadsheet_url = config["google_sheets"]["spreadsheet_url"]

# Notion 설정
notion_token = config["notion"]["token"]
notion_database_id = config["notion"]["database_id"]

print("=== Google Sheets 데이터 소거 시작 ===")
try:
    gc = gspread.service_account_from_dict(gcp_creds)
    sh = gc.open_by_url(spreadsheet_url)
    
    # 1. portfolio 초기화
    ws_port = sh.worksheet("portfolio")
    ws_port.clear()
    ws_port.append_row(["symbol", "shares", "purchase_price", "entry_reason", "position_type", "created_at"])
    print("[OK] Google Sheets: portfolio 보유 잔고 리셋 완료.")
    
    # 2. trading_history 초기화
    ws_hist = sh.worksheet("trading_history")
    ws_hist.clear()
    ws_hist.append_row(["symbol", "shares", "purchase_price", "sell_price", "entry_reason", "exit_reason", "position_type", "trade_date", "created_at"])
    print("[OK] Google Sheets: trading_history 실현 성적 리셋 완료.")

    # 3. order_history 초기화
    existing_sheets = [ws.title for ws in sh.worksheets()]
    if "order_history" not in existing_sheets:
        sh.add_worksheet(title="order_history", rows=1000, cols=9)
        print("[OK] Google Sheets: order_history 주문 DB 신설 완료.")
        
    ws_ord = sh.worksheet("order_history")
    ws_ord.clear()
    ws_ord.append_row(["symbol", "action_type", "shares", "price", "reason", "position_type", "trade_date"])
    print("[OK] Google Sheets: order_history 주문 DB 리셋 완료.")
except Exception as e:
    print(f"[FAIL] Google Sheets 초기화 중 오류: {e}")

print("\n=== Notion Database 페이지 아카이브 시작 ===")
notion_headers = {
    "Authorization": f"Bearer {notion_token}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28"
}

query_url = f"https://api.notion.com/v1/databases/{notion_database_id}/query"

try:
    has_more = True
    next_cursor = None
    pages_to_archive = []
    
    while has_more:
        payload = {}
        if next_cursor:
            payload["start_cursor"] = next_cursor
        
        resp = requests.post(query_url, json=payload, headers=notion_headers)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            for page in results:
                pages_to_archive.append(page["id"])
            has_more = data.get("has_more", False)
            next_cursor = data.get("next_cursor", None)
        else:
            print(f"[FAIL] Notion DB 조회 에러: {resp.text}")
            has_more = False
            
    print(f"-> 총 {len(pages_to_archive)}개의 액티브 노션 페이지 감지됨. 일괄 삭제 처리 중...")
    
    archived_count = 0
    for page_id in pages_to_archive:
        page_url = f"https://api.notion.com/v1/pages/{page_id}"
        archive_resp = requests.patch(page_url, json={"archived": True}, headers=notion_headers)
        if archive_resp.status_code == 200:
            archived_count += 1
        else:
            print(f"[FAIL] 페이지 {page_id} 삭제 실패: {archive_resp.text}")
            
    print(f"[OK] Notion: {archived_count}개 페이지 최종 아카이브 처리 완료.")
except Exception as e:
    print(f"[FAIL] Notion 리셋 중 오류: {e}")

print("\n=== 전체 시스템 테스트 데이터 완전 초기화 완료 ===")
