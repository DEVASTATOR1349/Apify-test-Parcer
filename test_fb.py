"""Тест Facebook через Apify web-scraper (бесплатный)."""
import sys; sys.path.insert(0, 'src')
from config import APIFY_API_TOKEN_BACKUP
from apify_client import ApifyClient

client = ApifyClient(token=APIFY_API_TOKEN_BACKUP)

PAGE_FN = """
async function pageFunction(context) {
    const { page } = context;
    await page.waitForTimeout(3000);
    const text = await page.evaluate(() => document.body.innerText);
    const m = text.match(/(\\d[\\d,.]*)\\s*(?:followers|likes|people like|people follow)/i);
    return { text: text.slice(0, 2000), match: m ? m[0] : null, title: document.title };
}
"""

run = client.actor('apify/web-scraper').call(run_input={
    'startUrls': [{'url': 'https://www.facebook.com/InstitutPlasticheskoyHirurgii'}],
    'pageFunction': PAGE_FN.strip(),
    'maxPagesPerCrawl': 1,
    'maxResultsPerCrawl': 1,
    'proxyConfiguration': {'useApifyProxy': True},
}, wait_secs=30)

items = client.dataset(run['defaultDatasetId']).list_items().items
if items:
    item = items[0]
    print('Title:', item.get('title'))
    print('Match:', item.get('match'))
    txt = (item.get('text') or '')[:500]
    # Ищем follower в тексте
    import re
    for m in re.finditer(r'.{0,60}follower.{0,60}', txt, re.I):
        print('FOUND:', m.group(0))
    for m in re.finditer(r'.{0,60}(?:like|fan|people).{0,60}', txt, re.I):
        print('LIKE:', m.group(0)[:100])
else:
    print('No items')
