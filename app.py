import streamlit as st
import os
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="내돈내산 블로그 자동 포스팅",
    page_icon="✍️",
    layout="wide",
)

def check_env():
    missing = []
    if not os.getenv("ANTHROPIC_API_KEY"):
        missing.append("ANTHROPIC_API_KEY")
    if not os.getenv("NAVER_ID"):
        missing.append("NAVER_ID")
    if not os.getenv("NAVER_PW"):
        missing.append("NAVER_PW")
    if not os.getenv("NAVER_BLOG_ID"):
        missing.append("NAVER_BLOG_ID")
    return missing


def _do_post(title: str, content: str, images: list):
    from modules.naver_poster import post_to_naver_blog
    naver_id = os.getenv("NAVER_ID")
    naver_pw = os.getenv("NAVER_PW")
    naver_blog_id = os.getenv("NAVER_BLOG_ID")
    with st.spinner("네이버 블로그에 포스팅 중... (브라우저가 자동으로 열립니다)"):
        result = post_to_naver_blog(
            title=title or "블로그 포스팅",
            content=content,
            images=images,
            naver_id=naver_id,
            naver_pw=naver_pw,
            naver_blog_id=naver_blog_id,
        )
    if result["success"]:
        st.success(f"✅ 포스팅 완료! 블로그 URL: {result['url']}")
        st.balloons()
    else:
        st.error(f"포스팅 실패: {result['error']}")
        st.info("'저장' 버튼으로 텍스트 저장 후 직접 붙여넣기 하세요.")


st.title("✍️ 내돈내산 블로그 자동 포스팅")
st.caption("사진 + 업체 정보 → AI 후기 작성 → 네이버 블로그 자동 게시")

missing_keys = check_env()
if missing_keys:
    st.warning(
        f"⚠️ `.env` 파일에 다음 항목을 설정해주세요: `{'`, `'.join(missing_keys)}`\n\n"
        "`.env.example` 파일을 복사해서 `.env`로 만든 뒤 값을 채워주세요.",
        icon="⚠️",
    )

with st.sidebar:
    st.header("⚙️ AI 포스팅 옵션")
    post_style = st.selectbox(
        "스타일",
        ["내돈내산 솔직 후기", "맛집 탐방 일지", "제품 사용 후기"],
    )
    include_rating = st.checkbox("별점 포함", value=True)
    include_nearby = st.checkbox("주변 여행 및 맛집 포함", value=False)
    include_pros_cons = st.checkbox("장단점 분석 포함", value=True)
    include_seo_keywords = st.checkbox("SEO 키워드 (#태그) 포함", value=True)
    st.divider()
    st.caption("📌 사용 방법\n1. 사진 업로드\n2. AI 생성 또는 직접 작성\n3. 수정 후 블로그 게시")
    st.divider()
    st.caption("🔐 네이버 로그인")
    cookie_exists = os.path.exists(
        os.path.join(os.path.dirname(__file__), "naver_cookies.json")
    )
    if cookie_exists:
        st.success("로그인 세션 저장됨")
        if st.button("로그인 초기화", use_container_width=True):
            from modules.naver_poster import delete_saved_cookies
            delete_saved_cookies()
            st.rerun()
    else:
        st.info("첫 포스팅 시 브라우저에서\n직접 로그인해주세요")

col1, col2 = st.columns([1, 1], gap="large")

# ── 왼쪽: 사진 & 업체 정보 ──────────────────────────────
with col1:
    st.subheader("1️⃣ 사진 & 업체 정보")

    uploaded_files = st.file_uploader(
        "사진 업로드 (최대 10장, JPG/PNG)",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="photo_upload",
    )

    if uploaded_files:
        preview_cols = st.columns(min(len(uploaded_files), 4))
        for i, file in enumerate(uploaded_files[:4]):
            with preview_cols[i]:
                st.image(file, use_container_width=True)
        if len(uploaded_files) > 4:
            st.caption(f"외 {len(uploaded_files) - 4}장 더 업로드됨")

    business_name = st.text_input(
        "업체명",
        placeholder="예: 스타벅스 강남점",
    )
    website_url = st.text_input(
        "홈페이지 또는 네이버 플레이스 URL",
        placeholder="https://place.naver.com/...",
    )
    personal_notes = st.text_area(
        "개인 메모 (선택)",
        placeholder="기억에 남는 점, 추천 메뉴, 주차 여부 등",
        height=90,
    )

    generate_btn = st.button(
        "🤖 AI로 포스팅 자동 생성",
        type="primary",
        use_container_width=True,
        disabled=bool(missing_keys),
    )

    if generate_btn:
        if not uploaded_files:
            st.error("사진을 최소 1장 업로드해주세요.")
        elif not business_name:
            st.error("업체명을 입력해주세요.")
        else:
            from modules.image_analyzer import analyze_images
            from modules.web_scraper import scrape_business_info
            from modules.post_generator import generate_blog_post

            with st.status("AI가 작업 중입니다...", expanded=True) as status:
                st.write("📸 사진 분석 중...")
                image_analysis = analyze_images(uploaded_files)
                st.write("✅ 사진 분석 완료")

                business_info = {}
                if website_url:
                    st.write("🌐 업체 정보 수집 중...")
                    business_info = scrape_business_info(website_url)
                    if business_info.get("error"):
                        st.write(f"⚠️ 홈페이지 수집 부분 실패: {business_info['error']}")
                    else:
                        st.write("✅ 업체 정보 수집 완료")

                st.write("✍️ 인플루언서 스타일 포스팅 작성 중...")
                blog_post = generate_blog_post(
                    image_analysis=image_analysis,
                    business_name=business_name,
                    business_info=business_info,
                    personal_notes=personal_notes,
                    style=post_style,
                    include_rating=include_rating,
                    include_nearby=include_nearby,
                    include_pros_cons=include_pros_cons,
                    include_seo_keywords=include_seo_keywords,
                )
                st.write("✅ 포스팅 완성!")
                status.update(label="완료!", state="complete")

            st.session_state.blog_post = blog_post
            st.session_state.post_title = business_name + " 솔직 후기"
            st.session_state.uploaded_files = uploaded_files
            # key= 위젯은 value=를 무시하므로 세션 상태에 직접 주입
            st.session_state.ai_title = business_name + " 솔직 후기"
            st.session_state.ai_editor = blog_post
            st.rerun()

