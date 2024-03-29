import logging

import pyfiglet
import ujson
from os import environ

from sanic import Sanic
from sanic.log import logger
from sanic.request import Request
from sanic.response import HTTPResponse, text

from goingfast.traders.base import Actions, BaseTrader
from goingfast.traders.binancefutures import BinanceFutures
from goingfast.traders.bybit import BybitTrader
from goingfast.traders.bitmex import BitmexTrader
from goingfast.notifications.telegram import send_telegram_message

APP_DEBUG = True if environ.get('APP_DEBUG') == '1' else False
log_level = logging.DEBUG if APP_DEBUG else logging.INFO
logger.setLevel(level=log_level)

TRADER = environ.get('TRADER')
CAPITAL_IN_USD = int(environ.get('CAPITAL_IN_USD'))


def is_valid_message(message: dict) -> bool:
    check = map(lambda x: x in message, ['close', 'indicator', 'exchange', 'pair', 'action'])

    return not (False in check)


def ok_response():
    return text('ok')


def show_config(trader: BaseTrader):
    title = pyfiglet.figlet_format('GoingFast')
    print(title)

    logger.debug(f'Trader: {trader.__name__.capitalize()}')
    logger.debug(f'Direction: {trader.action}')
    logger.debug(f'Quantity: {trader.quantity}')
    logger.debug(f'Stop Delta: {trader.stop_delta}')
    logger.debug(f'TP Delta: {trader.tp_delta}')
    logger.debug(f'Leverage: {trader.leverage}')
    logger.debug('\n---------------------------------\n')


async def trade(message):
    action = message.get('action').lower()
    if action != 'long' and action != 'short':
        raise NotImplementedError(f'Only Long and Short actions are supported, sent is: {action}')
    logger.debug(f'Trade direction is {action}')

    traders = {'bybit': BybitTrader, 'bitmex': BitmexTrader, 'binance-futures': BinanceFutures}
    trader_class = traders.get(TRADER)
    if not trader_class:
        raise NotImplementedError('Trader chosen is not implemented yet')
    logger.debug(f'Going to trade at {TRADER.capitalize()}')

    metadata = message.get('metadata')

    try:
        trader = trader_class(
            action=Actions.LONG if action == 'long' else Actions.SHORT,
            quantity=CAPITAL_IN_USD,
            logger=logger,
            metadata=metadata,
        )
    except NotImplementedError as e:
        logger.error(f'Exchange does not support the action: {action}')
        raise e

    show_config(trader=trader)

    try:
        if trader.action == Actions.LONG:
            await trader.long_entry()
        elif trader.action == Actions.SHORT:
            await trader.short_entry()
    except AssertionError as exc:
        logger.info(exc.args[0])
        logger.debug('There was no entry, bailing')
        return

    # Send Notification
    logger.debug('Sending notifications via Telegram')
    await send_telegram_message(trader=trader, tv_alert_message=message)


async def webhook_handler(request: Request) -> HTTPResponse:
    if APP_DEBUG:
        logger.debug('Request body below')
        print(request.body)

    text_body = request.body
    try:
        message = ujson.loads(text_body)
    except ValueError:
        logger.debug('Failed parsing the post body as JSON')
        message = None

    if not message or not is_valid_message(message=message):
        logger.debug('Not a valid message, ignoring..')
        return ok_response()

    logger.debug('Message is valid, starting to trade in the background')
    await request.app.add_task(trade(message=message))

    logger.debug('Sending response to client and closes connection')
    return ok_response()


def create_app():
    app = Sanic('GoingFast')

    app.add_route(webhook_handler, '/webhook', methods=['POST'])

    return app
