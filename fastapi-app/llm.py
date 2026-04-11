import os
import json


SYSTEM_PROMPT = "당신은 대학생에게 학교 공지, 장학금, 취업 정보를 추천하는 AI입니다. JSON으로만 응답하세요."


def _build_user_prompt(keywords: list[str], title: str, category: str, raw_content: str) -> str:
    content_preview = raw_content[:3000] if raw_content else ""
    return f"""학생의 관심 키워드: {", ".join(keywords)}

아래 게시글을 분석해서 JSON으로 응답하세요.

게시글:
- 제목: {title}
- 카테고리: {category}
- 본문:
{content_preview}

응답 형식 (JSON만, 다른 텍스트 없이):
{{
  "matchScore": <0~100 정수, 키워드와의 관련도>,
  "matchReason": "<2~3문장, 왜 이 학생에게 관련있는지 한국어로>",
  "preparationTips": ["<준비사항1>", "<준비사항2>", "<준비사항3>"]
}}"""


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return json.loads(text)


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
    keywords: list[str],
    title: str,
    category: str,
    raw_content: str,
) -> dict:
    # ANTHROPIC_API_KEY 우선, 없으면 OPENAI_API_KEY
    if os.getenv("ANTHROPIC_API_KEY"):
        call_fn = _call_anthropic
    elif os.getenv("OPENAI_API_KEY"):
        call_fn = _call_openai
    else:
        return _fallback(keywords, title)

    prompt = _build_user_prompt(keywords, title, category, raw_content)

    try:
        text = call_fn(prompt)
        return _parse_json(text)
    except Exception as e:
        print(f"LLM error: {e}")
        return _fallback(keywords, title)


def _fallback(keywords: list[str], title: str) -> dict:
    matched = [kw for kw in keywords if kw.lower() in title.lower()]
    score = min(100, len(matched) * 30 + 20) if matched else 10
    return {
        "matchScore": score,
        "matchReason": f"키워드 '{', '.join(matched or keywords[:2])}'와 관련된 게시글입니다."
        if matched
        else "키워드와 직접적으로 일치하는 내용이 적습니다.",
        "preparationTips": [
            "게시글 내용을 자세히 확인해보세요.",
            "관련 일정과 마감기한을 체크하세요.",
            "필요한 서류를 미리 준비하세요.",
        ],
    }
