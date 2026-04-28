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


def send_verification_code(to_email: str, code: str, expires_minutes: int = 10) -> None:
    """이메일 인증코드 발송. 실패 시 예외 raise."""
    cfg = _config()
    if not cfg["user"] or not cfg["password"]:
        raise RuntimeError(
            "SMTP_USER / SMTP_PASSWORD 환경변수가 설정되어 있지 않습니다."
        )

    body = (
        "BoonPick 회원가입 인증코드입니다.\n\n"
        f"인증코드: {code}\n\n"
        f"이 코드는 {expires_minutes}분 동안 유효합니다.\n"
        "본인이 요청하지 않았다면 이 메일을 무시해주세요."
    )
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = "[BoonPick] 이메일 인증코드"
    msg["From"] = formataddr((cfg["from_name"], cfg["from_email"]))
    msg["To"] = to_email

    with smtplib.SMTP(cfg["host"], cfg["port"], timeout=15) as s:
        s.starttls()
        s.login(cfg["user"], cfg["password"])
        s.send_message(msg)
    logger.info("verification code sent to %s", to_email)
