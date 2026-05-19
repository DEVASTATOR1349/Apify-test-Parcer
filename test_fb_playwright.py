"""Тест: Playwright → ВСЕ FB профили из таблицы → подписчики."""
import re, sys
sys.path.insert(0, 'src')
from sheets import read_links_sheet
from playwright.sync_api import sync_playwright

# Собираем все FB-ссылки
fb_links = []
for p in read_links_sheet():
    for l in p['links']:
        if 'facebook.com' in l:
            fb_links.append((p['name'], l))

# Чистим URL от мусора
def clean_url(u):
    u = u.split('&mibextid')[0]
    u = u.split('?mibextid')[0]
    u = u.split('&sk=')[0]
    u = u.split('&rdid=')[0]
    u = u.split('&share_url=')[0]
    return u.rstrip('?')

print(f"Total FB profiles: {len(fb_links)}")
results = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        proxy={
            'server': 'http://176.118.189.157:63416',
            'username': 'Sg91cpe23',
            'password': 'ErHxGv1C2',
        },
        args=['--disable-blink-features=AutomationControlled']
    )
    ctx = browser.new_context(
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    )
    
    for name, url in fb_links:
        clean = clean_url(url)
        print(f"\n--- {name} ---")
        print(f"  URL: {clean[:80]}")
        try:
            page = ctx.new_page()
            page.goto(clean, timeout=20000, wait_until='domcontentloaded')
            page.wait_for_timeout(4000)
            text = page.inner_text('body')
            final_url = page.url
            
            # Проверяем приватность
            if 'Этот контент сейчас недоступен' in text or 'Выполните вход' in text:
                status = 'PRIVATE'
                count = None
                print(f"  ❌ PRIVATE (login wall)")
            else:
                # Ищем подписчиков
                m = re.search(r'(\d[\d\s]*)\s*[—–-]\s*подписчик', text, re.I)
                if m:
                    count = m.group(1).replace(' ', '')
                    status = 'OK'
                    print(f"  ✅ {count} подписчиков")
                else:
                    # Ищем followers
                    m = re.search(r'(\d[\d,.]*)\s*followers?', text, re.I)
                    if m:
                        count = m.group(1).replace(',', '').replace('.', '')
                        status = 'OK'
                        print(f"  ✅ {count} followers")
                    else:
                        count = None
                        status = 'NO_DATA'
                        print(f"  ⚠️ No follower count, title: {page.title()[:60]}")
                        # Покажем что есть
                        lines = [l.strip() for l in text.split('\n') if l.strip() and len(l.strip()) < 150]
                        for l in lines[:10]:
                            print(f"    {l}")
            
            results.append({'name': name, 'url': clean, 'status': status, 'count': count, 'final_url': final_url})
            page.close()
        except Exception as e:
            err = str(e)[:100]
            print(f"  ❌ ERROR: {err}")
            results.append({'name': name, 'url': clean, 'status': 'ERROR', 'count': None, 'error': err})
    
    browser.close()

# Итоги
ok = [r for r in results if r['status'] == 'OK']
private = [r for r in results if r['status'] == 'PRIVATE']
err = [r for r in results if r['status'] == 'ERROR']
nodata = [r for r in results if r['status'] == 'NO_DATA']

print(f"\n{'='*60}")
print(f"ИТОГ: OK={len(ok)} PRIVATE={len(private)} NO_DATA={len(nodata)} ERROR={len(err)}")
print(f"\nУспешно:")
for r in ok:
    print(f"  {r['name']:25} → {r['count']} подписчиков")
if private:
    print(f"\nПриватные (нужен логин):")
    for r in private:
        print(f"  {r['name']}")
if nodata:
    print(f"\nБез данных:")
    for r in nodata:
        print(f"  {r['name']}")
