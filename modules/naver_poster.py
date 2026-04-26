import asyncio
import json
import os
import re
import tempfile
import threading
import traceback
from playwright.async_api import async_playwright

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "naver_post.log")
COOKIE_PATH = os.path.join(os.path.dirname(__file__), "..", "naver_cookies.json")

# 서버 배포 시 환경변수 HEADLESS=true 로 headless 모드 전환
IS_HEADLESS = os.getenv("HEADLESS", "false").lower() == "true"


def _log(msg: str):
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def _strip_markdown(text: str) -> str:
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'^\-{3,}$', '', text, flags=re.MULTILINE)
    text = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def _split_three(lst: list) -> tuple:
    n = len(lst)
    if n == 0: return [], [], []
    if n == 1: return lst[:1], [], []
    if n == 2: return lst[:1], [], lst[1:]
    n_top = (n + 2) // 3
    n_mid = (n + 1) // 3
    return lst[:n_top], lst[n_top:n_top + n_mid], lst[n_top + n_mid:]


async def _save_cookies(context):
    cookies = await context.cookies()
    with open(COOKIE_PATH, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    _log("쿠키 저장")


async def _load_cookies(context):
    if not os.path.exists(COOKIE_PATH):
        return False
    with open(COOKIE_PATH, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    await context.add_cookies(cookies)
    _log("쿠키 로드")
    return True


def _is_logged_in(url: str) -> bool:
    return "nid.naver.com" not in url or "login" not in url


async def _do_manual_login(page) -> bool:
    await page.goto("https://nid.naver.com/nidlogin.login", wait_until="load", timeout=20000)
    _log("수동 로그인 대기...")
    for _ in range(120):
        await page.wait_for_timeout(1000)
        if _is_logged_in(page.url):
            _log(f"로그인 성공: {page.url}")
            return True
    return False


async def _get_editor_frame(page):
    """SE3 contenteditable 있는 프레임 반환 (없으면 page)"""
    for attempt in range(40):
        for fr in page.frames:
            try:
                if not fr.url or fr.url == 'about:blank':
                    continue
                cnt = await fr.evaluate(
                    "() => document.querySelectorAll('[contenteditable=\"true\"]').length"
                )
                if cnt > 0:
                    label = "메인" if fr == page.main_frame else fr.url[:60]
                    _log(f"에디터 프레임 발견: {label} (contenteditable: {cnt})")
                    return page if fr == page.main_frame else fr
            except Exception:
                pass
        await page.wait_for_timeout(500)
        if attempt % 5 == 4:
            _log(f"에디터 대기 중... {attempt+1}/40")
    _log("에디터 프레임 못 찾음 → 메인 페이지 사용")
    return page


async def _screenshot(page, name: str):
    try:
        path = os.path.join(tempfile.gettempdir(), name)
        await page.screenshot(path=path)
        _log(f"스크린샷: {path}")
    except Exception as e:
        _log(f"스크린샷 실패: {e}")


async def _hide_help_panel(page):
    """모든 프레임 도움말 패널 강제 숨김"""
    for fr in page.frames:
        try:
            await fr.evaluate("""() => {
                const p = document.querySelector('.se-help-panel');
                if (p) {
                    p.style.setProperty('display','none','important');
                    const b = p.querySelector('.se-help-panel-close-button,button');
                    if (b) b.click();
                }
            }""")
        except Exception:
            pass
    await page.wait_for_timeout(300)


async def _enter_title(page, frame, title: str):
    """
    제목 필드 입력
    - placeholder가 '제목' 또는 '제목을 입력하세요.' 모두 대응
    - pressSequentially → JS innerText → 마우스 좌표 순으로 시도
    """
    _log(f"=== 제목 입력: {title[:50]} ===")
    title_js = json.dumps(title)

    # 현재 contenteditable 목록 로그 (디버깅)
    try:
        ce_list = await frame.evaluate("""() =>
            Array.from(document.querySelectorAll('[contenteditable="true"]')).map(e => ({
                ph: e.getAttribute('data-placeholder') || '',
                cls: e.className.slice(0, 50),
                parent: (e.parentElement ? e.parentElement.className : '').slice(0, 40),
                top: Math.round(e.getBoundingClientRect().top),
                h: Math.round(e.getBoundingClientRect().height)
            }))
        """)
        _log(f"contenteditable 목록: {json.dumps(ce_list, ensure_ascii=False)}")
    except Exception as e:
        _log(f"contenteditable 로그 실패: {e}")

    # 스크린샷에서 확인된 placeholder = '제목' (앞에 긴 문장 없음)
    title_sels = [
        "div[data-placeholder='제목'][contenteditable='true']",
        "div[data-placeholder='제목을 입력하세요.'][contenteditable='true']",
        "div[data-placeholder='제목을 입력하세요'][contenteditable='true']",
        ".se-documentTitle [contenteditable='true']",
        ".se-title [contenteditable='true']",
        "[class*='documentTitle'][contenteditable='true']",
        "[class*='title-input'][contenteditable='true']",
        ".se-title-input[contenteditable='true']",
    ]

    for target in ([frame] if frame is not page else []) + [page]:
        for sel in title_sels:
            try:
                el = target.locator(sel).first
                if await el.count() == 0:
                    continue

                # ── 방법 1: pressSequentially (SE3 에 가장 자연스러운 입력) ──
                await el.click()
                await page.wait_for_timeout(400)
                await el.press_sequentially(title, delay=40)
                await page.wait_for_timeout(200)
                text_in = await el.inner_text()
                if text_in.strip():
                    _log(f"제목 pressSequentially 성공: {sel} → '{text_in[:30]}'")
                    return

                # ── 방법 2: JS innerText 직접 설정 + input 이벤트 ──
                await target.evaluate(f"""(sel) => {{
                    const el = document.querySelector(sel);
                    if (!el) return;
                    el.focus();
                    el.innerText = {title_js};
                    el.dispatchEvent(new InputEvent('input', {{
                        inputType: 'insertText',
                        data: {title_js},
                        bubbles: true,
                        cancelable: true
                    }}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                }}""", sel)
                await page.wait_for_timeout(200)
                text_in2 = await el.inner_text()
                if text_in2.strip():
                    _log(f"제목 JS innerText 성공: {sel} → '{text_in2[:30]}'")
                    return

            except Exception as ex:
                _log(f"제목 {sel}: {ex}")

    # ── Fallback: 화면 최상위 contenteditable 직접 JS 입력 ──
    try:
        ok = await frame.evaluate(f"""() => {{
            const els = Array.from(document.querySelectorAll('[contenteditable="true"]'))
                .filter(e => {{
                    const r = e.getBoundingClientRect();
                    return r.width > 50 && r.height > 5 && r.top >= 0;
                }})
                .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
            if (!els.length) return false;
            const el = els[0];
            el.focus();
            el.click();
            el.innerText = {title_js};
            el.dispatchEvent(new InputEvent('input', {{
                inputType: 'insertText', data: {title_js}, bubbles: true
            }}));
            return el.innerText.length > 0;
        }}""")
        if ok:
            _log("제목 JS fallback 성공 (최상위 contenteditable)")
            return
    except Exception as e:
        _log(f"제목 JS fallback 실패: {e}")

    # ── 최후 수단: 마우스 좌표 클릭 후 pressSequentially ──
    try:
        info = await frame.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('[contenteditable="true"]'))
                .map(e => { const r = e.getBoundingClientRect(); return {r, e}; })
                .filter(({r}) => r.width > 50 && r.height > 5 && r.top >= 0)
                .sort((a, b) => a.r.top - b.r.top);
            if (!els.length) return null;
            const {r, e} = els[0];
            return {x: Math.round(r.left + r.width/2), y: Math.round(r.top + r.height/2),
                    ph: e.getAttribute('data-placeholder') || '', cls: e.className.slice(0,40)};
        }""")
        _log(f"최상위 좌표: {info}")
        if info:
            await page.mouse.click(info['x'], info['y'])
            await page.wait_for_timeout(400)
            # Ctrl+A 로 기존 내용 지우고 새로 입력
            await page.keyboard.press("Control+a")
            await page.keyboard.type(title, delay=30)
            _log(f"제목 마우스+keyboard.type: ({info['x']}, {info['y']})")
            return
    except Exception as e:
        _log(f"제목 마우스 fallback 실패: {e}")

    _log("제목 입력 모든 전략 실패")


async def _focus_body(page, frame):
    """본문 영역 포커스"""
    body_sels = [
        ".se-content",
        ".se-main-container",
        ".se-content-area",
        ".se-documentArea",
        ".se-document",
        ".se-module-text",
    ]
    for target in ([frame] if frame is not page else []) + [page]:
        for sel in body_sels:
            try:
                el = target.locator(sel).first
                if await el.count() > 0:
                    await el.click()
                    _log(f"본문 포커스: {sel}")
                    return True
            except Exception:
                pass

    # Fallback: 두 번째 contenteditable (첫 번째는 제목)
    try:
        info = await frame.evaluate("""() => {
            const els = Array.from(document.querySelectorAll('[contenteditable="true"]'))
                .map(el => { const r = el.getBoundingClientRect(); return {r}; })
                .filter(({r}) => r.width > 50 && r.height > 5)
                .sort((a, b) => a.r.top - b.r.top);
            if (els.length < 2) return null;
            const r = els[1].r;
            return {x: Math.round(r.left + r.width / 2), y: Math.round(r.top + 20)};
        }""")
        if info:
            await page.mouse.click(info['x'], info['y'])
            _log(f"본문 2번째 contenteditable: {info}")
            return True
    except Exception as e:
        _log(f"본문 fallback 실패: {e}")
    return False


async def _type_line(page, frame, line: str):
    """한 줄 입력: execCommand 우선, 실패 시 keyboard.type"""
    line_js = json.dumps(line)
    try:
        ok = await frame.evaluate(
            f"() => document.execCommand('insertText', false, {line_js})"
        )
        if ok:
            return
    except Exception:
        pass
    await page.keyboard.type(line, delay=5)


async def _insert_image(page, frame, tmp_path: str) -> bool:
    """
    SE3 이미지 삽입
    전략 A: 사진 버튼 → SE3 패널 → 내 PC 버튼 → 파일 선택창
    전략 B: hidden file input 직접 조작
    """
    _log(f"이미지 삽입: {os.path.basename(tmp_path)}")

    # 버튼 목록 로그 (디버깅)
    try:
        btns = await page.evaluate("""() =>
            Array.from(document.querySelectorAll('button,[role="button"]')).slice(0,25).map(b => ({
                t: (b.innerText||b.textContent||'').trim().slice(0,12),
                a: (b.getAttribute('aria-label')||'').slice(0,15),
                c: b.className.slice(0,25)
            }))
        """)
        _log(f"버튼 목록: {btns}")
    except Exception:
        pass

    # ── 전략 A: filechooser 이벤트 리스너 ──
    fc_holder = {"fc": None}

    def on_fc(fc):
        fc_holder["fc"] = fc

    page.on("filechooser", on_fc)

    try:
        photo_sels = [
            "button[aria-label='사진']",
            "button[aria-label='이미지']",
            "button[title='사진']",
            "button[title='이미지']",
            ".se-toolbar-item-image button",
            "[data-name='image'] button",
            "button:has-text('사진')",
        ]

        for target in ([frame] if frame is not page else []) + [page]:
            for sel in photo_sels:
                try:
                    btn = target.locator(sel).first
                    if await btn.count() == 0:
                        continue
                    _log(f"사진 버튼 클릭: {sel}")
                    await btn.click(force=True)
                    await page.wait_for_timeout(1500)

                    # SE3 내부 패널이 열렸으면 "내 PC" 버튼 클릭
                    pc_sels = [
                        "button:has-text('내 컴퓨터')",
                        "button:has-text('내 PC')",
                        "button:has-text('내PC')",
                        "button:has-text('직접 올리기')",
                        "button:has-text('파일 올리기')",
                        "button:has-text('PC에서')",
                        "text=내 컴퓨터에서 올리기",
                        "text=PC에서 올리기",
                        "text=내 컴퓨터",
                    ]
                    for pc_sel in pc_sels:
                        try:
                            pc_btn = page.locator(pc_sel).first
                            if await pc_btn.count() > 0:
                                _log(f"SE3 내PC 버튼: {pc_sel}")
                                await pc_btn.click()
                                await page.wait_for_timeout(1000)
                                break
                        except Exception:
                            pass

                    # filechooser 대기 (최대 4초)
                    for _ in range(40):
                        if fc_holder["fc"]:
                            await fc_holder["fc"].set_files([tmp_path])
                            await page.wait_for_timeout(3500)
                            _log(f"이미지 파일 선택 완료 ({sel})")
                            return True
                        await page.wait_for_timeout(100)

                    _log(f"파일선택창 타임아웃 ({sel})")

                except Exception as ex:
                    _log(f"사진 버튼 {sel} 오류: {ex}")

    finally:
        page.remove_listener("filechooser", on_fc)

    # ── 전략 B: hidden file input 직접 조작 ──
    try:
        for target in ([frame] if frame is not page else []) + [page]:
            fi_list = target.locator("input[type='file']")
            cnt = await fi_list.count()
            if cnt > 0:
                _log(f"file input 직접 조작 ({cnt}개 발견)")
                await fi_list.first.set_input_files([tmp_path])
                await page.wait_for_timeout(3500)
                _log("이미지 file input 성공")
                return True
    except Exception as ex:
        _log(f"file input 전략 실패: {ex}")

    _log("이미지 삽입 실패 (모든 전략)")
    return False


async def _enter_body_with_images(page, frame, text: str, images: list):
    """본문 텍스트 + 이미지 (맨위/중간/아래) 입력"""
    tmp_paths = []
    try:
        for i, file in enumerate(images[:10]):
            file.seek(0)
            suffix = os.path.splitext(getattr(file, "name", f"img_{i}.jpg"))[1] or ".jpg"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
            tmp.write(file.read())
            tmp.close()
            tmp_paths.append(tmp.name)
            file.seek(0)

        top_imgs, mid_imgs, bot_imgs = _split_three(tmp_paths)
        _log(f"이미지 배치 — 위:{len(top_imgs)} 중:{len(mid_imgs)} 아래:{len(bot_imgs)}")

        # 본문 포커스
        await _focus_body(page, frame)
        await page.wait_for_timeout(500)

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        mid_idx = max(len(paragraphs) // 2, 1)

        # 맨위 이미지
        for path in top_imgs:
            ok = await _insert_image(page, frame, path)
            _log(f"위 이미지: {'OK' if ok else 'FAIL'}")
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(300)

        # 본문 + 중간 이미지
        for idx, para in enumerate(paragraphs):
            for line in para.split("\n"):
                if line.strip():
                    await _type_line(page, frame, line)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(8)
            await page.keyboard.press("Enter")

            if idx == mid_idx - 1 and mid_imgs:
                for path in mid_imgs:
                    ok = await _insert_image(page, frame, path)
                    _log(f"중간 이미지: {'OK' if ok else 'FAIL'}")
                    await page.keyboard.press("Enter")
                    await page.wait_for_timeout(300)

        # 아래 이미지
        for path in bot_imgs:
            await page.keyboard.press("Enter")
            ok = await _insert_image(page, frame, path)
            _log(f"아래 이미지: {'OK' if ok else 'FAIL'}")
            await page.wait_for_timeout(300)

        _log("본문+이미지 입력 완료")

    finally:
        for path in tmp_paths:
            try:
                os.unlink(path)
            except Exception:
                pass


async def _select_publish_now(page):
    """발행 패널에서 '지금 발행' 선택 (예약 발행 → 즉시 발행 전환)"""
    _log("지금 발행 옵션 선택 시도")

    # 모든 프레임에서 '지금 발행' 관련 요소 탐색
    for fr in page.frames:
        try:
            result = await fr.evaluate("""() => {
                // radio input / label / span / div 에서 '지금 발행' 텍스트 탐색
                const all = Array.from(document.querySelectorAll(
                    'input[type="radio"], label, span, div, button'
                ));
                const el = all.find(e => {
                    const t = (e.innerText || e.textContent || e.value || '').trim();
                    return t === '지금 발행' || t.includes('지금 발행');
                });
                if (!el) return null;

                // radio 직접 클릭
                if (el.tagName === 'INPUT') {
                    el.checked = true;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                    el.click();
                    return 'INPUT:' + el.id;
                }
                // label 이면 연결 input 도 클릭
                if (el.tagName === 'LABEL') {
                    el.click();
                    const inp = el.control || document.getElementById(el.htmlFor);
                    if (inp) { inp.checked = true; inp.click(); }
                    return 'LABEL:' + el.textContent.trim().slice(0, 20);
                }
                el.click();
                return el.tagName + ':' + el.textContent.trim().slice(0, 20);
            }""")
            if result:
                _log(f"지금 발행 선택 완료: {result}")
                await page.wait_for_timeout(400)
                return True
        except Exception:
            pass

    # Playwright locator 폴백
    for sel in [
        "label:has-text('지금 발행')",
        "span:has-text('지금 발행')",
        "div:has-text('지금 발행')",
        "button:has-text('지금 발행')",
        "text=지금 발행",
    ]:
        try:
            el = page.locator(sel).first
            if await el.count() > 0:
                await el.click()
                _log(f"지금 발행 locator 클릭: {sel}")
                await page.wait_for_timeout(400)
                return True
        except Exception:
            pass

    _log("지금 발행 옵션 못 찾음 (이미 선택됐거나 패널 구조 다름)")
    return False


async def _publish(page) -> bool:
    """발행 3단계: 상단 발행 버튼 → 패널에서 '지금 발행' 선택 → 패널 확인 발행"""
    _log("=== 발행 시작 ===")

    # 1단계: 우측 상단 녹색 '발행' 버튼 클릭 (스크린샷에서 가장 오른쪽 버튼)
    step1 = False
    for fi, fr in enumerate(page.frames):
        try:
            html = await fr.evaluate("""() => {
                const btns = Array.from(document.querySelectorAll(
                    'button,[role="button"]'
                )).filter(el => {
                    const t = (el.innerText || el.textContent || '').trim();
                    return t === '발행' || t.startsWith('발행') || t === '게시하기';
                });
                if (!btns.length) return null;
                // 가장 오른쪽 버튼 = 우측 상단 발행 버튼
                btns.sort((a, b) =>
                    b.getBoundingClientRect().right - a.getBoundingClientRect().right
                );
                btns[0].click();
                return btns[0].outerHTML.slice(0, 100);
            }""")
            if html:
                _log(f"1단계 (우측상단 버튼) 프레임{fi}: {html}")
                step1 = True
                break
        except Exception:
            pass

    if not step1:
        # Playwright locator 폴백 — 가장 마지막 발행 버튼 (DOM 순서상 우측)
        for sel in ["button:has-text('발행')", "button:has-text('게시하기')",
                    "[class*='publish']", "[class*='btn_pub']"]:
            try:
                btns = page.locator(sel)
                cnt = await btns.count()
                if cnt > 0:
                    await btns.last.click(force=True)
                    _log(f"1단계 force (last): {sel} ({cnt}개 중 마지막)")
                    step1 = True
                    break
            except Exception:
                pass

    if not step1:
        _log("1단계 발행 버튼 실패")
        return False

    await page.wait_for_timeout(2500)
    await _screenshot(page, "naver_panel.png")

    # 1.5단계: 발행 패널에서 '지금 발행' 선택 (예약대기 방지)
    await _select_publish_now(page)
    await page.wait_for_timeout(500)
    await _screenshot(page, "naver_panel_after_now.png")

    # 2단계: 패널 하단 최종 발행 버튼 클릭
    for fr in page.frames:
        try:
            n = await fr.evaluate("""() => {
                const all = Array.from(document.querySelectorAll('button,[role="button"]'))
                    .filter(b => (b.innerText || b.textContent || '').trim().includes('발행'));
                if (all.length) { all[all.length - 1].click(); return all.length; }
                return 0;
            }""")
            if n:
                _log(f"2단계 JS 클릭 (발행 버튼 {n}개 중 마지막)")
                return True
        except Exception:
            pass

    try:
        btns = page.locator("button:has-text('발행')")
        cnt = await btns.count()
        if cnt > 0:
            await btns.last.click(force=True)
            _log(f"2단계 force click (총 {cnt}개)")
    except Exception:
        pass

    return True


async def _post_to_naver(
    title: str, content: str, images: list,
    naver_id: str, naver_pw: str, naver_blog_id: str
) -> dict:
    _log("\n\n=== 포스팅 시작 ===")
    clean_title = _strip_markdown(title)
    clean_content = _strip_markdown(content)
    _log(f"제목: {clean_title[:60]}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=IS_HEADLESS,
            slow_mo=50 if not IS_HEADLESS else 0,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox",
                  "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            const _obs = new MutationObserver(() => {
                const p = document.querySelector('.se-help-panel');
                if (p) {
                    p.style.setProperty('display','none','important');
                    const b = p.querySelector('.se-help-panel-close-button,button');
                    if (b) b.click();
                }
            });
            const _attach = () => _obs.observe(document.body,
                {childList:true, subtree:true, attributes:true});
            if (document.body) _attach();
            else document.addEventListener('DOMContentLoaded', _attach);
        """)

        try:
            # ── 로그인 ──
            cookie_ok = await _load_cookies(context)
            if cookie_ok:
                await page.goto("https://www.naver.com", wait_until="load", timeout=20000)
                await page.wait_for_timeout(2000)
                is_logged = await page.locator(
                    ".MyView-module__btn_my___HmOXb,.gnb_my_img,#account,.gnb_login_area"
                ).count() > 0
                _log(f"쿠키 로그인: {is_logged}")
            else:
                is_logged = False

            if not is_logged:
                ok = await _do_manual_login(page)
                if not ok:
                    return {"success": False, "error": "로그인 실패 (120초 초과)"}
                await _save_cookies(context)

            # ── 에디터 열기 ──
            write_url = f"https://blog.naver.com/{naver_blog_id}?Redirect=Write&"
            _log(f"에디터 이동: {write_url}")
            await page.goto(write_url, wait_until="load", timeout=30000)
            await page.wait_for_timeout(3000)

            frame = await _get_editor_frame(page)
            await _hide_help_panel(page)
            await _screenshot(page, "01_editor_loaded.png")

            # ── 제목 입력 ──
            await _enter_title(page, frame, clean_title)
            await page.wait_for_timeout(500)
            await _screenshot(page, "02_after_title.png")

            # ── 본문 + 이미지 ──
            _log(f"본문 입력 시작 (이미지 {len(images)}장)")
            await _enter_body_with_images(page, frame, clean_content, images)
            await page.wait_for_timeout(1000)

            await _hide_help_panel(page)
            await _screenshot(page, "03_before_publish.png")

            # ── 발행 ──
            ok = await _publish(page)
            if not ok:
                raise Exception("발행 실패")

            _log("발행 완료 — URL 변경 대기 중")

            # 발행 후 Write URL에서 벗어날 때까지 최대 25초 대기
            for _ in range(50):
                current = page.url
                if "Redirect=Write" not in current:
                    _log(f"URL 변경 감지: {current}")
                    break
                await page.wait_for_timeout(500)
            else:
                _log("URL 변경 없음 (25초 초과)")

            try:
                await page.wait_for_load_state("load", timeout=10000)
            except Exception:
                pass

            post_url = page.url

            # Write URL 그대로면 블로그 홈 URL로 대체
            if "Redirect=Write" in post_url or not post_url:
                post_url = f"https://blog.naver.com/{naver_blog_id}"

            _log(f"완료 URL: {post_url}")
            return {"success": True, "url": post_url}

        except Exception as e:
            err = traceback.format_exc()
            _log(f"ERROR:\n{err}")
            await _screenshot(page, "99_error.png")
            return {"success": False, "error": str(e) or err[:400]}
        finally:
            await browser.close()


def delete_saved_cookies():
    if os.path.exists(COOKIE_PATH):
        os.remove(COOKIE_PATH)
        return True
    return False


def post_to_naver_blog(
    title: str, content: str, images: list,
    naver_id: str, naver_pw: str, naver_blog_id: str
) -> dict:
    result = {"success": False, "error": "알 수 없는 오류"}

    def run():
        loop = asyncio.ProactorEventLoop()
        asyncio.set_event_loop(loop)
        try:
            r = loop.run_until_complete(
                _post_to_naver(title, content, images, naver_id, naver_pw, naver_blog_id)
            )
            result.update(r)
        except Exception as e:
            err = traceback.format_exc()
            _log(f"THREAD ERROR:\n{err}")
            result.update({"success": False, "error": str(e) or err[:400]})
        finally:
            loop.close()

    t = threading.Thread(target=run)
    t.start()
    t.join()
    return result
