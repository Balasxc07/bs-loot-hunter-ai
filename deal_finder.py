import os
import json
import hashlib
import urllib.request
import urllib.parse
from datetime import datetime, timezone

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

FEED_URLS = [
    url.strip()
    for url in os.environ.get("DEAL_FEED_URLS", "").split(",")
    if url.strip()
]

MIN_DISCOUNT = 50
HISTORY_FILE = "price_history.json"


def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": "false"
    }).encode()

    request = urllib.request.Request(url, data=payload)

    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError("Telegram notification failed")


def load_history():
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, indent=2)


def fetch_feed(feed_url):
    request = urllib.request.Request(
        feed_url,
        headers={"User-Agent": "BS-Loot-Hunter-AI/1.0"}
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        data = json.loads(response.read().decode("utf-8"))

    if isinstance(data, list):
        return data

    if isinstance(data, dict):
        products = data.get("products", [])
        return products if isinstance(products, list) else []

    return []


def product_id(product):
    identity = (
        str(product.get("url", ""))
        or str(product.get("name", ""))
    )

    return hashlib.sha256(identity.encode()).hexdigest()[:20]


def process_product(product, history):
    name = str(product.get("name", "Unknown product"))
    url = str(product.get("url", ""))
    category = str(product.get("category", "General"))

    try:
        price = float(product["price"])
        mrp = float(product["mrp"])
    except (KeyError, TypeError, ValueError):
        return

    if price <= 0 or mrp <= 0 or price > mrp:
        return

    discount = round((mrp - price) / mrp * 100, 2)
    if discount < MIN_DISCOUNT:
        return

    key = product_id(product)
    previous = history.get(key)
    old_price = previous.get("price") if previous else None

    is_new = previous is None
    price_dropped = old_price is not None and price < float(old_price)

    history[key] = {
        "name": name,
        "price": price,
        "mrp": mrp,
        "url": url,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    if not is_new and not price_dropped:
        return

    priority = "🔥 MEGA LOOT — 90%+ OFF!" if discount >= 90 else "💥 DEAL ALERT!"

    message = (
        f"{priority}\n\n"
        f"🛍️ {name}\n"
        f"📂 Category: {category}\n"
        f"💰 Price: ₹{price:,.2f}\n"
        f"🏷️ Listed MRP: ₹{mrp:,.2f}\n"
        f"📉 Discount: {discount}% OFF\n"
    )

    if price_dropped:
        message += f"⬇️ Previous tracked price: ₹{float(old_price):,.2f}\n"

    message += f"\n🔗 Buy/check deal: {url}\n\n🤖 BS LOOT HUNTER AI"

    send_telegram(message)


def main():
    history = load_history()

    if not FEED_URLS:
        print("No permitted deal feeds configured yet.")
        return

    for feed_url in FEED_URLS:
        try:
            products = fetch_feed(feed_url)
            print(f"Read {len(products)} products from a configured feed.")

            for product in products:
                if isinstance(product, dict):
                    try:
                        process_product(product, history)
                    except Exception as error:
                        print(f"Product processing error: {error}")

        except Exception as error:
            print(f"Feed could not be read: {error}")

    save_history(history)


if __name__ == "__main__":
    main()
