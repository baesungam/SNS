import anthropic
import os


STYLE_GUIDE = {
    "내돈내산 솔직 후기": (
        "직접 돈 내고 다녀온 리얼 후기. 과장 없이 솔직하되 읽는 재미가 있어야 함. "
        "좋은 점은 확실히, 아쉬운 점도 쿨하게 언급. 친구한테 카톡으로 추천해주는 느낌."
    ),
    "맛집 탐방 일지": (
        "음식에 진심인 푸드 블로거 스타일. 첫 한 입의 감동을 생생하게 전달. "
        "비주얼·맛·향·식감을 오감으로 묘사. '이 집 안 오면 손해'라는 확신을 심어줘야 함."
    ),
    "제품 사용 후기": (
        "실제 구매 후 며칠 써본 솔직한 소비자 리뷰. 언박싱 감동, 실사용 경험, "
        "전후 비교까지. '나도 살까 말까' 고민 중인 사람을 설득하는 글."
    ),
}

INFLUENCER_SYSTEM = """당신은 네이버 블로그 팔로워 10만 명을 보유한 라이프스타일 인플루언서입니다.

글쓰기 철학:
- 독자가 첫 문장을 읽자마자 멈출 수 없게 만드는 훅(Hook)으로 시작
- '나도 저기 가고 싶다'는 감정을 유발하는 감성적 묘사
- 정보는 정확하되 딱딱하지 않게 — 친한 친구가 귓속말로 알려주는 느낌
- 군더더기 없는 문장, 리듬감 있는 호흡
- 사진이 눈에 선하게 떠오르는 구체적 묘사
- 솔직함이 신뢰를 만든다 — 단점도 쿨하게 인정
- 독자가 '저장'하고 싶게 만드는 실용 정보 포함
- 마무리는 여운이 남게 — 다음 방문을 기대하게 만들기"""


def generate_blog_post(
    image_analysis: str,
    business_name: str,
    business_info: dict,
    personal_notes: str,
    style: str,
    include_rating: bool,
    include_nearby: bool,
    include_pros_cons: bool,
    include_seo_keywords: bool,
) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    business_context_parts = [f"업체명: {business_name}"]
    if business_info.get("description"):
        business_context_parts.append(f"업체 소개: {business_info['description']}")
    if business_info.get("address"):
        business_context_parts.append(f"주소: {business_info['address']}")
    if business_info.get("phone"):
        business_context_parts.append(f"전화: {business_info['phone']}")
    if business_info.get("hours"):
        business_context_parts.append(f"영업시간: {business_info['hours']}")
    if business_info.get("raw_text"):
        business_context_parts.append(
            f"홈페이지 내용:\n{business_info['raw_text'][:700]}"
        )
    business_context = "\n".join(business_context_parts)

    optional_sections = []
    if include_rating:
        optional_sections.append(
            "⭐ 총평 별점: 5점 만점 별점 + '한 줄로 이 집을 정의한다면?' 형식의 임팩트 있는 총평"
        )
    if include_nearby:
        optional_sections.append(
            "🗺️ [함께 가면 좋은 곳] 섹션: 근처 여행지·맛집·카페 2~3곳을 '코스 짜는 법' 형식으로 소개. "
            "각 장소마다 한 줄 포인트 설명 포함."
        )
    if include_pros_cons:
        optional_sections.append(
            "✅ [찐 장점] 3가지 — 구체적 근거와 함께\n"
            "💡 [알고 가면 좋은 점] 2~3가지 — 단점보다는 '이런 분께는 안 맞을 수도' 톤으로 솔직하게"
        )
    if include_seo_keywords:
        optional_sections.append(
            "🔍 포스팅 맨 마지막 줄에 네이버 검색 최적화 해시태그 15~20개.\n"
            "형식: #키워드1 #키워드2 ...\n"
            "구성: 업체명·지역·업종·메뉴·분위기·방문목적(데이트/혼밥/가족나들이 등)·계절 키워드 포함.\n"
            "실제 네이버에서 많이 검색되는 롱테일 키워드 위주로."
        )

    optional_text = "\n".join(optional_sections) if optional_sections else ""

    prompt = f"""스타일: {STYLE_GUIDE[style]}

아래 정보로 네이버 블로그 포스팅을 작성해주세요.

[사진 분석]
{image_analysis}

[업체 정보]
{business_context}

[개인 경험 메모]
{personal_notes if personal_notes else "없음"}

───────────────────────────────
📌 포스팅 구성 가이드

제목 (필수)
- 검색되고 클릭되는 제목: 지역명 + 업체명/업종 + 강력한 수식어
- 예시 형식: "홍대 ○○ 솔직 후기ㅣ줄 서서 먹을 가치 있을까?" / "○○ 가봤더니 진짜였다🔥"
- 40자 이내, 궁금증 유발 또는 결론 선공개 방식

본문 구성
1. 🪝 훅 오프닝 (2~3줄)
   - 독자가 공감할 상황이나 질문으로 시작
   - 예: "솔직히 기대 안 했어요. 그냥 근처니까 들어간 거였는데..."

2. 📍 방문 스토리
   - 언제, 누구와, 어떤 이유로 — 독자가 같이 온 느낌

3. 🏠 첫인상 & 분위기
   - 사진 묘사를 살려서 눈에 그려지게

4. 🍽️ 핵심 경험 (음식/제품/서비스 상세)
   - 오감 묘사, 가격 대비 만족도, 놀랐던 포인트

5. {optional_text if optional_text else "💬 총평 & 추천 대상"}

6. 🔚 마무리
   - 재방문 의사 + "이런 분께 추천" + 따뜻한 마무리 한 줄

───────────────────────────────
작성 원칙:
- 분량: 1200~1800자 (넉넉하게, 정보량 풍부하게)
- 소제목은 ## 사용, 이모지로 섹션 구분
- 문장은 짧고 리드미컬하게 (한 문장 최대 40자)
- 줄바꿈 적극 활용 — 읽기 편한 레이아웃
- 구어체 자연스럽게 (존댓말 유지하되 딱딱하지 않게)
- "협찬", "광고", "제공" 절대 금지
- 독자가 저장 버튼 누르게 만드는 실용 정보 1개 이상 포함

지금 바로 완성된 포스팅을 작성해주세요:"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=3500,
        system=[
            {
                "type": "text",
                "text": INFLUENCER_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": prompt}],
    )

    return response.content[0].text
