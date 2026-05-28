import requests
import logging
from app.config import config
from app.database import db

logger = logging.getLogger("PhilTVTech.Bot")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"

def send_message(chat_id: str, text: str) -> bool:
    """지정된 Chat ID로 텔레그램 메시지를 발송합니다 (HTML 파싱 모드)"""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning(f"[메시지 발송 생략 (토큰 없음)] Chat ID: {chat_id}, 내용: {text[:30]}...")
        return False
        
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if response.status_code == 200 and res_data.get("ok"):
            logger.info(f"텔레그램 메시지 발송 성공 -> Chat ID: {chat_id}")
            return True
        else:
            logger.error(f"텔레그램 API 오류: {res_data.get('description')} (코드: {response.status_code})")
            return False
    except Exception as e:
        logger.error(f"텔레그램 메시지 발송 실패 (네트워크 오류): {str(e)}")
        return False

def broadcast_report(report_text: str) -> int:
    """모든 등록된 구독자에게 인사이트 리포트를 발송합니다"""
    subscribers = db.get_subscribers()
    if not subscribers:
        logger.warning("구독자가 등록되어 있지 않습니다. 기본 TELEGRAM_CHAT_ID로 발송을 시도합니다.")
        if config.TELEGRAM_CHAT_ID:
            subscribers = [str(config.TELEGRAM_CHAT_ID)]
        else:
            logger.error("발송 대상 구독자 정보 및 기본 TELEGRAM_CHAT_ID가 없습니다.")
            return 0
            
    success_count = 0
    for chat_id in subscribers:
        if send_message(chat_id, report_text):
            success_count += 1
            
    logger.info(f"리포트 브로드캐스트 완료: 총 {len(subscribers)}명 중 {success_count}명 전송 성공")
    return success_count

def set_telegram_webhook(webhook_url: str) -> bool:
    """텔레그램 웹훅 URL을 등록합니다"""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN이 없어서 웹훅 설정을 스킵합니다.")
        return False
        
    url = f"{TELEGRAM_API_URL}/setWebhook"
    payload = {
        "url": webhook_url,
        "allowed_updates": ["message"]
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        res_data = response.json()
        if response.status_code == 200 and res_data.get("ok"):
            logger.info(f"텔레그램 웹훅 등록 성공 -> {webhook_url}")
            return True
        else:
            logger.error(f"텔레그램 웹훅 등록 실패: {res_data.get('description')}")
            return False
    except Exception as e:
        logger.error(f"텔레그램 웹훅 등록 에러: {str(e)}")
        return False

def handle_telegram_update(update: dict) -> None:
    """텔레그램으로부터 수신된 웹훅 데이터를 처리합니다"""
    message = update.get("message")
    if not message:
        return
        
    chat = message.get("chat", {})
    chat_id = str(chat.get("id"))
    text = message.get("text", "").strip()
    from_user = message.get("from", {})
    username = from_user.get("username", "")
    first_name = from_user.get("first_name", "Anonymous")
    author_name = f"{first_name} (@{username})" if username else first_name
    
    # 1. 명령어 처리 (/start, /subscribe, /stop, /unsubscribe)
    if text.startswith("/start") or text.startswith("/subscribe"):
        db.add_subscriber(chat_id)
        welcome_msg = (
            "✨ <b>PhilTVTech_bot 구독을 환영합니다!</b> ✨\n\n"
            "삼성전자 TV사업부 필리핀 주재원 및 현장 센싱 모니터링 시스템입니다.\n"
            "매일 아침 10시에 필리핀 현지의 따끈따끈한 테크 소식과 인사이트 3가지를 정리하여 전송해 드립니다.\n\n"
            "💡 <i>이 채팅방에 현장의 경쟁사 소식, 매장 사진(설명 포함), 현지 리뷰 및 사용자 피드백 등을 텍스트로 남겨주시면 리포트 분석에 실시간 반영됩니다.</i>\n\n"
            "• 구독 해지: /unsubscribe 또는 /stop"
        )
        send_message(chat_id, welcome_msg)
        return
        
    elif text.startswith("/stop") or text.startswith("/unsubscribe"):
        db.remove_subscriber(chat_id)
        goodbye_msg = "📴 <b>PhilTVTech_bot 구독이 해지되었습니다.</b>\n언제든지 다시 /start를 입력하여 구독하실 수 있습니다."
        send_message(chat_id, goodbye_msg)
        return
        
    # 2. 사진 메시지 처리 (설명이 캡션으로 올 경우 함께 수집)
    photo = message.get("photo")
    caption = message.get("caption", "").strip()
    
    if photo:
        note_content = f"[현장 사진 수신] {caption}".strip()
        db.save_sensing_note(
            text=note_content,
            source="telegram_photo",
            author=author_name
        )
        feedback_msg = "📸 <b>현장 사진이 성공적으로 센싱 데이터베이스에 등록되었습니다.</b>\n인사이트 리포트 생성 시 반영하겠습니다. 감사합니다!"
        send_message(chat_id, feedback_msg)
        return
        
    # 3. 일반 텍스트 입력 처리 -> 센싱 노트 데이터베이스에 저장
    if text:
        db.save_sensing_note(
            text=text,
            source="telegram",
            author=author_name
        )
        feedback_msg = "📝 <b>새로운 현장 센싱 정보가 성공적으로 등록되었습니다.</b>\n매일 아침 10시 보고서 생성 시 반영됩니다. 현장의 소중한 피드백 감사합니다!"
        send_message(chat_id, feedback_msg)
