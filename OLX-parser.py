import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import os
from telegram import Bot
from telegram import Update, InputMediaPhoto
from telegram.helpers import escape_markdown
import asyncio
import json
import logging

# Конфігурація
#SEARCH_URL = "https://www.olx.pl/elektronika/sprzet-audio/glosniki-i-kolumny/q-magnat/?courier=1"
HEADERS = {"User-Agent": "Mozilla/5.0"}
JSON_FILE = "olx_ads.json"
TOKEN = '7930055889:AAEG1rcIRftxKxzIRzqAxTj8TaWpd2c-fNQ'
CHAT_ID = '376481898'
bot = Bot(token=TOKEN)

filter = set()
filter.add("Na moich wystawionych pozostałych ogłoszeniach możesz kupić sprzęty typu:")

os.makedirs("logs", exist_ok=True)
log_file = os.path.join("logs", f"{datetime.now().strftime('%Y-%m-%d')}.log")

# Налаштування логування
logging.basicConfig(
    level=logging.INFO,  # Рівень логів (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    format="%(asctime)s - %(levelname)s - %(message)s",  # Формат повідомлення
    datefmt="%Y-%m-%d %H:%M:%S",  # Формат дати й часу
    handlers=[
        logging.StreamHandler(),  # Виведення в консоль
        logging.FileHandler(log_file, encoding="utf-8")  # Запис у файл
    ]
)

"""
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Привіт! Я OLX Бот 🛎️")
"""
async def load_old_ads():
    if os.path.exists(JSON_FILE):
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

async def save_ads(data):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

async def generate_html_from_json(json_path: str, html_output: str = "index.html"):
    with open(json_path, "r", encoding="utf-8") as f:
        ads = json.load(f)

    html_parts = ['<html><head><meta charset="utf-8"><title>OLX Ads</title>']
    html_parts.append("""
    <style>
        body { font-family: Arial; background: #f8f8f8; }
        .ad { background: white; margin: 10px auto; padding: 15px; border-radius: 10px; max-width: 800px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        .ad img { max-height: 200px; margin-right: 10px; border-radius: 5px; }
        .images { display: flex; overflow-x: auto; }
        .title { font-size: 20px; font-weight: bold; margin-bottom: 5px; color: black; }
        .title.removed { color: red; }
        .price { font-size: 22px; color: #e6c300; font-weight: bold; margin-bottom: 5px; }
        .meta { color: #666; margin-bottom: 5px; }
        .desc { margin-top: 10px; }
        .link { margin-top: 10px; display: inline-block; background: #007bff; color: white; padding: 8px 12px; border-radius: 5px; text-decoration: none; }
    </style>
    </head><body>
    <h2 style="text-align:center;">OLX Ads Preview</h2>
    """)

    for ad in ads:
        is_removed = ad.get("date_removed") is not None
        title_class = "title removed" if is_removed else "title"

        html_parts.append('<div class="ad">')
        html_parts.append(f'<div class="{title_class}">{ad.get("title", "Без назви")}</div>')
        html_parts.append(f'<div class="price">{ad.get("price", "")}</div>')
        html_parts.append(f'<div class="meta">{ad.get("location", "")} | Знайдено: {ad.get("published_date", "")}</div>')

        if "images" in ad:
            html_parts.append('<div class="images">')
            for img in ad["images"]:
                html_parts.append(f'<img src="{img}" loading="lazy">')
            html_parts.append('</div>')
        elif "image" in ad:
            html_parts.append(f'<img src="{ad["image"]}" loading="lazy">')

        if "description" in ad:
            html_parts.append(f'<div class="desc">{ad["description"]}</div>')

        html_parts.append(f'<a class="link" href="{ad.get("link", "#")}" target="_blank">Перейти на OLX</a>')
        html_parts.append('</div>')
    html_parts.append(f'<div class="time">{datetime.now().strftime("%Y-%m-%d ")}</div>')

    html_parts.append('</body></html>')

    with open(html_output, "w", encoding="utf-8") as f:
        f.write("".join(html_parts))

    #print(f"✅ HTML файл збережено: {html_output}")
    logging.info(f"✅ HTML файл збережено: {html_output}")

