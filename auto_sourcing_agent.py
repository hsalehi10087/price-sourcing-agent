import os
from datetime import datetime
import requests

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

USD_TO_TOMAN = float(os.getenv("USD_TO_TOMAN", "271650"))
MIN_PROFIT_MARGIN_PCT = float(os.getenv("MIN_PROFIT_MARGIN_PCT", "20.0"))

SEARCH_QUERIES = [
    {"query": "compact cordless desk vacuum", "extra_cost_usd": 5.0, "markup_factor": 1.45},
    {"query": "magnetic cable clips desk organizer", "extra_cost_usd": 3.0, "markup_factor": 1.55},
    {"query": "collapsible silicone travel container", "extra_cost_usd": 4.0, "markup_factor": 1.50},
]


def parse_usd_price(price_str: str | None) -> float | None:
    if not price_str:
        return None
    cleaned = "".join(ch for ch in str(price_str) if ch.isdigit() or ch == ".")
    try:
        val = float(cleaned)
        return val if val > 0 else None
    except ValueError:
        return None


def discover_products(query: str, api_key: str) -> list[dict]:
    """یافتن محصولات از طریق Google Shopping (SerpApi)."""
    if not api_key:
        return []
    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": api_key,
    }
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("shopping_results", [])[:5]


def analyze_item(item: dict, extra_cost_usd: float, markup_factor: float) -> dict | None:
    buy_usd = parse_usd_price(item.get("extracted_price") or item.get("price"))
    if buy_usd is None:
        return None

    sell_usd = round(buy_usd * markup_factor, 2)
    total_cost_usd = buy_usd + extra_cost_usd
    net_profit_usd = sell_usd - total_cost_usd
    margin_pct = (net_profit_usd / sell_usd) * 100 if sell_usd > 0 else 0.0

    return {
        "title": item.get("title", "محصول بدون عنوان"),
        "source": item.get("source", "نامشخص"),
        "buy_toman": buy_usd * USD_TO_TOMAN,
        "cost_toman": total_cost_usd * USD_TO_TOMAN,
        "sell_toman": sell_usd * USD_TO_TOMAN,
        "profit_toman": net_profit_usd * USD_TO_TOMAN,
        "margin_pct": margin_pct,
        "link": item.get("link", ""),
    }


def build_telegram_report(opportunities: list[dict]) -> str:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"🤖 *گزارش خودکار کشف کالا و سود* (`{now_str}`)", ""]

    if not opportunities:
        lines.append("ℹ️ امروز کالایی با حاشیه سود بالای آستانه تعیین‌شده پیدا نشد.")
        return "\n".join(lines)

    for idx, item in enumerate(opportunities[:8], start=1):
        lines.append(
            f"{idx}. *{item['title']}*\n"
            f"   منبع: {item['source']}\n"
            f"   بهای تمام‌شده تخمینی: `{item['cost_toman']:,.0f}` تومان\n"
            f"   قیمت فروش هدف: `{item['sell_toman']:,.0f}` تومان\n"
            f"   سود خالص تخمینی: `{item['profit_toman']:,.0f}` تومان (`{item['margin_pct']:.1f}%`)"
        )
    return "\n".join(lines)


def send_telegram(text: str) -> bool:
    if not BOT_TOKEN or not CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
    }
    resp = requests.post(url, json=payload, timeout=15)
    return resp.status_code == 200


def main() -> None:
    if not SERPAPI_KEY:
        send_telegram("⚠️ کلید `SERPAPI_KEY` تنظیم نشده است؛ برای کشف خودکار کالاها این متغیر را در محیط اجرا قرار دهید.")
        return

    found = []
    for cfg in SEARCH_QUERIES:
        raw_items = discover_products(cfg["query"], SERPAPI_KEY)
        for raw in raw_items:
            analyzed = analyze_item(raw, cfg["extra_cost_usd"], cfg["markup_factor"])
            if analyzed and analyzed["margin_pct"] >= MIN_PROFIT_MARGIN_PCT:
                found.append(analyzed)

    found.sort(key=lambda x: x["profit_toman"], reverse=True)
    report = build_telegram_report(found)
    send_telegram(report)


if __name__ == "__main__":
    main()
