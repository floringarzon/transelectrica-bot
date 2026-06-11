import asyncio
import logging
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional
from telegram import Bot
from telegram.error import TelegramError

# ── Configuration ────────────────────────────────────────────────────────────
BOT_TOKEN = "8655900763:AAFMAcyi7j_5DVg4k1Cwrxpf2fq1JwlyOfw"
CHAT_ID   = "8954542030"

CHECK_INTERVAL_SECONDS = 60  # verifica la fiecare 1 minut
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


def fetch_latest_price() -> Optional[dict]:
    try:
        now = datetime.now(timezone.utc)
        time_from = now.strftime("%Y-%m-%dT00:00:00.000Z")
        time_to = (now + timedelta(days=1)).strftime("%Y-%m-%dT00:00:00.000Z")

        url = (
            "https://newmarkets.transelectrica.ro"
            "/usy-durom-publicreportg01/00121002500000000000000000000100"
            "/publicReport/estimatedImbalancePrices"
        )
        params = {
            "timeInterval.from": time_from,
            "timeInterval.to": time_to,
            "pageInfo.pageSize": 3000,
        }
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

        response = requests.get(url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        records = None
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            for key in ["data", "rows", "result", "items", "records", "pageEntries"]:
                if key in data and isinstance(data[key], list):
                    records = data[key]
                    break
            if not records:
                for value in data.values():
                    if isinstance(value, list) and len(value) > 0:
                        records = value
                        break

        if not records:
            return None

        for record in reversed(records):
            pos = record.get("estimatedPricePositiveImbalance")
            neg = record.get("estimatedPriceNegativeImbalance")
            if pos not in (None, "N/A") or neg not in (None, "N/A"):
                return record

        return None

    except Exception as e:
        log.error("Eroare la fetch: %s", e)
        return None


def get_interval_id(record: dict) -> str:
    interval = record.get("timeInterval", {})
    return "{}-{}".format(interval.get("from", ""), interval.get("to", ""))


def format_message(record: dict) -> str:
    now = datetime.now().strftime("%d.%m.%Y %H:%M")

    interval = record.get("timeInterval", {})
    time_from = interval.get("from", "N/A")
    time_to = interval.get("to", "N/A")

    try:
        dt_from = datetime.fromisoformat(time_from.replace("Z", "+00:00")) + timedelta(hours=3)
        dt_to = datetime.fromisoformat(time_to.replace("Z", "+00:00")) + timedelta(hours=3)
        interval_str = "{} - {}".format(dt_from.strftime("%H:%M"), dt_to.strftime("%H:%M"))
    except Exception:
        interval_str = "{} - {}".format(time_from, time_to)

    pos = record.get("estimatedPricePositiveImbalance", "N/A")
    neg = record.get("estimatedPriceNegativeImbalance", "N/A")

    return (
        "Pret dezechilibru estimat\n"
        "Interval: {}\n"
        "Pret pozitiv: {} RON/MWh\n"
        "Pret negativ: {} RON/MWh\n"
        "Actualizat: {}"
    ).format(interval_str, pos, neg, now)


async def send_telegram(bot: Bot, message: str) -> None:
    try:
        await bot.send_message(chat_id=CHAT_ID, text=message)
        log.info("Mesaj Telegram trimis.")
    except TelegramError as e:
        log.error("Eroare Telegram: %s", e)


async def main() -> None:
    bot = Bot(token=BOT_TOKEN)
    log.info("Bot pornit. Verific la fiecare %d secunde.", CHECK_INTERVAL_SECONDS)
    await send_telegram(bot, "Bot pornit! Voi trimite mesaj de fiecare data cand apare un interval nou.")

    last_interval_id = None

    while True:
        record = fetch_latest_price()
        if record:
            interval_id = get_interval_id(record)
            if interval_id != last_interval_id:
                log.info("Interval nou: %s", interval_id)
                msg = format_message(record)
                await send_telegram(bot, msg)
                last_interval_id = interval_id
            else:
                log.info("Acelasi interval, nu trimit.")
        
        await asyncio.sleep(CHECK_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
