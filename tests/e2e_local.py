import json, sys, os, threading, http.server, socketserver, functools, collections
from playwright.sync_api import sync_playwright
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT=lambda n: os.path.join(ROOT,"tests",n)
Handler=functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
Handler.log_message=lambda *a,**k: None
srv=socketserver.TCPServer(("127.0.0.1",8791),Handler,bind_and_activate=False); srv.allow_reuse_address=True; srv.server_bind(); srv.server_activate(); threading.Thread(target=srv.serve_forever,daemon=True).start()
URL="http://127.0.0.1:8791/index.html?test=1&src=pilot"
fails=[]
def check(c,msg):
    print(("PASS " if c else "FAIL ")+msg)
    if not c: fails.append(msg)
with sync_playwright() as p:
    b=p.chromium.launch(**({"executable_path":"/usr/bin/google-chrome","args":["--no-sandbox"]} if os.path.exists("/usr/bin/google-chrome") else {}))
    iphone=dict(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True,user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148")
    ctx=b.new_context(**iphone); pg=ctx.new_page(); errs=[]
    pg.route("**/config.js", lambda r: r.fulfill(status=200,content_type="application/javascript",body='window.SURVEY_CONFIG={SUPABASE_URL:"",SUPABASE_KEY:"",TABLE:"responses",FORM_VERSION:"v4"};'))  # 실제 config.js와 무관하게 로컬 모드로 시험
    pg.on("pageerror",lambda e: errs.append(str(e))); pg.on("console",lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto(URL); pg.wait_for_selector(".btn")
    pg.screenshot(path=SHOT("shot_intro.png"))
    # 1) 부적격 경로
    pg.click(".btn"); pg.wait_for_selector("h2:has-text('연령대')"); pg.click(".opt:has-text('만 20~29세가 아닙니다')"); pg.wait_for_selector("text=이번 설문은 만 20~29세를 대상")
    check(True,"'만 20~29세가 아닙니다' → 종료 화면(저장 안 함)")
    pg.click("#back"); pg.wait_for_selector("h2:has-text('연령대')")
    check(pg.evaluate("__survey.state.age") is None,"종료 화면에서 이전 → 연령대 화면 복귀, 값 초기화")
    # 2) 정상 경로 + 연타(더블탭) 방어
    pg.click(".opt:has-text('만 20~22세')"); pg.wait_for_selector("h2:has-text('스마트폰')")
    pg.dblclick(".opt:has-text('iPhone')"); pg.wait_for_selector("h2:has-text('써 본 적')")
    check(pg.evaluate("__survey.state.step")=="q2","Q1 더블탭해도 한 단계만 이동")
    pg.screenshot(path=SHOT("shot_q2.png"))
    pg.click(".opt:has-text('체험해 본')"); pg.wait_for_selector("h2:has-text('지불할 수 있는 최대 금액')")
    check(pg.evaluate("__survey.state.step")=="wtp" and pg.is_visible(".def"),"카드보다 먼저 지불 의향 화면(정의 문구 포함)이 나옴")
    check(pg.locator(".opt").count()==6,"지불 의향 보기 6개")
    check(not any(x in pg.inner_text("main") for x in ["169","199"]),"지불 의향 화면에 카드 가격(169/199)이 노출되지 않음")
    pg.screenshot(path=SHOT("shot_wtp.png"))
    pg.click(".opt:has-text('170만 원 이상 200만 원 미만')"); pg.wait_for_selector(".spec")
    order=pg.evaluate("__survey.state.order"); check(sorted(order)==list(range(1,9)),f"카드 순서는 1~8 순열 {order}")
    pg.screenshot(path=SHOT("shot_card.png"))
    # 3) 카드 8장: 이전 버튼으로 수정, 키보드 입력, 값 기록
    rating={}
    for i in range(8):
        pid=order[i]
        spec=pg.inner_text(".spec").replace("\n"," ")
        prof=pg.evaluate("__survey.PROFILES")[pid-1]
        want=[["169만 원","100만 원"][prof[0]],["약 20개","약 300개"][prof[1]],["친구 10명 중 0명","친구 10명 중 4명"][prof[2]],["퍽 분리형","단독형"][prof[3]]]
        check(all(w in spec for w in want),f"카드{i+1}(상품{pid}) 표시 수준이 설계표와 일치")
        v=(pid*3)%7+1; rating[pid]=v
        if i==2: # 키보드 입력 후 이전 버튼으로 돌아와 값 수정
            pg.keyboard.press("5"); pg.wait_for_timeout(500)
            check(pg.evaluate("__survey.state.step")=="c3","키보드 5 입력 → 다음 카드")
            pg.click("#back"); pg.wait_for_timeout(400)
            check(pg.evaluate("__survey.state.step")=="c2" and pg.evaluate("__survey.state.intent")[str(pid)]==5,"이전 → 직전 카드로 이동, 기존 값 5 유지")
            pg.keyboard.press("2"); pg.wait_for_timeout(500)
            rating[pid]=2
            check(pg.evaluate("__survey.state.step")=="c3","수정 후 다시 앞으로")
            continue
        pg.click(f".pt[aria-label='{v}점']"); pg.wait_for_timeout(450)
    check(pg.evaluate("__survey.state.step")=="q3","8장 완료 후 Q3")
    pg.screenshot(path=SHOT("shot_q3.png"))
    check(pg.is_disabled(".btn.block"),"Q3 미선택 시 '다음' 버튼 비활성")
    pg.click(".opt:has-text('기타')"); pg.fill(".other-wrap input","배터리 시간")
    check(pg.is_enabled(".btn.block"),"Q3 선택 후 '다음' 활성")
    # 새로고침 → 이어서 하기(순서 유지)
    pg.reload(); pg.wait_for_selector("h2:has-text('망설이게')")
    check(pg.evaluate("__survey.state.order")==order,"새로고침 후 카드 순서 유지, Q3에서 재개")
    check(pg.input_value(".other-wrap input")=="배터리 시간","새로고침 후 기타 입력 유지")
    pg.click(".btn.block"); pg.wait_for_selector("h2:has-text('다양한 앱과 콘텐츠가 제공되더라도')")
    # Q4: 최대 2개, none 배타, 셔플, 상태 유지
    check(pg.is_disabled(".btn.block"),"Q4 미선택 시 '제출하기' 비활성")
    labels=pg.locator(".opt").all_inner_texts(); check(len(labels)==6 and labels[-1]=="특별히 망설일 이유가 없다","Q4 보기 6개, '특별히 망설일 이유가 없다'는 항상 맨 아래")
    q4order=pg.evaluate("__survey.state.q4order"); check(sorted(q4order)==sorted(["apps_lack","substitute","complex","peers_lack","supply_uncertain"]),f"Q4 보기 순서(셔플) 저장 {q4order}")
    pg.click(".opt:has-text('기존 스마트폰이나 노트북')"); pg.click(".opt:has-text('다른 이용자와 함께')")
    check(pg.evaluate("__survey.state.q4").__len__()==2,"Q4 2개 선택됨")
    pg.click(".opt:has-text('사용 방법이 복잡')",force=True)  # aria-disabled 요소는 Playwright가 기다리므로 force
    check(sorted(pg.evaluate("__survey.state.q4"))==["peers_lack","substitute"],"Q4 3번째 선택은 무시됨(최대 2개)")
    check(pg.locator(".opt[aria-disabled='true']").count()==3,"Q4 2개 선택 시 선택 안 된 일반 보기 3개 비활성('없다'는 항상 활성)")
    pg.click(".opt:has-text('특별히 망설일 이유가 없다')")
    check(pg.evaluate("__survey.state.q4")==["none"],"2개 선택 상태에서 '없다'를 누르면 단독 선택으로 초기화")
    check(pg.locator(".opt[aria-disabled='true']").count()==0,"'없다' 단독 선택 시 비활성 보기 없음")
    pg.click(".opt:has-text('앱이나 콘텐츠의 사용 방법이 복잡')")
    check(pg.evaluate("__survey.state.q4")==["complex"],"다른 보기를 고르면 '없다'가 해제됨")
    pg.click(".opt:has-text('다른 이용자와 함께')")
    pg.reload(); pg.wait_for_selector("h2:has-text('다양한 앱과 콘텐츠가 제공되더라도')")
    check(sorted(pg.evaluate("__survey.state.q4"))==["complex","peers_lack"] and pg.evaluate("__survey.state.q4order")==q4order,"새로고침 후 Q4 선택·보기 순서 유지")
    check(pg.locator(".opt[aria-checked='true']").count()==2,"새로고침 후 화면에도 선택 표시 복원")
    pg.screenshot(path=SHOT("shot_q4.png"))
    pg.click(".btn.block"); pg.wait_for_selector("text=참여해 주셔서")
    pay=json.loads(pg.evaluate("localStorage.getItem('xr_survey_local_v4')"))[0]
    check(all(pay[f'intent_p{k}']==rating[k] for k in range(1,9)),f"intent_p1~8 이 입력과 일치 {rating}")
    check(pay["card_order"]==order and len(pay["card_ms"])==8 and all(x>=0 for x in pay["card_ms"]),"card_order·card_ms 길이/값")
    check(pay["age_band"]=="20_22" and pay["q1_phone"]=="iphone" and pay["q2_xr"]=="tried" and pay["wtp_band"]=="170_200" and pay["q3_barrier"]=="other" and pay["q3_other"]=="배터리 시간","age/Q1/Q2/wtp/Q3 값")
    check(pay["q4_constraints"]==["complex","peers_lack"] and "s1_20s" not in pay and pay["form_version"]=="v4","q4_constraints는 고정 순서로 저장, s1_20s 없음, form_version=v4")
    check(pay["is_test"] is True and pay["src"]=="pilot" and pay["device_type"]=="mobile" and True,"is_test/src/device_type")
    check(0<=pay["duration_sec"]<180,f"duration_sec={pay['duration_sec']}")
    check(pg.evaluate("localStorage.getItem('xr_survey_state_v4')") is None and pg.evaluate("localStorage.getItem('xr_survey_pending_v4')") is None,"성공 후 임시 상태 삭제")
    pg.screenshot(path=SHOT("shot_done.png"))
    # 4) 중복 참여 방지(비테스트 모드) + 테스트 모드 우회
    pg.evaluate("localStorage.setItem('xr_survey_done_v4','x')")
    pg.goto("http://127.0.0.1:8791/index.html"); pg.wait_for_selector("text=이미 참여")
    check(True,"비테스트 모드: 완료 플래그 있으면 '이미 참여' 표시")
    pg.goto(URL); pg.wait_for_selector(".btn"); check(pg.is_visible("text=동의하고 시작"),"?test=1 은 중복 방지 우회")
    # 5) 무작위화 분포: 새 세션 300회, 위치별 상품 등장 빈도
    cnt=[collections.Counter() for _ in range(8)]
    for _ in range(300):
        pg.evaluate("localStorage.clear()"); pg.reload(); o=pg.evaluate("__survey.state.order")
        for pos,pid in enumerate(o): cnt[pos][pid]+=1
    worst=max(abs(cnt[pos][pid]-300/8) for pos in range(8) for pid in range(1,9))
    check(worst<22,f"위치별 상품 등장 빈도가 균등(기대 37.5, 최대편차 {worst:.1f})")
    check(not errs,f"콘솔 오류 없음 {errs[:3]}")
    # 6) 다른 뷰포트 스크린샷
    ctx2=b.new_context(viewport={"width":1280,"height":800}); pd=ctx2.new_page(); pd.route("**/config.js", lambda r: r.fulfill(status=200,content_type="application/javascript",body='window.SURVEY_CONFIG={};')); pd.goto(URL); pd.wait_for_selector(".btn"); pd.screenshot(path=SHOT("shot_desktop_intro.png"))
    b.close()
print("\nFAILS:",fails if fails else "none"); sys.exit(1 if fails else 0)
