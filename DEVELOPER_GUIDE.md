# 🛠️ fn-web 개발자 환경 구축 및 외부 API 연동 가이드

본 문서는 `fn-web` 소스코드를 로컬 환경에서 직접 구동하거나, 자신만의 Google Sheets 및 Notion API 서비스 원장을 연결하기 위한 상세 기술 레퍼런스 가이드입니다.

---

## 1. 외부 서비스(Google Sheets & Notion) 사전 준비

### Step 1. GCP 서비스 계정 생성
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트를 생성하거나 선택합니다.
2. **IAM 및 행정 ➔ 서비스 계정** 메뉴로 이동하여 새로운 서비스 계정(Service Account)을 생성합니다.
3. 생성된 서비스 계정의 [키] 탭에서 **JSON 비대칭 키**를 생성하여 다운로드합니다.
4. 다운로드된 JSON 파일의 `client_email` 주소를 확인합니다.

### Step 2. 구글 스프레드시트 생성 및 권한 공유
1. 개인 구글 드라이브에서 신규 구글 스프레드시트를 생성합니다.
2. 우측 상단 [공유] 버튼을 클릭하고 위 `client_email` 주소를 **편집자(Editor)** 권한으로 추가합니다.
3. 생성된 스프레드시트 URL에서 `SPREADSHEET_ID` 값을 추출합니다:
   ```text
   https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/edit
   ```

### Step 3. Notion API Integration 및 포트폴리오 DB 설정
1. [Notion Developers](https://www.notion.so/my-integrations)에서 새 Integration을 생성하고 발급받은 Internal Integration Secret Token(`NOTION_TOKEN`)을 복사합니다.
2. 노션에서 포트폴리오 저널용 데이터베이스(표 뷰)를 생성하고 아래 **필수 속성(Properties)**을 설정합니다:

| 속성명 (Property Name) | 속성 유형 (Type) | 세부설명 |
| :--- | :--- | :--- |
| **`저널`** | **Title (제목)** | 저널 제목 (예: `SCHD (26.08)`) |
| **`티커`** | **Text (텍스트)** | 주식 티커 (예: `SCHD`, `O`) |
| **`최초 진입일`** | **Date (날짜)** | 포지션 최초 매수일 |
| **`평균 진입 단가`** | **Number (숫자)** | 평단가 |
| **`포지션`** | **Select (단일 선택)** | `LONG`, `SHORT` |
| **`상태`** | **Select (단일 선택)** | `진입중`, `청산완료` |
| **`실현 손익`** | **Number (숫자)** | 청산 완료 시 집계 금액 |
| **`실현 수익률`** | **Number (숫자)** | 청산 완료 시 집계 수익률 |
| **`최종 청산일`** | **Date (날짜)** | 포지션 완청일 |

3. DB 우측 상단 메뉴의 [연결 추가(Add Connections)]를 통해 방금 생성한 Integration을 연결합니다.
4. DB URL에서 32자리 `NOTION_DATABASE_ID`를 추출합니다.

---

## 2. 환경 변수 및 자격 증명 설정 (`.streamlit/secrets.toml`)

프로젝트 루트 디렉토리에 `.streamlit/secrets.toml` 파일(또는 로컬 `.env`)을 작성합니다.

```toml
# [.streamlit/secrets.toml]

# 1. GCP 서비스 계정 자격 증명 (JSON 키 내용)
[gcp_service_account]
type = "service_account"
project_id = "your-project-id"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nYOUR_PRIVATE_KEY\n-----END PRIVATE KEY-----\n"
client_email = "your-service-account@your-project.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"

# 2. Google Sheets 문서 URL
[google_sheets]
spreadsheet_url = "https://docs.google.com/spreadsheets/d/YOUR_SPREADSHEET_ID/edit"

# 3. Notion API 연동 정보
[notion]
token = "secret_your_notion_integration_token_here"
database_id = "your_notion_portfolio_database_id_here"

# 4. 클라우드 웹 접속용 관리자 비밀번호
[admin_auth]
admin_key = "your_custom_password_here"
```

---

## 3. 원장 시트 자동 생성 및 초기화 (Initial DB Setup)

`secrets.toml` 설정 완료 후 아래 데이터 초기화 스크립트를 구동하면 구글 시트에 7개 핵심 원장 테이블(`order_history`, `portfolio`, `trading_history` 등) 구조가 자동 생성됩니다.

```bash
python reset_all_data.py
```

---

## 4. 어플리케이션 구동 및 관리자 모드 접속 2가지 방법

### 🟢 [방법 1] 로컬 CLI 실행 시 관리자 모드 강제 활성화
```bash
# --local 옵션을 주어 실행하면 로컬 환경을 감지하여 관리자(Admin) 모드로 작동합니다.
streamlit run app.py -- --local
```

### 🔵 [방법 2] 배포(클라우드) 서비스 및 웹 브라우저 접속 시 관리자 인증
비밀키가 기입된 URL 쿼리 파라미터를 통해 접속하면 클라우드 배포 서버에서도 관리자 권한으로 자동 승격됩니다.
```text
# 게스트 모드 접속 (기본 샌드박스)
https://gaqu-stock.streamlit.app/

# 관리자 모드 접속 (secrets.toml에 설정한 admin_key 사용)
https://gaqu-stock.streamlit.app/?key={YOUR_ADMIN_KEY}
```

> 💡 **게스트 샌드박스 동작 원리**: `?key` 인증 없이 접속하는 사용자는 실제 DB에 손상을 주지 않는 인메모리 샌드박스 데이터로 구동되므로 누구나 자유롭게 조작 테스트가 가능합니다.
