import threading, http.server, socketserver, functools
from playwright.sync_api import sync_playwright
H=functools.partial(http.server.SimpleHTTPRequestHandler,directory="/home/claude/survey-app")
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*a): pass
H=functools.partial(Q,directory="/home/claude/survey-app")
srv=socketserver.TCPServer(("127.0.0.1",8792),H,bind_and_activate=False); srv.allow_reuse_address=True; srv.server_bind(); srv.server_activate()
threading.Thread(target=srv.serve_forever,daemon=True).start()
with sync_playwright() as p:
    b=p.chromium.launch(executable_path="/usr/bin/google-chrome",args=["--no-sandbox"])
    for name,vp in [("m390",{"width":390,"height":844}),("m360",{"width":360,"height":740}),("desk",{"width":1280,"height":800})]:
        c=b.new_context(viewport=vp,device_scale_factor=1 if name=="desk" else 2,has_touch=name!="desk"); pg=c.new_page()
        pg.goto("http://127.0.0.1:8792/index.html?test=1"); pg.wait_for_selector(".btn"); pg.wait_for_timeout(700); pg.screenshot(path=f"tests/{name}_intro.png")
        pg.click(".btn"); pg.wait_for_timeout(500); pg.click(".opt >> nth=0"); pg.wait_for_timeout(600); pg.click(".opt >> nth=0"); pg.wait_for_timeout(600); pg.click(".opt >> nth=0"); pg.wait_for_selector(".spec"); pg.wait_for_timeout(700); pg.screenshot(path=f"tests/{name}_card.png")
        ov=pg.evaluate("document.documentElement.scrollWidth>document.documentElement.clientWidth"); print(name,"가로 스크롤 발생:",ov)
        for k in range(8): pg.click(f".pt[aria-label='{(k%7)+1}점']"); pg.wait_for_timeout(420)
        pg.wait_for_timeout(600); pg.screenshot(path=f"tests/{name}_q3.png")
    b.close()
