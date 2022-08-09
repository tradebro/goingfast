from os import environ
from string import Template
from goingfast.traders.base import BaseTrader
from sanic.log import logger
import telepot


TELEGRAM_TOKEN = environ.get('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = environ.get('TELEGRAM_CHAT_ID')
TEMPLATE = '''<b>GoingFast</b>

New trade has been executed. Details below.

Direction: <b>$action</b>

Indicator: $indicator
Exchange: $exchange
Pair: $pair
Last Close: $close

Trader: <b>$trader</b>

Quantity: $quantity
Entry Price: $entryprice
Stop Price: $stopprice
TP Price: $tpprice

Written with 💚
<a href="https://github.com/tradebro">TradeBro</a>'''


async def send_telegram_message(trader: BaseTrader, tv_alert_message: dict):
    if not TELEGRAM_TOKEN:
        logger.error('Required env var TELEGRAM_TOKEN must be set')
        return
    if not TELEGRAM_CHAT_ID:
        logger.error('Required env var TELEGRAM_CHAT_ID must be set')
        return

    stop_price = trader.stop_limit_trigger_price if not trader.stop_price else trader.stop_price

    values = {
        'action': tv_alert_message.get('action'),
        'indicator': tv_alert_message.get('indicator'),
        'exchange': tv_alert_message.get('exchange'),
        'pair': tv_alert_message.get('pair'),
        'close': str(tv_alert_message.get('close')),
        'trader': trader.__name__.capitalize(),
        'quantity': str(trader.quantity),
        'entryprice': str(trader.entry_price),
        'stopprice': str(stop_price),
        'tpprice': str(trader.tp_price),
    }

    template = Template(TEMPLATE)
    message_html = template.substitute(values)

    # Send message
    bot = telepot.Bot(token=TELEGRAM_TOKEN)
    bot.sendMessage(chat_id=TELEGRAM_CHAT_ID, text=message_html, parse_mode='HTML')
