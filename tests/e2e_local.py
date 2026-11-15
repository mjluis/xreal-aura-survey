import json, sys, os, re, threading, http.server, socketserver, functools, collections
from playwright.sync_api import sync_playwright
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOT=lambda n: os.path.join(ROOT,"tests",n)
Handler=functools.partial(http.server.SimpleHTTPRequestHandler, directory=ROOT)
Handler.log_message=lambda *a,**k: None
srv=socketserver.TCPServer(("127.0.0.1",8791),Handler,bind_and_activate=False); srv.allow_reuse_address=True; srv.server_bind(); srv.server_activate(); threading.Thread(target=srv.serve_forever,daemon=True).start()
URL="http://127.0.0.1:8791/index.html?test=1&src=pilot"
LOCAL_CFG='window.SURVEY_CONFIG={SUPABASE_URL:"",SUPABASE_KEY:"",TABLE:"responses",FORM_VERSION:"v5"};'
fails=[]
def check(c,msg):
    print(("PASS " if c else "FAIL ")+msg)
    if not c: fails.append(msg)

# migration_v5.sql / schema.sql 의 CHECK 제약을 그대로 옮긴 검사기
INTERESTS=["gaming","tech_gadget","video","study","creative","sports","travel","social","other"]
USEV=["assistant","translation","notifications","big_screen","capture","vision_ai","study_work_ai","ar_games","none"]
Q4=["apps_lack","substitute","complex","peers_lack","supply_uncertain","none"]
def arr_ok(a,allowed,excl): return isinstance(a,list) and 1<=len(a)<=2 and set(a)<=set(allowed) and len(set(a))==len(a) and (excl not in a or len(a)==1)
def row_ok(p):
    errs=[]
    req=lambda c,n: errs.append(n) if not c else None
    req(re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",p.get("resp_id","")),"resp_id")
    req(isinstance(p.get("duration_sec"),int) and 0<=p["duration_sec"]<=7200,"duration_sec")
    req(p.get("age_band") in ["20_22","23_25","26_27","28_29"],"age_band")
    req(p.get("q1_phone") in ["iphone","galaxy","other"],"q1_phone")
    req(p.get("q2_xr") in ["none","tried","owner"],"q2_xr")
    req(p.get("wtp_band") in ["lt100","100_150","150_170","170_200","gte200","none"],"wtp_band")
    req(sorted(p.get("card_order",[]))==list(range(1,9)),"card_order")
    req(len(p.get("card_ms",[]))==8 and all(isinstance(x,int) for x in p["card_ms"]),"card_ms")
    for k in range(1,9): req(isinstance(p.get(f"intent_p{k}"),int) and 1<=p[f"intent_p{k}"]<=7,f"intent_p{k}")
    req(p.get("q3_barrier") in ["price","apps","peers","comfort","privacy","other"],"q3_barrier")
    req(p.get("q3_other") is None or len(p["q3_other"])<=100,"q3_other")
    req(arr_ok(p.get("q4_constraints"),Q4,"none"),"q4_constraints")
    req(p.get("device_type") in ["mobile","tablet","desktop"],"device_type")
    req(isinstance(p.get("form_version"),str) and len(p["form_version"])<=10,"form_version")
    req(p.get("src") is None or re.fullmatch(r"[A-Za-z0-9_-]{1,40}",p["src"]),"src")
    req(p.get("interests") is None or arr_ok(p["interests"],INTERESTS,"other"),"interests")
    req(p.get("adopt_style") is None or p["adopt_style"] in ["early","review","price_drop","need_only","none"],"adopt_style")
    req(p.get("value_source") is None or p["value_source"] in ["device","ai","apps","content","peers_info","peers_together","price","none"],"value_source")
    req(p.get("use_values") is None or arr_ok(p["use_values"],USEV,"none"),"use_values")
    req(p.get("intro_ms") is None or (isinstance(p["intro_ms"],int) and 0<=p["intro_ms"]<=3600000),"intro_ms")
    req(p.get("form_version")!="v5" or all(p.get(k) is not None for k in ["interests","adopt_style","value_source","use_values","intro_ms"]),"v5_required")
    return errs

FORBIDDEN=[r"\d[\d,.]*\s*(만\s*)?원",r"\d+\s*개",r"수백",r"수십",r"할인",r"Catalyst",r"!",r"혁신",r"편리",r"\d+\s*명",r"판매",r"이용자 수",r"%",r"광학",r"앱·콘텐츠"]

def multi_rules(pg, name, excl_label, a, b, c, key):
    """최대 2개, 단독(기타/없다), 최소 1개 규칙 공통 검사. a,b,c 는 일반 보기 문구, key 는 상태 키"""
    st=lambda: pg.evaluate(f"__survey.state.{key}")
    check(pg.is_disabled(".btn.block"),f"{name}: 미선택 시 버튼 비활성(최소 1개)")
    pg.click(f".opt:has-text('{a}')"); pg.click(f".opt:has-text('{b}')")
    check(len(st())==2,f"{name}: 2개 선택됨")
    pg.click(f".opt:has-text('{c}')",force=True)
    check(len(st())==2 and pg.locator(".opt[aria-checked='true']").count()==2,f"{name}: 3번째 선택은 무시(최대 2개)")
    check(pg.locator(".opt[aria-disabled='true']").count()==6,f"{name}: 2개 선택 시 나머지 일반 보기 6개 비활성(aria-disabled)")
    check(pg.get_attribute(f".opt:has-text('{excl_label}')","aria-disabled")=="false",f"{name}: '{excl_label}'은 항상 클릭 가능")
    pg.click(f".opt:has-text('{excl_label}')")
    excl=pg.evaluate(f"__survey.state.{key}")
    check(len(excl)==1 and pg.locator(".opt[aria-disabled='true']").count()==0,f"{name}: '{excl_label}' 선택 시 다른 선택 해제(단독) {excl}")
    pg.click(f".opt:has-text('{a}')")
    check(len(st())==1 and st()[0]!=excl[0],f"{name}: 다른 보기를 고르면 '{excl_label}' 해제")
    pg.click(f".opt:has-text('{excl_label}')"); pg.click(f".opt:has-text('{excl_label}')")
    check(st()==[] and pg.is_disabled(".btn.block"),f"{name}: '{excl_label}' 다시 누르면 해제, 버튼 다시 비활성")

with sync_playwright() as p:
    b=p.chromium.launch(**({"executable_path":"/usr/bin/google-chrome","args":["--no-sandbox"]} if os.path.exists("/usr/bin/google-chrome") else {}))
    iphone=dict(viewport={"width":390,"height":844},device_scale_factor=2,is_mobile=True,has_touch=True,user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148")
    ctx=b.new_context(**iphone); pg=ctx.new_page(); errs=[]
    pg.route("**/config.js", lambda r: r.fulfill(status=200,content_type="application/javascript",body=LOCAL_CFG))  # 실제 config.js와 무관하게 로컬 모드로 시험
    pg.on("pageerror",lambda e: errs.append(str(e))); pg.on("console",lambda m: errs.append(m.text) if m.type=="error" else None)
    pg.goto(URL); pg.wait_for_selector(".btn")
    # 1) 부적격 경로: 아무것도 저장하지 않음
    pg.click(".btn"); pg.wait_for_selector("h2:has-text('연령대')"); pg.click(".opt:has-text('만 20~29세가 아닙니다')"); pg.wait_for_selector("text=이번 설문은 만 20~29세를 대상")
    check(pg.evaluate("localStorage.getItem('xr_survey_local_v5')") is None and pg.evaluate("localStorage.getItem('xr_survey_pending_v5')") is None,"'만 20~29세가 아닙니다' → 종료 화면, 응답 저장 안 함")
    pg.click("#back"); pg.wait_for_selector("h2:has-text('연령대')")
    check(pg.evaluate("__survey.state.age") is None,"종료 화면에서 이전 → 연령대 화면 복귀, 값 초기화")
    # 2) interests
    pg.click(".opt:has-text('만 20~22세')"); pg.wait_for_selector("h2:has-text('취미·관심 분야')")
    check(pg.evaluate("__survey.state.step")=="interests","age 다음은 interests")
    labels=pg.locator(".opt").all_inner_texts(); intOrder=pg.evaluate("__survey.state.intOrder")
    check(len(labels)==9 and labels[-1]=="기타" and sorted(intOrder)==sorted(INTERESTS[:-1]),f"interests 보기 9개, '기타'는 맨 아래, 앞 8개 순서 저장 {intOrder}")
    check(pg.locator(".opt[role='checkbox']").count()==9,"interests는 role=checkbox UI")
    multi_rules(pg,"interests","기타","게임 (PC","새로운 IT 기기","운동·야외활동","interests")
    pg.click(".opt:has-text('운동·야외활동')"); pg.click(".opt:has-text('게임 (PC')")
    pg.reload(); pg.wait_for_selector("h2:has-text('취미·관심 분야')")
    check(pg.evaluate("__survey.state.interests")==["sports","gaming"] and pg.evaluate("__survey.state.intOrder")==intOrder and pg.locator(".opt[aria-checked='true']").count()==2,"새로고침 후 interests 선택·보기 순서 유지")
    check(pg.locator(".opt").all_inner_texts()==labels,"새로고침 후 화면의 보기 순서도 동일")
    pg.click(".btn.block"); pg.wait_for_selector("h2:has-text('새로 나온 IT 기기')")
    # 3) adopt_style
    alabels=pg.locator(".opt").all_inner_texts()
    check(alabels==["출시 직후, 리뷰가 많지 않아도 구매하는 편이다","리뷰가 쌓이고 평이 좋으면 구매하는 편이다","가격이 내려가거나 할인할 때 구매하는 편이다","꼭 필요할 때만 구매한다","거의 구매하지 않는다"],"adopt_style 보기 5개, 순서 고정")
    pg.click(".opt:has-text('가격이 내려가거나')"); pg.wait_for_selector("h2:has-text('주로 사용하는 스마트폰')")
    check(pg.evaluate("__survey.state.adopt")=="price_drop","adopt_style 선택 → 자동 진행, 값 price_drop")
    pg.click("#back"); pg.wait_for_selector("h2:has-text('새로 나온 IT 기기')")
    check(pg.get_attribute(".opt:has-text('가격이 내려가거나')","aria-checked")=="true","이전으로 돌아오면 adopt_style 선택 표시 유지")
    pg.click(".opt:has-text('리뷰가 쌓이고')"); pg.wait_for_selector("h2:has-text('주로 사용하는 스마트폰')")
    check(pg.evaluate("__survey.state.adopt")=="review","adopt_style 수정 → review")
    # 4) q1, q2
    pg.dblclick(".opt:has-text('iPhone')"); pg.wait_for_selector("h2:has-text('써 본 적')")
    check(pg.evaluate("__survey.state.step")=="q2","Q1 더블탭해도 한 단계만 이동")
    pg.click(".opt:has-text('체험해 본')"); pg.wait_for_selector("h2:has-text('XREAL AURA 소개')")
    # 5) product
    check(pg.evaluate("__survey.state.step")=="product","q2 다음은 제품 소개")
    pg.wait_for_timeout(1500)
    check(pg.evaluate("__survey.state.step")=="product","제품 소개 화면은 자동 진행하지 않음(1.5초 대기)")
    txt=pg.inner_text("main")
    hits=[f for f in FORBIDDEN if re.search(f,txt)]
    check(not hits,f"제품 소개 화면에 금지 문구 없음(가격·앱 개수·수백·할인·Catalyst·느낌표 등) {hits}")
    check("시야각 70도" in txt and "약 95g" in txt and "약 265g" in txt and "정보 출처: XREAL 공식 제품 페이지, Google 공식 블로그(2026-10-28), 2026-11-15 열람." in txt and "이후 문항의 상품 정보(가격 등)는 가상 상품이며 실제 제품과 다를 수 있습니다." in txt,"제품 소개 본문·가상 상품 안내·출처 문구 포함")
    check(pg.locator(".diagram svg").count()==1 and pg.locator("main img").count()==0,"직접 그린 인라인 SVG 1개, 이미지 없음")
    check(pg.locator(".btn.block").inner_text()=="다음","제품 소개는 '다음' 버튼으로 진행")
    pg.wait_for_timeout(400); pg.reload(); pg.wait_for_selector("h2:has-text('XREAL AURA 소개')")
    ms1=pg.evaluate("__survey.state.intro_ms")
    check(ms1>=1500,f"새로고침 직전까지의 제품 소개 체류 시간 보존 intro_ms={ms1}")
    pg.wait_for_timeout(300); pg.click(".btn.block"); pg.wait_for_selector("h2:has-text('지불할 수 있는 최대 금액')")
    ms2=pg.evaluate("__survey.state.intro_ms")
    check(ms2>ms1,f"'다음' 시 체류 시간 누적 intro_ms={ms2}")
    pg.click("#back"); pg.wait_for_selector("h2:has-text('XREAL AURA 소개')"); pg.wait_for_timeout(200); pg.click(".btn.block"); pg.wait_for_selector("h2:has-text('지불할 수 있는 최대 금액')")
    ms3=pg.evaluate("__survey.state.intro_ms")
    check(ms3>ms2,f"뒤로 갔다 오면 체류 시간이 이어서 누적 intro_ms={ms3}")
    # 6) wtp, 카드 (v4와 동일)
    check(pg.is_visible(".def") and pg.locator(".opt").count()==6,"지불 의향 화면(정의 문구, 보기 6개) 그대로")
    pg.click(".opt:has-text('170만 원 이상 200만 원 미만')"); pg.wait_for_selector(".spec")
    order=pg.evaluate("__survey.state.order"); check(sorted(order)==list(range(1,9)),f"카드 순서는 1~8 순열 {order}")
    rating={}
    for i in range(8):
        pid=order[i]
        spec=pg.inner_text(".spec").replace("\n"," ")
        prof=pg.evaluate("__survey.PROFILES")[pid-1]
        want=[["169만 원","100만 원"][prof[0]],["약 20개","약 300개"][prof[1]],["친구 10명 중 0명","친구 10명 중 4명"][prof[2]],["퍽 분리형","단독형"][prof[3]]]
        check(all(w in spec for w in want),f"카드{i+1}(상품{pid}) 표시 수준이 설계표와 일치")
        v=(pid*3)%7+1; rating[pid]=v
        if i==2:
            pg.keyboard.press("5"); pg.wait_for_timeout(500)
            check(pg.evaluate("__survey.state.step")=="c3","키보드 5 입력 → 다음 카드")
            pg.click("#back"); pg.wait_for_timeout(400)
            check(pg.evaluate("__survey.state.step")=="c2" and pg.evaluate("__survey.state.intent")[str(pid)]==5,"이전 → 직전 카드로 이동, 기존 값 5 유지")
            pg.keyboard.press("2"); pg.wait_for_timeout(500); rating[pid]=2
            continue
        pg.click(f".pt[aria-label='{v}점']"); pg.wait_for_timeout(450)
    check(pg.evaluate("__survey.state.step")=="q3","8장 완료 후 Q3")
    # 7) q3, q4 (문구·보기 동일, q4 버튼은 '다음')
    check(pg.is_disabled(".btn.block"),"Q3 미선택 시 '다음' 버튼 비활성")
    pg.click(".opt:has-text('기타')"); pg.fill(".other-wrap input","배터리 시간")
    pg.reload(); pg.wait_for_selector("h2:has-text('망설이게')")
    check(pg.evaluate("__survey.state.order")==order and pg.input_value(".other-wrap input")=="배터리 시간","새로고침 후 카드 순서·Q3 기타 입력 유지")
    pg.click(".btn.block"); pg.wait_for_selector("h2:has-text('다양한 앱과 콘텐츠가 제공되더라도')")
    labels4=pg.locator(".opt").all_inner_texts(); check(len(labels4)==6 and labels4[-1]=="특별히 망설일 이유가 없다","Q4 보기 6개, '없다'는 맨 아래(v4와 동일)")
    check(pg.locator(".btn.block").inner_text()=="다음","Q4 버튼은 '다음'(마지막 문항이 아니므로)")
    pg.click(".opt:has-text('사용 방법이 복잡')"); pg.click(".opt:has-text('다른 이용자와 함께')")
    pg.click(".opt:has-text('기존 스마트폰이나 노트북')",force=True)
    check(sorted(pg.evaluate("__survey.state.q4"))==["complex","peers_lack"],"Q4 최대 2개 유지")
    pg.click(".btn.block"); pg.wait_for_selector("h2:has-text('어떤 가치가 가장 의미')")
    # 8) value_source
    vlabels=pg.locator(".opt").all_inner_texts(); vsOrder=pg.evaluate("__survey.state.vsOrder")
    check(len(vlabels)==8 and vlabels[-1]=="특별히 의미 있는 가치가 없다" and sorted(vsOrder)==sorted(["device","ai","apps","content","peers_info","peers_together","price"]),f"value_source 보기 8개, '없다'는 맨 아래, 앞 7개 순서 저장 {vsOrder}")
    check(pg.locator(".opt[role='radio']").count()==8,"value_source는 단일 선택(radio)")
    check(not re.search(r"H[1-3]|네트워크 효과|분석",pg.inner_text("main")),"value_source 화면에 H1~H3·네트워크 효과·분석 문구 없음")
    pg.click(".opt:has-text('다른 이용자가 공유하는')"); pg.wait_for_selector("h2:has-text('어떤 기능이나 가치가 있어야')")
    check(pg.evaluate("__survey.state.vsrc")=="peers_info","value_source 선택 → 자동 진행, 값 peers_info")
    pg.click("#back"); pg.wait_for_selector("h2:has-text('어떤 가치가 가장 의미')")
    check(pg.locator(".opt[aria-checked='true']").count()==1 and pg.locator(".opt").all_inner_texts()==vlabels,"이전으로 오면 value_source 선택·보기 순서 유지")
    pg.reload(); pg.wait_for_selector("h2:has-text('어떤 가치가 가장 의미')")
    check(pg.evaluate("__survey.state.vsOrder")==vsOrder and pg.locator(".opt").all_inner_texts()==vlabels,"새로고침 후 value_source 보기 순서 유지")
    pg.click(".opt:has-text('부담 없는 가격')"); pg.wait_for_selector("h2:has-text('어떤 기능이나 가치가 있어야')")
    check(pg.evaluate("__survey.state.vsrc")=="price","value_source 수정 → price (1개만)")
    # 9) use_values
    ulabels=pg.locator(".opt").all_inner_texts(); useOrder=pg.evaluate("__survey.state.useOrder")
    check(len(ulabels)==9 and ulabels[-1]=="특별히 필요한 기능이 없다" and sorted(useOrder)==sorted(USEV[:-1]),f"use_values 보기 9개, '없다'는 맨 아래, 앞 8개 순서 저장 {useOrder}")
    check(pg.locator(".btn.block").inner_text()=="제출하기","마지막 문항 버튼은 '제출하기'")
    multi_rules(pg,"use_values","특별히 필요한 기능이 없다","실시간 외국어 번역","AR 기반 게임","사진·영상 촬영","use")
    pg.click(".opt:has-text('AR 기반 게임')"); pg.click(".opt:has-text('AI 음성 비서')")
    pg.reload(); pg.wait_for_selector("h2:has-text('어떤 기능이나 가치가 있어야')")
    check(pg.evaluate("__survey.state.use")==["ar_games","assistant"] and pg.evaluate("__survey.state.useOrder")==useOrder and pg.locator(".opt").all_inner_texts()==ulabels,"새로고침 후 use_values 선택·보기 순서 유지")
    pg.click(".btn.block"); pg.wait_for_selector("text=참여해 주셔서")
    # 10) payload
    pay=json.loads(pg.evaluate("localStorage.getItem('xr_survey_local_v5')"))[0]
    check(all(pay[f'intent_p{k}']==rating[k] for k in range(1,9)),f"intent_p1~8 이 입력과 일치")
    check(pay["age_band"]=="20_22" and pay["q1_phone"]=="iphone" and pay["q2_xr"]=="tried" and pay["wtp_band"]=="170_200" and pay["q3_barrier"]=="other" and pay["q3_other"]=="배터리 시간" and pay["q4_constraints"]==["complex","peers_lack"],"v4 문항 값 그대로")
    check(pay["interests"]==["gaming","sports"],f"interests는 canonical 순서로 저장 {pay['interests']}")
    check(pay["use_values"]==["assistant","ar_games"],f"use_values는 canonical 순서로 저장 {pay['use_values']}")
    check(pay["adopt_style"]=="review" and pay["value_source"]=="price","adopt_style·value_source 저장값")
    check(isinstance(pay["intro_ms"],int) and pay["intro_ms"]>0 and pay["intro_ms"]>=ms3,f"intro_ms 양의 정수 {pay['intro_ms']}")
    check(pay["form_version"]=="v5" and pay["is_test"] is True and pay["src"]=="pilot" and pay["device_type"]=="mobile","form_version=v5, is_test, src, device_type")
    bad=row_ok(pay); check(not bad,f"payload 전체가 migration_v5 CHECK 형식을 통과 {bad}")
    check(pg.evaluate("localStorage.getItem('xr_survey_state_v5')") is None and pg.evaluate("localStorage.getItem('xr_survey_pending_v5')") is None,"성공 후 임시 상태 삭제")
    # 검사기 자체 점검(잘못된 값은 거부해야 함)
    for name,mut in [("interests 3개",{"interests":["gaming","video","study"]}),("interests 중복",{"interests":["gaming","gaming"]}),("interests other+",{"interests":["other","gaming"]}),
                     ("interests 잘못된 값",{"interests":["x"]}),("adopt_style 잘못",{"adopt_style":"x"}),("value_source 잘못",{"value_source":"x"}),
                     ("use_values none+",{"use_values":["none","capture"]}),("intro_ms 음수",{"intro_ms":-1}),("v5 필수 누락",{"use_values":None})]:
        q=dict(pay); q.update(mut); check(bool(row_ok(q)),f"검사기: {name} 거부")
    # 11) 중복 참여 방지 + 테스트 모드 우회 (v5 키)
    pg.evaluate("localStorage.setItem('xr_survey_done_v5','x')")
    pg.goto("http://127.0.0.1:8791/index.html"); pg.wait_for_selector("text=이미 참여"); check(True,"비테스트 모드: 완료 플래그 있으면 '이미 참여'")
    pg.goto(URL); pg.wait_for_selector(".btn"); check(pg.is_visible("text=동의하고 시작"),"?test=1 은 중복 방지 우회")
    # v4 중간 상태가 v5 흐름에 섞이지 않음
    pg.evaluate("localStorage.clear(); localStorage.setItem('xr_survey_state_v4', JSON.stringify({id:'x',step:'q4',order:[1,2,3,4,5,6,7,8],q4order:[]}))")
    pg.reload(); pg.wait_for_selector(".btn"); check(pg.evaluate("__survey.state.step")=="intro","v4 중간 상태는 무시하고 v5를 처음부터 시작")
    # 12) 무작위화: 새 세션 300회
    cnt=[collections.Counter() for _ in range(8)]; ic=collections.Counter(); vc=collections.Counter(); uc=collections.Counter(); seen=set()
    for _ in range(300):
        pg.evaluate("localStorage.clear()"); pg.reload()
        s=pg.evaluate("({o:__survey.state.order,i:__survey.state.intOrder,v:__survey.state.vsOrder,u:__survey.state.useOrder})")
        for pos,pid in enumerate(s["o"]): cnt[pos][pid]+=1
        ic[s["i"][0]]+=1; vc[s["v"][0]]+=1; uc[s["u"][0]]+=1; seen.add(tuple(s["i"]))
    worst=max(abs(cnt[pos][pid]-300/8) for pos in range(8) for pid in range(1,9))
    check(worst<22,f"카드 위치별 등장 빈도 균등(기대 37.5, 최대편차 {worst:.1f})")
    wi=max(abs(ic[k]-300/8) for k in INTERESTS[:-1]); wv=max(abs(vc[k]-300/7) for k in ["device","ai","apps","content","peers_info","peers_together","price"]); wu=max(abs(uc[k]-300/8) for k in USEV[:-1])
    check(wi<22 and wv<24 and wu<22 and len(seen)>250,f"interests/value_source/use_values 첫 보기 분포 균등(편차 {wi:.0f}/{wv:.0f}/{wu:.0f}), 순서 다양 {len(seen)}종")
    check(not errs,f"콘솔 오류 없음 {errs[:3]}")
    # 13) 360px: 제품 소개가 스크롤 없이 본문·버튼까지 보이는지
    for w,h in [(360,740),(390,844)]:
        c2=b.new_context(viewport={"width":w,"height":h},is_mobile=True,has_touch=True); p2=c2.new_page()
        p2.route("**/config.js", lambda r: r.fulfill(status=200,content_type="application/javascript",body=LOCAL_CFG))
        p2.goto(URL); p2.wait_for_selector(".btn")
        p2.evaluate("(()=>{const s=__survey.state; s.step='product'; localStorage.setItem('xr_survey_state_v5',JSON.stringify(s));})()"); p2.reload(); p2.wait_for_selector(".diagram svg"); p2.wait_for_timeout(600)
        bb=p2.locator(".btn.block").bounding_box(); sc=p2.evaluate("document.documentElement.scrollWidth>document.documentElement.clientWidth")
        check(bb["y"]+bb["height"]<=h and not sc,f"{w}x{h}: 제품 소개 본문·'다음' 버튼이 스크롤 없이 보임(버튼 하단 {bb['y']+bb['height']:.0f}px), 가로 스크롤 없음")
        c2.close()
    b.close()
print("\nFAILS:",fails if fails else "none"); sys.exit(1 if fails else 0)
