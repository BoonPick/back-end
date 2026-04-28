"""
Gmail SMTP 메일 발송 유틸.

필요 환경변수:
    SMTP_HOST       기본 smtp.gmail.com
    SMTP_PORT       기본 587 (STARTTLS)
    SMTP_USER       Gmail 주소
    SMTP_PASSWORD   Gmail 앱 비밀번호 (2단계 인증 후 발급)
    MAIL_FROM_NAME  발신자 표시명 (기본 "BoonPick")
    MAIL_FROM_EMAIL 발신 주소 (기본 SMTP_USER)
"""
from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

logger = logging.getLogger(__name__)


def _config() -> dict:
    user = os.getenv("SMTP_USER", "")
    return {
        "host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": user,
        "password": os.getenv("SMTP_PASSWORD", ""),
        "from_name": os.getenv("MAIL_FROM_NAME", "BoonPick"),
        "from_email": os.getenv("MAIL_FROM_EMAIL", user),
    }


def _send(msg: MIMEText, to_email: str) -> None:
    cfg = _config()
    if not cfg["user"] or not cfg["password"]:
        raise RuntimeError(
            "SMTP_USER / SMTP_PASSWORD 환경변수가 설정되어 있지 않습니다."
        )
    msg["From"] = formataddr((cfg["from_name"], cfg["from_email"]))
    msg["To"] = to_email
    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as s:
        s.starttls()
        s.login(cfg["user"], cfg["password"])
        s.send_message(msg)


def send_verification_code(to_email: str, code: str, expires_minutes: int = 10) -> None:
    """이메일 인증코드 발송. 실패 시 예외 raise."""
    body = (
        "BoonPick 회원가입 인증코드입니다.\n\n"
        f"인증코드: {code}\n\n"
        f"이 코드는 {expires_minutes}분 동안 유효합니다.\n"
        "본인이 요청하지 않았다면 이 메일을 무시해주세요."
    )
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = "[BoonPick] 이메일 인증코드"
    _send(msg, to_email)
    logger.info("verification code sent to %s", to_email)


def send_notification_email(to_email: str, items: list[dict]) -> None:
    """
    새로 올라온 매칭 게시물 목록을 한 통의 메일로 발송.
    items: [{title, category_label, source, url, summary, score(optional)}, ...]
    """
    if not items:
        return

    lines = ["BoonPick에서 회원님 조건과 일치하는 새 게시물이 도착했습니다.\n"]
    for it in items:
        score_str = (
            f" (매칭 {it['score']}%)" if it.get("score") is not None else ""
        )
        lines.append(
            f"[{it.get('category_label', '')}] {it.get('title', '')}{score_str}\n"
            f"- 출처: {it.get('source', '')}\n"
            f"- 링크: {it.get('url', '')}\n"
            f"- 요약: {it.get('summary', '')}\n"
        )
    lines.append("\n알림 설정 변경: 사이트의 [알림 설정]에서 가능합니다.")

    msg = MIMEText("\n".join(lines), _charset="utf-8")
    msg["Subject"] = f"[BoonPick] 새 게시물 알림 ({len(items)}건)"
    _send(msg, to_email)
    logger.info("notification email sent to %s (%d items)", to_email, len(items))
