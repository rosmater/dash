import sys, subprocess, time, os
from playwright.sync_api import sync_playwright
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
srv = subprocess.Popen([sys.executable, '-m', 'http.server', '8765', '--bind', '127.0.0.1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
variants = sys.argv[1:] or ['a', 'b', 'c']
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path='/usr/bin/google-chrome', args=['--no-sandbox'])
        for v in variants:
            for name, vp, tab in [('', dict(width=1440, height=900), 'overview'), ('-peptides', dict(width=1440, height=900), 'peptides'), ('-mobile', dict(width=390, height=844), 'overview')]:
                pg = b.new_page(viewport=vp, device_scale_factor=2 if 'mobile' in name else 1)
                errs = []
                pg.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
                pg.on('pageerror', lambda e: errs.append(str(e)))
                pg.goto(f'http://127.0.0.1:8765/variant-{v}.html?mode=week&tab={tab}', wait_until='networkidle')
                pg.wait_for_timeout(1500)
                out = f'shots/variant-{v}{name}.png'
                pg.screenshot(path=out, full_page=True)
                print(out, 'errors:', errs[:5])
                pg.close()
        b.close()
finally:
    srv.terminate()