# ── 오른쪽: 포스팅 편집기 (항상 표시) ────────────────────
with col2:
    st.subheader("2️⃣ 포스팅 편집기")

    tab_ai, tab_manual = st.tabs(["🤖 AI 생성 결과", "✏️ 직접 작성 / 붙여넣기"])

    # ── AI 생성 탭 ──
    with tab_ai:
        ai_content = st.session_state.get("blog_post", "")
        ai_title = st.session_state.get("post_title", business_name + " 솔직 후기" if business_name else "")

        if not ai_content:
            st.info("왼쪽에서 정보를 입력하고 **AI로 포스팅 자동 생성** 버튼을 누르면 여기에 결과가 나타납니다.")

        ai_title_input = st.text_input(
            "제목",
            value=ai_title,
            key="ai_title",
            placeholder="포스팅 제목을 입력하세요",
        )
        ai_edited = st.text_area(
            "내용 (수정 가능)",
            value=ai_content,
            height=420,
            key="ai_editor",
            placeholder="AI 생성 결과가 여기에 표시됩니다. 직접 수정도 가능합니다.",
        )

        col_a1, col_a2, col_a3 = st.columns(3)
        with col_a1:
            if ai_edited:
                st.download_button(
                    "💾 저장",
                    data=ai_edited,
                    file_name=f"{ai_title_input or '포스팅'}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
        with col_a2:
            if st.button("🗑️ 초기화", key="ai_clear", use_container_width=True):
                st.session_state.blog_post = ""
                st.session_state.post_title = ""
                st.rerun()
        with col_a3:
            ai_post_btn = st.button(
                "📤 블로그 게시",
                type="primary",
                key="ai_post_btn",
                use_container_width=True,
                disabled=bool(missing_keys) or not ai_edited,
            )

        if ai_post_btn and ai_edited:
            _do_post(ai_title_input, ai_edited, st.session_state.get("uploaded_files", []))

        # ── 포스팅 미리보기 (텍스트 + 이미지) ────────────────────
        saved_files = st.session_state.get("uploaded_files", [])
        if ai_edited and saved_files:
            with st.expander(f"📖 포스팅 미리보기 (이미지 {len(saved_files)}장 포함)", expanded=False):
                if ai_title_input:
                    st.markdown(f"## {ai_title_input}")
                    st.divider()

                # 이미지를 맨위 / 중간 / 아래 세 위치에 배치
                import re as _re
                paragraphs = [p.strip() for p in _re.split(r'\n{2,}', ai_edited) if p.strip()]
                n = len(saved_files)
                if n == 0:
                    top_f, mid_f, bot_f = [], [], []
                elif n == 1:
                    top_f, mid_f, bot_f = saved_files[:1], [], []
                elif n == 2:
                    top_f, mid_f, bot_f = saved_files[:1], [], saved_files[1:]
                else:
                    n_top = (n + 2) // 3
                    n_mid = (n + 1) // 3
                    top_f = saved_files[:n_top]
                    mid_f = saved_files[n_top:n_top + n_mid]
                    bot_f = saved_files[n_top + n_mid:]

                mid_idx = max(len(paragraphs) // 2, 1)

                # 맨위 이미지
                for f in top_f:
                    st.image(f, use_container_width=True)

                # 본문 + 중간 이미지
                for i, para in enumerate(paragraphs):
                    st.markdown(para)
                    if i == mid_idx - 1 and mid_f:
                        for f in mid_f:
                            st.image(f, use_container_width=True)

                # 아래 이미지
                for f in bot_f:
                    st.image(f, use_container_width=True)

    # ── 직접 작성 탭 ──
    with tab_manual:
        st.caption("직접 글을 쓰거나 다른 곳에서 복사한 내용을 붙여넣으세요.")

        manual_title = st.text_input(
            "제목",
            key="manual_title",
            placeholder="포스팅 제목을 입력하세요",
        )
        manual_content = st.text_area(
            "내용",
            height=420,
            key="manual_editor",
            placeholder="여기에 직접 글을 쓰거나 붙여넣기(Ctrl+V) 하세요.\n\nAI 생성 결과를 복사해서 수정하거나, 처음부터 작성할 수 있습니다.",
        )

        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            if manual_content:
                st.download_button(
                    "💾 저장",
                    data=manual_content,
                    file_name=f"{manual_title or '포스팅'}.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
        with col_m2:
            if st.button("📋 AI 내용 복사", key="copy_ai", use_container_width=True):
                if st.session_state.get("blog_post"):
                    st.session_state.manual_editor = st.session_state.blog_post
                    st.session_state.manual_title = st.session_state.get("post_title", "")
                    st.rerun()
                else:
                    st.warning("AI 생성 결과가 없습니다.")
        with col_m3:
            manual_post_btn = st.button(
                "📤 블로그 게시",
                type="primary",
                key="manual_post_btn",
                use_container_width=True,
                disabled=bool(missing_keys) or not manual_content,
            )

        if manual_post_btn and manual_content:
            _do_post(manual_title, manual_content, uploaded_files or [])