async def parse_ads(old_links):
    ads = []
    seen_links = set()
    last_page = set()
    this_page = set()
    page = 1
    itteration = 0
    while True:
        url = f"https://www.olx.pl/elektronika/sprzet-audio/glosniki-i-kolumny/q-magnat/?page={page}"
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select("div[data-cy='l-card']")
        
        if not cards:
            break

        new_ads = []
        for offer in cards:
            link_tag = offer.select_one("a.css-1tqlkj0")
            title_tag = offer.select_one("h4")
            price_tag = offer.select_one("p[data-testid='ad-price']")
            #await asyncio.sleep(0.1)  # 1 секунда між запитами
            itteration += 1
            if link_tag and title_tag:
                #print(f"{itteration}: {title_tag.get_text(strip=True)} ")
               
                relative_link = link_tag.get("href")
                link = "https://www.olx.pl" + relative_link
                
                if link in seen_links:
                    continue  # це вже було
                this_page.add(link)
                seen_links.add(link)
                
                if not link in old_links:
                    
                    ad = {
                        "title": title_tag.get_text(strip=True),
                        "link": link,
                        "price": price_tag.get_text(strip=True).replace("do negocjacji", "").strip() if price_tag else "",
                        "status": "active",
                        "date_found": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "date_removed": None
                    }
                    await parse_ad_details(ad)  # <- доповнюємо інформацію
                    if not any(f in ad["description"] for f in filter):
                        logging.info(f"NEW {ad}")
                        new_ads.append(ad)
                else:
                    #print(f"Пропускаємо {link} (вже в базі)")
                    continue
                
        """
        if not cards:
            print(f"No new ads on page {page}. Stopping.")
            break
        """
        last_page = this_page.copy()
        this_page.clear()
        
        if last_page == this_page:
            #print(f"Last page {page} is the same as this page. Stopping.")
            logging.info(f"Last page {page} is the same as this page. Stopping.")
            break
        
        ads.extend(new_ads)
        #print(f"Parsed page {page}, found {len(new_ads)} new ads.")
        if len(new_ads) > 0:
            logging.info(f"Parsed page {page}, found {len(new_ads)} new ads.")
        page += 1
        await asyncio.sleep(1)
        

    return ads

async def parse_ad_details(ad):
    response = requests.get(ad["link"], headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")

    # Опис
    desc_tag = soup.select_one("div[class='css-19duwlz']")
    ad["description"] = desc_tag.get_text(strip=True) if desc_tag else ""

     # Всі зображення з класу swiper-zoom-container
    image_urls = []
    for div in soup.select("div.swiper-zoom-container img"):
        src = div.get("src")
        if src and src.startswith("http"):
            image_urls.append(src)

    ad["images"] = image_urls
    
    # Дата публікації (іноді прихована)
    #posted_info = soup.find("span", string=re.compile(r"dnia"))
    posted_info = soup.select_one("span[class='css-1eaxltp']")
    if posted_info:
        posted_info = posted_info.get_text(strip=True)
        posted_info = posted_info.replace("Dodane", "").strip()
        if not posted_info.find("Dzisiaj"):
            posted_info = posted_info.replace("Dzisiaj", "").strip()
            posted_info = f"{datetime.now().strftime("%Y-%m-%d")} {posted_info}"
        ad["published_date"] = posted_info
        
    location_tag = soup.select_one("p[data-testid='location-date']")
    ad["location"] = location_tag.get_text(strip=True) if location_tag else ""

async def notify_new_ads(new_ads):
    await asyncio.sleep(1)
    for ad in new_ads:
        message = (
            f"🆕 *{ad['title']}*\n"
            f"💰 {ad['price']}\n"
            f"📍 {ad['location']}\n"
            f"🔗 [Перейти на OLX]({ad['link']})"
        )
        #message2 = (f"{ad['description'][:1021] + '...'}")
        message2 = escape_markdown(ad['description'][:1021] + '...', version=2)
        images = ad.get("images") or []
        if images:
            media_group = [InputMediaPhoto(media=img) for img in images[:10]]  # max 10
            try:
                await bot.send_media_group(chat_id=CHAT_ID, media=media_group)
            except Exception as e:
                #print(f"❌ Помилка надсилання фото: {e}")
                logging.error(f"❌ Помилка надсилання фото: {e}")
        
        # Надіслати окремо повідомлення з caption, оскільки caption в media_group показується лише до першої картинки
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode="Markdown", disable_web_page_preview=True)
        await bot.send_message(chat_id=CHAT_ID, text=message2, parse_mode="MarkdownV2", disable_web_page_preview=True) #MarkdownV2 - escape_markdown
        
        
async def main():
    old_ads = await load_old_ads()
    old_links = {ad["link"]: ad for ad in old_ads}
    old_titles = {ad["title"]: ad for ad in old_ads}
    #print(f"Found old {len(old_links)} ads.")
    logging.info(f"Found old {len(old_links)} ads.")
    current_ads = await parse_ads(old_links)
    #print(f"Found actual {len(current_ads)} ads.")
    logging.info(f"Found actual {len(current_ads)} ads.")
    current_links = {ad["link"] for ad in current_ads}
    today = datetime.now().strftime("%Y-%m-%d")

    updated_ads = []

    # Додаємо або оновлюємо активні оголошення
    for ad in current_ads:
        if (ad["link"] not in old_links) or (ad["title"] not in old_titles):
            logging.info(f"Додаємо {ad["link"]}.")
            ad["date_found"] = today
            ad["status"] = "active"
            ad["date_removed"] = None
            await notify_new_ads([ad])
            updated_ads.append(ad)
        else:
            existing = old_links[ad["link"]]
            ad["date_found"] = existing.get("date_found") or today
            ad["status"] = "active"
            ad["date_removed"] = None
            updated_ads.append(ad)

    # Позначаємо як неактивні ті, що зникли
    for link, ad in old_links.items():
        if link not in current_links:
            if ad.get("status") != "inactive":
                ad["status"] = "inactive"
                ad["date_removed"] = today
            updated_ads.append(ad)
              
    await save_ads(updated_ads)
    
    await generate_html_from_json("olx_ads.json")
    
"""
def main0():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    loop = asyncio.get_event_loop()
    loop.create_task(main())
    app.run_polling()
"""

if __name__ == "__main__":
    asyncio.run(main())
