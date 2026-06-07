import os
import json
from datetime import datetime
from xml.sax.saxutils import escape as _xml_escape


# 시스템 프롬프트: 역할 + 평가 원칙 + 출력 규칙을 명시.
SYSTEM_PROMPT = (
    "당신은 대학생의 진로·학업을 돕는 정보 큐레이션 AI입니다. "
    "학생의 관심 키워드를 기준으로 학교 공지·장학금·채용 정보가 그 학생에게 "
    "얼마나 적합한지 평가하고, 구체적인 매칭 점수와 준비 가이드를 제시합니다.\n"
    "규칙:\n"
    "- 항상 한국어로 답합니다.\n"
    "- 게시글에 없는 내용을 사실처럼 단정하지 말고, 일반적 조언은 그 사실을 드러냅니다.\n"
    "- 점수는 근거에 기반해 보수적으로 매깁니다.\n"
    "- 출력은 지정된 JSON 객체 하나만 반환하고, 그 외 설명·코드펜스는 절대 포함하지 않습니다."
)


# 출력 JSON 스키마(프롬프트에 그대로 삽입). 들여쓰기는 모델 가독성용.
_OUTPUT_SCHEMA = """{
  "matchScore": <0~100 정수, 아래 세부 점수를 종합한 최종 적합도>,
  "matchLevel": "<매우 적합 | 적합 | 보통 | 낮음 중 하나>",
  "matchReason": "<2~3문장. 왜 이 학생에게 (안)맞는지 한국어로>",
  "scoreBreakdown": [
    {"label": "키워드 관련성", "score": <0~100>, "comment": "<한 문장 근거>"},
    {"label": "분야 적합도",   "score": <0~100>, "comment": "<한 문장 근거>"},
    {"label": "시기 적절성",   "score": <0~100>, "comment": "<한 문장 근거>"},
    {"label": "기회 가치",     "score": <0~100>, "comment": "<한 문장 근거>"}
  ],
  "matchedKeywords": ["<게시글과 직접 맞닿는 관심 키워드>"],
  "missingKeywords": ["<관심 키워드 중 게시글에서 다루지 않는 것>"],
  "preparationTips": ["<준비해야 할 것을 한 문장씩, 3~5개>"],
  "recommendedActions": ["<지금 바로 하면 좋을 행동을 한 문장씩, 2~4개>"],
  "deadlineNote": "<마감/시급성 한 줄 요약. 본문에 단서가 없으면 null>"
}"""


def _build_job_detail_xml(
    employment=None,
    work_type=None,
    duty=None,
    deadline=None,
    is_always_open=None,
) -> str:
    """채용 상세(있을 때만) 를 XML 블록으로. 없으면 빈 문자열."""
    rows = []
    if employment:
        rows.append(f"  <employment>{_xml_escape(str(employment))}</employment>")
    if work_type:
        rows.append(f"  <work_type>{_xml_escape(str(work_type))}</work_type>")
    if duty:
        rows.append(f"  <duty>{_xml_escape(str(duty))}</duty>")
    if is_always_open:
        rows.append("  <deadline>상시 모집 (마감 없음)</deadline>")
    elif deadline:
        rows.append(f"  <deadline>{_xml_escape(str(deadline))}</deadline>")
    if not rows:
        return ""
    return "\n<job_detail>\n" + "\n".join(rows) + "\n</job_detail>\n"


