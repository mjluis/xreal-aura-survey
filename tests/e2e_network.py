import json, sys, os, threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
H=functools.partial(Q,directory=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
srv=socketserver.TCPServer(("127.0.0.1",8793),H,bind_and_activate=False); srv.allow_reuse_address=True; srv.server_bind(); srv.server_activate()
threading.Thread(target=srv.serve_forever,daemon=True).start()
URL="http://127.0.0.1:8793/index.html?test=1"
FAKE="https://fake-proj.supabase.co"; KEY="sb_publishable_TESTKEY"
fails=[]
def check(c,m):
    print(("PASS " if c else "FAIL ")+m)
    if not c: fails.append(m)
CONFIG=f'window.SURVEY_CONFIG={{SUPABASE_URL:"{FAKE}",SUPABASE_KEY:"{KEY}",TABLE:"responses",FORM_VERSION:"v5"}};'

def fill(pg):
    pg.goto(URL); pg.wait_for_selector(".btn"); pg.click(".btn"); pg.wait_for_selector("h2:has-text('연령대')")
    pg.click(".opt >> nth=0"); pg.wait_for_selector("h2:has-text('취미·관심 분야')")                    # age
    pg.click(".opt >> nth=0"); pg.click(".btn.block"); pg.wait_for_selector("h2:has-text('새로 나온 IT 기기')")   # interests → 다음
    pg.click(".opt >> nth=0"); pg.wait_for_selector("h2:has-text('주로 사용하는 스마트폰')")              # adopt_style
    pg.click(".opt >> nth=0"); pg.wait_for_selector("h2:has-text('써 본 적')")                          # q1
    pg.click(".opt >> nth=0"); pg.wait_for_selector("h2:has-text('XREAL AURA 소개')")                   # q2
    pg.wait_for_timeout(300); pg.click(".btn.block"); pg.wait_for_selector("h2:has-text('지불할 수 있는 최대 금액')")  # product → 다음
    pg.click(".opt >> nth=0"); pg.wait_for_selector(".spec")                                            # wtp
    for k in range(8): pg.click(f".pt[aria-label='{(k%7)+1}점']"); pg.wait_for_timeout(420)
    pg.wait_for_selector("h2:has-text('가장 망설이게')"); pg.click(".opt >> nth=0"); pg.click(".btn.block")   # q3 → 다음
    pg.wait_for_selector("h2:has-text('다양한 앱과 콘텐츠가 제공되더라도')"); pg.click(".opt >> nth=0"); pg.click(".btn.block")   # q4 → 다음
    pg.wait_for_selector("h2:has-text('어떤 가치가 가장 의미')"); pg.click(".opt >> nth=0")                # value_source
    pg.wait_for_selector("h2:has-text('어떤 기능이나 가치가 있어야')"); pg.click(".opt >> nth=0"); pg.click(".btn.block")   # use_values → 제출

def run(b, name, statuses, after=None, expect=None):
    ctx=b.new_context(viewport={"width":390,"height":844}); pg=ctx.new_page()
    calls=[]; seq=list(statuses)
    pg.route("**/config.js", lambda r: r.fulfill(status=200,content_type="application/javascript",body=CONFIG))
    def api(route):
        req=route.request; calls.append({"url":req.url,"headers":req.headers,"body":req.post_data,"method":req.method})
        st=seq.pop(0) if seq else statuses[-1]
        if st==0: return route.abort()
        route.fulfill(status=st,headers={"access-control-allow-origin":"*","access-control-allow-headers":"*"},body="" if st<300 else json.dumps({"message":"err","code":str(st)}))
    pg.route(f"{FAKE}/**", lambda r: r.fulfill(status=204,headers={"access-control-allow-origin":"*","access-control-allow-headers":"*","access-control-allow-methods":"*"}) if r.request.method=="OPTIONS" else api(r))
    fill(pg); return pg,calls,ctx

with sync_playwright() as p:
    b=p.chromium.launch(**({"executable_path":"/usr/bin/google-chrome","args":["--no-sandbox"]} if os.path.exists("/usr/bin/google-chrome") else {}))
    # 1) 500,500,201 → 3번째 시도에서 성공
    pg,calls,ctx=run(b,"retry",[500,500,201]); pg.wait_for_selector("text=참여해 주셔서",timeout=15000)
    check(len(calls)==3,f"500,500,201 → 총 3회 시도 후 성공 (시도 {len(calls)})")
    c=calls[0]; body=json.loads(c["body"])
    check(c["url"]==f"{FAKE}/rest/v1/responses" and c["method"]=="POST","요청 URL/메서드가 PostgREST 형식 (on_conflict 없음)")
    check(c["headers"].get("apikey")==KEY and "authorization" not in c["headers"],"apikey 헤더만 전송, Authorization 없음")
    check(c["headers"].get("prefer")=="return=minimal","Prefer: return=minimal")
    check(len({json.loads(x['body'])['resp_id'] for x in calls})==1,"재시도마다 같은 resp_id 사용")
    check(isinstance(body["q4_constraints"],list) and 1<=len(body["q4_constraints"])<=2 and body["age_band"]=="20_22" and body["wtp_band"]=="lt100" and "s1_20s" not in body,"v4 필드 값/형식(age_band, wtp_band, q4_constraints 배열, s1_20s 없음)")
    check(all(k in body for k in ["resp_id","t_start","t_end","duration_sec","age_band","q1_phone","q2_xr","wtp_band","card_order","card_ms","intent_p1","intent_p8","q3_barrier","q4_constraints","device_type","form_version","is_test","src",
                                  "interests","adopt_style","value_source","use_values","intro_ms"]),"본문에 스키마의 모든 컬럼(v5 신규 5개 포함)")
    check(body["form_version"]=="v5" and len(body["interests"])==1 and body["adopt_style"]=="early" and body["value_source"] in ["device","ai","apps","content","peers_info","peers_together","price"] and len(body["use_values"])==1 and isinstance(body["intro_ms"],int) and body["intro_ms"]>0,
          f"v5 필드 값/형식 (interests={body['interests']}, adopt_style={body['adopt_style']}, value_source={body['value_source']}, use_values={body['use_values']}, intro_ms={body['intro_ms']})")
    ctx.close()
    # 2) 전부 실패(503) → 실패 화면 → 복구 후 다시 시도
    pg,calls,ctx=run(b,"fail",[503,503,503]); pg.wait_for_selector("text=저장하지 못했습니다",timeout=20000)
    check(len(calls)==3,"503 연속 → 3회 시도 후 실패 화면")
    check(pg.evaluate("localStorage.getItem('xr_survey_pending_v5')") is not None,"실패 시 응답이 기기에 보관됨(pending)")
    rid=json.loads(calls[0]["body"])["resp_id"]; n=len(calls)
    pg.unroute(f"{FAKE}/**"); pg.route(f"{FAKE}/**", lambda r: r.fulfill(status=204 if r.request.method=="OPTIONS" else 201,headers={"access-control-allow-origin":"*","access-control-allow-headers":"*","access-control-allow-methods":"*"},body=""))
    pg.click("button.btn:has-text('다시 시도')"); pg.wait_for_selector("text=참여해 주셔서",timeout=10000)
    check(pg.evaluate("localStorage.getItem('xr_survey_pending_v5')") is None,"재시도 성공 후 pending 삭제")
    ctx.close()
    # 2b) 실패 후 새로고침해도 응답 보존 → 다시 시도 가능
    pg,calls,ctx=run(b,"fail2",[503,503,503]); pg.wait_for_selector("text=저장하지 못했습니다",timeout=20000)
    pg.reload(); pg.wait_for_selector("text=저장하지 못했습니다",timeout=8000); check(True,"실패 화면에서 새로고침해도 실패 화면/응답 유지")
    ctx.close()
    # 3) 409(이미 저장됨) → 성공 처리
    pg,calls,ctx=run(b,"dup",[409]); pg.wait_for_selector("text=참여해 주셔서",timeout=10000)
    check(len(calls)==1,"409 → 재시도 없이 성공 처리"); ctx.close()
    # 4) 400(검증 거부) → 재시도 없이 실패
    pg,calls,ctx=run(b,"bad",[400]); pg.wait_for_selector("text=저장하지 못했습니다",timeout=10000)
    check(len(calls)==1,"400 → 재시도하지 않고 실패 화면"); ctx.close()
    # 4b) 종료 경로(만 20~29세 아님)는 서버로 아무것도 보내지 않음
    ctx=b.new_context(viewport={"width":390,"height":844}); pg=ctx.new_page(); calls=[]
    pg.route("**/config.js", lambda r: r.fulfill(status=200,content_type="application/javascript",body=CONFIG))
    pg.route(f"{FAKE}/**", lambda r: (calls.append(r.request.method), r.fulfill(status=201,headers={"access-control-allow-origin":"*"},body="")))
    pg.goto(URL); pg.wait_for_selector(".btn"); pg.click(".btn"); pg.wait_for_selector("h2:has-text('연령대')")
    pg.click(".opt:has-text('만 20~29세가 아닙니다')"); pg.wait_for_selector("text=이번 설문은 만 20~29세를 대상"); pg.wait_for_timeout(1500)
    check(not calls and pg.evaluate("localStorage.getItem('xr_survey_pending_v5')") is None,"종료 경로 → 서버 요청 0건, pending 없음")
    ctx.close()
    # 5) 네트워크 단절(abort)
    pg,calls,ctx=run(b,"offline",[0,0,0]); pg.wait_for_selector("text=저장하지 못했습니다",timeout=20000)
    check(len(calls)==3,"네트워크 오류 → 3회 시도 후 실패 화면"); ctx.close()
    b.close()
print("\nFAILS:",fails if fails else "none"); sys.exit(1 if fails else 0)
