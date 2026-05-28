# PhilTVTech_bot: 필리핀 TV 기술 및 지역 동향 센싱 서비스

이 프로젝트는 필리핀 현지에 파견된 삼성전자 TV사업부 S/W 개발 주재원 및 현장 모니터링 인력이 수집한 동향 데이터를 분석하여, TV사업부장님이 신흥국 비즈니스 및 기술 기획 의사결정에 참고할 수 있는 고품질의 인사이트 리포트(3대 핵심 소식)를 매일 오전 10시에 자동으로 생성하고 텔레그램 `@PhilTVTech_bot`으로 발송하는 서비스입니다.

---

## 🛠️ 기술 스택 및 아키텍처
* **백엔드**: FastAPI (Python 3.11)
* **프론트엔드**: HTML5, Vanilla CSS (Glassmorphism 다크 테마), JavaScript (AJAX)
* **데이터베이스**: Google Cloud Firestore (GCP 프로덕션) / Local JSON (로컬 테스트용 폴백)
* **AI 인사이트 분석**: Google Gemini API (gemini-2.5-flash 모델 사용, 이전 리포트 피드백 기반 중복 방지)
* **메시지 플랫폼**: Telegram Bot API (주재원 데이터 수집 Webhook 및 리포트 발송)
* **인프라**: Google Cloud Run (Serverless) + Google Cloud Scheduler (Cron Trigger)

---

## 📂 디렉토리 구조
```
C:\Workspace\TechSensing
├── Dockerfile                  # GCP Cloud Run 배포용 컨테이너 빌드 파일
├── README.md                   # 프로젝트 사용 설명서
├── requirements.txt            # Python 의존성 라이브러리 목록
├── .env.example                # 환경 변수 설정 템플릿
├── app/
│   ├── main.py                 # FastAPI 애플리케이션 라우터 및 설정
│   ├── config.py               # 설정 및 환경 변수 유효성 검증
│   ├── database.py             # Firestore 및 로컬 JSON 데이터베이스 모듈
│   ├── bot.py                  # 텔레그램 봇 Webhook 핸들러 및 메시지 전송 모듈
│   ├── analyzer.py             # Gemini API 연동 및 맞춤형 프롬프트 엔진
│   ├── templates/
│   │   └── dashboard.html      # 관리자 로그인 & 센싱 대시보드 UI
│   └── static/
│       ├── css/
│       │   └── style.css       # 미려한 글래스모피즘 다크 모드 CSS
│       └── js/
│           └── app.js          # 모달 오픈 및 리포트 즉시 실행 JS
```

---

## 🚀 로컬 환경 실행 및 테스트 가이드

### 1. 가상환경 설정 및 의존성 설치
```bash
# 가상환경 생성 (Optional)
python -m venv venv
source venv/Scripts/activate  # Windows의 경우: venv\Scripts\activate

# 의존성 패키지 설치
pip install -r requirements.txt
```

### 2. 환경 변수 구성
프로젝트 루트 디렉토리에 `.env` 파일을 생성하고 `.env.example`을 참고하여 아래 설정을 채워 넣습니다:
```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_chat_id_here
GEMINI_API_KEY=your_google_gemini_api_key
CRON_SECRET_TOKEN=secure_cron_token_for_validation
WEB_PASSWORD=admin_dashboard_password_here
```
> **로컬 테스트 팁**: `FIRESTORE_PROJECT_ID`를 입력하지 않을 경우, 자동으로 데이터베이스가 `data/` 폴더에 로컬 JSON 데이터베이스를 생성하여 작동하므로 GCP 연결 없이 빠르게 화면 및 연동 테스트를 할 수 있습니다.

### 3. FastAPI 로컬 실행
```bash
uvicorn app.main:app --reload --port 8000
```
웹 브라우저에서 `http://localhost:8000`으로 접속하여 설정한 `WEB_PASSWORD`로 로그인합니다.

---

## ☁️ GCP (Google Cloud Platform) 배포 가이드

소스코드를 GitHub Repository `DongHyunSong/tech-sensing`에 업로드한 뒤 아래 과정을 통해 GCP에 무중단 서버리스 배포를 세팅합니다.

### STEP 1: GCP Secret Manager에 비밀키 등록
GCP 콘솔의 **Secret Manager**로 이동하여 다음 보안 토큰들을 비밀번호로 등록합니다:
1. `TELEGRAM_BOT_TOKEN`
2. `GEMINI_API_KEY`
3. `CRON_SECRET_TOKEN`
4. `WEB_PASSWORD`

### STEP 2: Google Cloud Run 서비스 배포
1. GCP 콘솔에서 **Cloud Run**을 선택하고 **서비스 만들기**를 클릭합니다.
2. **'소스 리포지토리에서 지속적으로 새 버전 배포'**를 선택하고, GitHub 계정과 연결 후 `DongHyunSong/tech-sensing` 저장소의 `main` 브랜치를 지정합니다.
3. 빌드 설정은 **Cloud Build (Dockerfile 방식)**를 선택합니다.
4. **변수 및 보안 비밀** 탭에서:
   * **환경 변수**:
     * `FIRESTORE_PROJECT_ID` = `본인의-GCP-프로젝트-ID`
     * `WEBHOOK_URL` = `배포가 완료된 후 발급받을 Cloud Run 서비스의 HTTPS URL`
   * **보안 비밀(Secrets)**: Step 1에서 등록한 비밀키 4종을 각각의 환경 변수로 매핑합니다.
5. **허용량**: 기본 포트 `8080`을 그대로 사용하고, '모든 트래픽 허용', '미인증 호출 허용(보안 검증은 크론 토큰 및 로그인 패스워드로 서버 내부에서 처리)'을 체크 후 **만들기**를 누릅니다.

### STEP 3: 텔레그램 Webhook 자동 등록
서비스가 성공적으로 배포되면 Cloud Run URL이 발급됩니다 (예: `https://tech-sensing-xxxx.a.run.app`).
1. Cloud Run의 환경 변수 중 `WEBHOOK_URL` 값을 이 실제 도메인 URL로 업데이트해 줍니다.
2. 서비스가 재시작하면서 `app/main.py`의 `startup_event`가 트리거되어 텔레그램 서버에 자동으로 웹훅이 등록됩니다.
3. 텔레그램 봇 `@PhilTVTech_bot`으로 들어가서 `/start`를 치면 구독이 활성화되고, 현장 수집 채널 작동이 시작됩니다.

### STEP 4: Cloud Scheduler로 아침 10시 크론 잡 등록
매일 필리핀 시간 기준 아침 10시에 보고서 자동 발송 트리거를 걸어줍니다.
1. GCP **Cloud Scheduler** 콘솔로 이동하여 **작업 만들기**를 클릭합니다.
2. **이름**: `daily-tv-sensing-report`
3. **빈도**: `0 10 * * *` (매일 10시)
4. **시간대**: `Asia/Manila` (필리핀 시간대)
5. **대상**: `HTTP`
6. **URL**: `https://{본인의-Cloud-Run-도메인}/cron/send-report`
7. **HTTP 메서드**: `POST` (또는 GET)
8. **HTTP 헤더 추가**:
   * 이름: `X-Cron-Token`
   * 값: `본인이 지정한 CRON_SECRET_TOKEN 값`
9. **만들기**를 클릭하여 등록 완료합니다.