def _build_user_prompt(
    keywords: list,
    title: str,
    category: str,
    raw_content: str,
    employment=None,
    work_type=None,
    duty=None,
    deadline=None,
    is_always_open=None,
) -> str:
    """관심 키워드 + 게시글을 XML 로 구조화한 user 메시지를 만든다.

    입력은 XML 태그로 감싸 모델이 경계를 명확히 인식하게 하고,
    출력은 파싱 안정성을 위해 JSON 한 객체로만 받는다.
    채용 상세(마감/고용형태 등)가 있으면 <job_detail> 블록으로 함께 전달해
    '시기 적절성' 평가와 deadlineNote 산출의 근거로 쓰게 한다.
    """
    content_preview = (raw_content or "")[:3000]
    kw_text = ", ".join(keywords) if keywords else "(설정된 키워드 없음)"
    job_detail = _build_job_detail_xml(
        employment, work_type, duty, deadline, is_always_open
    )

    return f"""<student>
  <interest_keywords>{_xml_escape(kw_text)}</interest_keywords>
</student>

<posting category="{_xml_escape(category or "")}">
  <title>{_xml_escape(title or "")}</title>
  <body>{_xml_escape(content_preview)}</body>
</posting>
{job_detail}
<task>
학생의 관심 키워드와 위 게시글의 적합도를 평가하세요.
1) 관심 키워드를 게시글 내용과 대조해 matched/missing 으로 분류합니다.
2) 아래 4개 축으로 각각 0~100 세부 점수를 매기고, 그 근거를 한 문장으로 답니다.
3) 세부 점수를 종합해 최종 matchScore(0~100)와 matchLevel 을 정합니다.
4) 이 학생이 실제로 무엇을 준비하고(preparationTips), 지금 당장 무슨 행동을 하면
   좋을지(recommendedActions) 게시글 맥락에 맞춰 구체적으로 제안합니다.
5) 마감·일정·시급성 단서가 본문에 있으면 deadlineNote 로 요약하고, 없으면 null.
</task>

<scoring_axes>
- 키워드 관련성: 관심 키워드와 게시글 내용이 얼마나 직접 맞닿아 있는가.
- 분야 적합도: 게시글의 카테고리/분야가 학생 관심사와 부합하는가.
- 시기 적절성: 마감·모집 일정상 지금 준비/지원하기에 적절한가. (단서 없으면 50 기준)
- 기회 가치: 참여 시 학생이 얻는 성장·혜택·커리어 가치의 크기.
</scoring_axes>

<output_format>
정확히 아래 형태의 JSON 객체 하나만 출력하세요. 다른 텍스트나 코드펜스는 금지합니다.
{_OUTPUT_SCHEMA}
</output_format>"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


# ── 응답 정규화 ──────────────────────────────────────────────────────
_VALID_LEVELS = ("매우 적합", "적합", "보통", "낮음")


def _level_from_score(score: int) -> str:
    if score >= 80:
        return "매우 적합"
    if score >= 60:
        return "적합"
    if score >= 35:
        return "보통"
    return "낮음"


def _as_int_score(v, default: int = 0) -> int:
    try:
        return max(0, min(100, int(round(float(v)))))
    except (TypeError, ValueError):
        return default


def _as_str_list(v) -> list:
    if isinstance(v, list):
        return [str(x).strip() for x in v if str(x).strip()]
    if isinstance(v, str) and v.strip():
        return [v.strip()]
    return []


def _normalize(result: dict, keywords: list) -> dict:
    """LLM 출력이 일부 빠지거나 타입이 어긋나도 main 의 Recommendation 모델에
    바로 들어갈 수 있도록 형태를 보정한다."""
    result = result if isinstance(result, dict) else {}

    score = _as_int_score(result.get("matchScore"), 0)

    level = result.get("matchLevel")
    if level not in _VALID_LEVELS:
        level = _level_from_score(score)

    breakdown = []
    if isinstance(result.get("scoreBreakdown"), list):
        for item in result["scoreBreakdown"]:
            if isinstance(item, dict) and item.get("label"):
                breakdown.append({
                    "label": str(item.get("label")),
                    "score": _as_int_score(item.get("score"), 0),
                    "comment": str(item.get("comment") or ""),
                })

    deadline = result.get("deadlineNote")
    deadline = str(deadline).strip() if deadline not in (None, "", "null") else None

    return {
        "matchScore": score,
        "matchLevel": level,
        "matchReason": str(result.get("matchReason") or "").strip(),
        "scoreBreakdown": breakdown,
        "matchedKeywords": _as_str_list(result.get("matchedKeywords")),
        "missingKeywords": _as_str_list(result.get("missingKeywords")),
        "preparationTips": _as_str_list(result.get("preparationTips")),
        "recommendedActions": _as_str_list(result.get("recommendedActions")),
        "deadlineNote": deadline,
    }


def _call_anthropic(prompt: str) -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_openai(prompt: str) -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        max_tokens=1024,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return response.choices[0].message.content


def get_llm_recommendation(
    keywords: list,
    title: str,
    category: str,
    raw_content: str,
    employment=None,
    work_type=None,
    duty=None,
    deadline=None,
    is_always_open=None,
) -> dict:
    # ANTHROPIC_API_KEY 우선, 없으면 OPENAI_API_KEY
    if os.getenv("ANTHROPIC_API_KEY"):
        call_fn = _call_anthropic
    elif os.getenv("OPENAI_API_KEY"):
        call_fn = _call_openai
    else:
        return _fallback(keywords, title, raw_content, category, deadline, is_always_open)

    prompt = _build_user_prompt(
        keywords, title, category, raw_content,
        employment=employment, work_type=work_type, duty=duty,
        deadline=deadline, is_always_open=is_always_open,
    )

    try:
        text = call_fn(prompt)
        return _normalize(_parse_json(text), keywords)
    except Exception as e:
        print(f"LLM error: {e}")
        return _fallback(keywords, title, raw_content, category, deadline, is_always_open)


_CATEGORY_LABEL = {
    "job": "채용",
    "scholarship": "장학",
    "announcement": "공지",
}


def _deadline_urgency(deadline, is_always_open):
    """마감 정보로 (시기적절성 점수, deadlineNote) 산출.
    가까울수록 '지금 행동' 적절도가 높다. 단서 없으면 (50, None)."""
    if is_always_open:
        return 70, "상시 모집이라 마감 압박은 없지만 일찍 지원할수록 유리합니다."
    if not deadline:
        return 50, None
    try:
        d = datetime.strptime(str(deadline)[:10], "%Y-%m-%d").date()
    except ValueError:
        return 50, None
    days = (d - datetime.now().date()).days
    if days < 0:
        return 5, f"마감일({d})이 이미 지났습니다."
    if days == 0:
        return 100, "오늘 마감입니다. 지금 바로 지원하세요."
    if days <= 7:
        return 95, f"마감 D-{days} ({d}). 서둘러 준비하세요."
    if days <= 30:
        return 75, f"마감 D-{days} ({d}). 지원 준비를 시작하기 좋은 시점입니다."
    return 55, f"마감까지 {days}일 ({d}) 남아 여유가 있습니다."


def _fallback(
    keywords: list,
    title: str,
    raw_content: str = "",
    category: str = "",
    deadline=None,
    is_always_open=None,
) -> dict:
    """LLM 키가 없거나 호출 실패 시의 규칙 기반 대체 응답.
    제목+본문에서 키워드를 매칭하고, 카테고리·마감 정보까지 반영해 4개 축을 채운다."""
    title_l = (title or "").lower()
    hay = (title_l + " " + (raw_content or "").lower())
    matched = [kw for kw in keywords if kw and kw.lower() in hay]
    # 제목 매칭은 본문 매칭보다 신호가 강하므로 점수에 가중.
    in_title = [kw for kw in matched if kw.lower() in title_l]
    missing = [kw for kw in keywords if kw and kw.lower() not in hay]

    # 종합 점수: 제목 일치는 가중치를 더 둔다. (제목 1개 = 50점, 테스트 호환)
    base = len(in_title) * 30 + (len(matched) - len(in_title)) * 15
    score = min(100, base + 20) if matched else 10

    total = len(keywords) or 1
    kw_score = min(100, round(len(matched) / total * 100))
    cat_label = _CATEGORY_LABEL.get(category or "", "")
    fit_score = 60 if matched else 25
    timing_score, deadline_note = _deadline_urgency(deadline, is_always_open)

    if in_title:
        reason = f"관심 키워드 '{', '.join(in_title)}'가 제목과 일치해 관련도가 높습니다."
    elif matched:
        reason = f"관심 키워드 '{', '.join(matched)}'가 본문에서 언급돼 관련이 있습니다."
    else:
        reason = "관심 키워드와 직접 일치하는 내용이 적어 관련도가 낮습니다."

    return {
        "matchScore": score,
        "matchLevel": _level_from_score(score),
        "matchReason": reason,
        "scoreBreakdown": [
            {"label": "키워드 관련성", "score": kw_score,
             "comment": f"관심 키워드 {total}개 중 {len(matched)}개가 글에서 발견됐습니다."},
            {"label": "분야 적합도", "score": fit_score,
             "comment": f"{cat_label or '해당'} 분야 글로, 키워드 일치 여부로만 추정했습니다."},
            {"label": "시기 적절성", "score": timing_score,
             "comment": deadline_note or "마감/일정 단서가 없어 기본값으로 추정했습니다."},
            {"label": "기회 가치", "score": 60 if category == "job" else 50,
             "comment": "AI 분석 없이 카테고리 기준으로 추정한 값입니다."},
        ],
        "matchedKeywords": matched,
        "missingKeywords": missing,
        "preparationTips": [
            "게시글 본문과 첨부 자료를 자세히 확인하세요.",
            "관련 일정과 마감기한을 캘린더에 등록하세요.",
            "필요한 서류나 자격 요건을 미리 준비하세요.",
        ],
        "recommendedActions": [
            "원문 링크를 열어 상세 요건을 확인하세요.",
            "관심 키워드를 더 구체적으로 설정하면 정확한 추천을 받을 수 있습니다.",
        ],
        "deadlineNote": deadline_note,
    }
