"""Быстрая проверка NO_DATA профилей — парсинг с правильным regex."""
import re

samples = {
    "ИнститутПластики": "1,3 тыс. — подписчики • 0 — подписки",
    "ВсеСвои": "7,2 тыс. — подписчики • 0 — подписки",
    "Кристина": "62 тыс. — подписчики • 0 — подписки",
    "Лондон": "Pfp Property\nЕщё\nФото\nПодробнее",
    "ЛондонРУС": "Pfp London\nЕщё\nФото\nПодробнее",
    "Сюсан": '2,9 тыс. — "Нравится" • 2,9 тыс. — подписчики',
    "/": "1 подписчик • 0 — подписки",
    "Айфоника": "1 подписчик • 0 — подписки",
}

def normalize_count(s):
    s = s.replace('\u00a0', ' ').strip()
    # Убираем завершающую точку если есть
    s = s.rstrip('.')
    # "1,3 тыс" → 1300
    if 'тыс' in s or 'k' in s.lower():
        s = s.replace('тыс.', '').replace('тыс', '').replace('k', '').replace('K', '').strip()
        return int(float(s.replace(',', '.')) * 1000)
    if 'млн' in s or 'm' in s.lower():
        s = s.replace('млн', '').replace('m', '').replace('M', '').strip()
        return int(float(s.replace(',', '.')) * 1000000)
    return int(float(s.replace(',', '.')))

def parse_fb_followers(text):
    text = text.replace('\u00a0', ' ')
    
    # Паттерн: число+тыс — подписчики  OR  число — подписчики
    pat = r'([\d ,]+(?:\s*тыс\.?)?)\s*[—–-]\s*подписчик'
    m = re.search(pat, text, re.I)
    if m:
        return normalize_count(m.group(1))
    return None

for name, text in samples.items():
    result = parse_fb_followers(text)
    print(f"{name:20} → {result}")
