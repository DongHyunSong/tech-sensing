import os
import logging
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Query, Header
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from datetime import datetime, timezone

from app.config import config
from app.database import db
from app.bot import handle_telegram_update, broadcast_report, set_telegram_webhook
from app.analyzer import generate_sensing_report

logger = logging.getLogger("PhilTVTech.Main")

# FastAPI 앱 생성
app = FastAPI(
    title="PhilTVTech Sensing Service",
    description="삼성전자 TV사업부 필리핀 주재원용 현지 시장/기술 동향 센싱 봇 및 대시보드",
    version="1.0.0"
)

# 정적 파일 및 템플릿 마운트
# 폴더 생성 보장
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(__file__), "templates"), exist_ok=True)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


# --- 보안 및 인증 헬퍼 함수 ---
def is_authenticated(request: Request) -> bool:
    """간단한 쿠키 기반 대시보드 세션 인증 검사"""
    session = request.cookies.get("philtvtech_session")
    # 간단한 토큰 인증 (실제 프로덕션 환경에선 해시값 검증을 권장하나 가벼운 데모/단일 주재원 관리용으로 구현)
    return session == "authenticated_active"


# --- 웹 대시보드 라우터 ---

@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """메인 대시보드 페이지 (인증 실패 시 로그인 화면 렌더링)"""
    if not is_authenticated(request):
        # 로그인 템플릿 렌더링 (dashboard.html 안에서 로그인 모달/폼으로 표시하도록 통합 설계 가능)
        return templates.TemplateResponse("dashboard.html", {
            "request": request, 
            "authenticated": False,
            "error": None,
            "project_name": "PhilTVTech Sensing Center"
        })
        
    # 최근 7일간 센싱 데이터
    recent_notes = db.get_sensing_notes_since(7)
    # 최근 발송된 리포트
    recent_reports = db.get_recent_reports(5)
    # 구독자 수
    subscribers_count = len(db.get_subscribers())
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "authenticated": True,
        "notes": recent_notes,
        "reports": recent_reports,
        "subscribers_count": subscribers_count,
        "project_name": "PhilTVTech Sensing Center"
    })


@app.post("/login")
async def post_login(password: str = Form(...)):
    """웹 대시보드 로그인 처리"""
    if password == config.WEB_PASSWORD:
        response = RedirectResponse(url="/", status_code=303)
        # 1일간 유효한 간단한 인증 세션 쿠키 설정
        response.set_cookie(
            key="philtvtech_session", 
            value="authenticated_active", 
            max_age=86400,
            httponly=True,
            samesite="lax"
        )
        logger.info("대시보드 로그인 성공.")
        return response
    else:
        logger.warning("대시보드 로그인 실패: 비밀번호 오류.")
        return templates.TemplateResponse("dashboard.html", {
            "request": None,  # Jinja2에서 사용하지 않을 수도 있어 빈 전달 가능, 또는 가상 리퀘스트 매핑
            "authenticated": False,
            "error": "잘못된 접근 비밀번호입니다. 다시 입력해 주세요.",
            "project_name": "PhilTVTech Sensing Center"
        })


@app.get("/logout")
async def get_logout():
    """로그아웃 처리"""
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("philtvtech_session")
    logger.info("대시보드 로그아웃 완료.")
    return response


# --- API 및 백엔드 서비스 라우터 ---

@app.post("/api/notes")
async def create_note(
    request: Request,
    text: str = Form(...),
    source: str = Form("web_dashboard"),
    author: str = Form("주재원(Web)")
):
    """대시보드에서 수동으로 신규 센싱 노트를 등록하는 API"""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="인증되지 않은 사용자입니다.")
        
    if not text.strip():
        return JSONResponse(status_code=400, content={"success": False, "message": "내용을 입력해 주세요."})
        
    success = db.save_sensing_note(
        text=text.strip(),
        source=source,
        author=author
    )
    
    if success:
        return RedirectResponse(url="/", status_code=303)
    else:
        return JSONResponse(status_code=500, content={"success": False, "message": "데이터베이스 저장 실패."})


@app.post("/webhook")
async def telegram_webhook(request: Request):
    """텔레그램 봇 Webhook 수신 엔드포인트"""
    try:
        update = await request.json()
        logger.info(f"텔레그램 웹훅 업데이트 수신: {update.get('update_id')}")
        handle_telegram_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"텔레그램 웹훅 처리 중 에러 발생: {str(e)}")
        # 텔레그램 서버에 200 응답을 줘야 재시도를 반복하지 않습니다.
        return {"status": "error", "message": str(e)}


@app.get("/cron/send-report")
@app.post("/cron/send-report")
async def trigger_cron_report(
    request: Request,
    token: str = Query(None),
    x_cron_token: str = Header(None)
):
    """
    Cloud Scheduler 또는 수동으로 인사이트 리포트를 트리거하여 발송하는 엔드포인트.
    보안을 위해 쿼리 파라미터 'token' 또는 헤더 'X-Cron-Token' 값이 설정 파일과 일치해야 작동합니다.
    """
    # 토큰 검증
    provided_token = token or x_cron_token
    if provided_token != config.CRON_SECRET_TOKEN:
        logger.warning("미승인 크론 트리거 요청 거부됨.")
        raise HTTPException(status_code=403, detail="승인되지 않은 크론 토큰입니다.")
        
    logger.info("센싱 리포트 자동 생성 및 발송 크론 태스크를 시작합니다.")
    
    # 1. 최근 7일간의 수집된 원본 데이터 취합
    notes = db.get_sensing_notes_since(7)
    logger.info(f"취합된 원본 센싱 자료 개수: {len(notes)}개")
    
    # 2. 중복 방지를 위한 최근 발행 리포트 이력 조회
    previous_reports = db.get_recent_reports(5)
    
    # 3. Gemini를 통한 고품질 리포트 생성
    report_text = generate_sensing_report(notes, previous_reports)
    
    # 4. 생성된 리포트 아카이브 저장
    db.save_report(report_text)
    
    # 5. 모든 구독자에게 브로드캐스트 발송
    sent_count = broadcast_report(report_text)
    
    return {
        "success": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "notes_analyzed_count": len(notes),
        "subscribers_sent_count": sent_count,
        "report_preview": report_text[:100] + "..."
    }


# --- 애플리케이션 시작 이벤트 ---

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 환경 유효성 검사 및 웹훅 자동 등록 시도"""
    # 환경변수 로딩 체크
    config.validate()
    
    # 만약 WEBHOOK_URL이 환경 변수에 별도로 정의되어 있다면 자동으로 텔레그램 웹훅 등록 시도
    webhook_url = os.getenv("WEBHOOK_URL", "")
    if webhook_url and config.TELEGRAM_BOT_TOKEN:
        logger.info(f"자동 웹훅 등록을 시도합니다. URL: {webhook_url}/webhook")
        # 텔레그램 웹훅 등록 API 호출
        set_telegram_webhook(f"{webhook_url}/webhook")
