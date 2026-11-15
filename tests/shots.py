# v5 신규 화면 스크린샷: 폭 360/390/데스크톱 × 라이트/다크. 결과는 tests/shot5_*.png (커밋 제외: .gitignore의 tests/*.png)
import os, sys, json, threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
H=functools.partial(Q,directory=ROOT)
srv=socketserver.TCPServer(("127.0.0.1",8792),H,bind_and_activate=False); srv.allow_reuse_address=True; srv.server_bind(); srv.server_activate()
threading.Thread(target=srv.serve_forever,daemon=True).start()
CFG='window.SURVEY_CONFIG={SUPABASE_URL:"",SUPABASE_KEY:"",TABLE:"responses",FORM_VERSION:"v5"};'
STEPS=["interests","adopt_style","product","value_source","use_values"]
out=[]
with sync_playwright() as p:
    b=p.chromium.launch()
    for name,vp in [("m360",{"width":360,"height":740}),("m390",{"width":390,"height":844}),("desk",{"width":1280,"height":800})]:
        for scheme in ["light","dark"]:
            mob=name!="desk"
            c=b.new_context(viewport=vp,device_scale_factor=1 if not mob else 2,is_mobile=mob,has_touch=mob,color_scheme=scheme); pg=c.new_page()
            pg.route("**/config.js", lambda r: r.fulfill(status=200,content_type="application/javascript",body=CFG))
            pg.goto("http://127.0.0.1:8792/index.html?test=1"); pg.wait_for_selector(".btn")
            for st in STEPS:
                # 긴 문구 줄바꿈 확인용으로 2개 선택된 상태도 보이게 함
                pg.evaluate("""st=>{const s=__survey.state; s.step=st; s.age='20_22';
                  if(st==='interests') s.interests=[s.intOrder[0],s.intOrder[2]];
                  if(st==='use_values') s.use=[s.useOrder[1],s.useOrder[3]];
                  localStorage.setItem('xr_survey_state_v5',JSON.stringify(s));}""",st)
                pg.reload(); pg.wait_for_selector("h2"); pg.wait_for_timeout(600)
                ov=pg.evaluate("document.documentElement.scrollWidth>document.documentElement.clientWidth")
                f=os.path.join(ROOT,"tests",f"shot5_{name}_{scheme}_{st}.png"); pg.screenshot(path=f,full_page=True); out.append(f)
                print(f"{name} {scheme} {st}: 가로 스크롤 {'있음' if ov else '없음'}")
            c.close()
    b.close()
print("\n".join(out))
