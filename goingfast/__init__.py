import logging
from os import environ

from sanic import Sanic
from sanic.log import logger
from sanic.request import Request
from sanic.response import HTTPResponse, text

from goingfast.traders.base import Actions
from goingfast.traders.bybit import BybitTrader

APP_DEBUG = True if environ.get('APP_DEBUG') == '1' else False
log_level = logging.DEBUG if APP_DEBUG else logging.INFO
logger.setLevel(level=log_level)

TRADER = environ.get('TRADER')
CAPITAL_IN_USD = int(environ.get('CAPITAL_IN_USD'))


def is_valid_message(message: dict) -> bool:
    check = map(lambda x: x in message, [
        'close',
        'indicator',
        'exchange',
        'pair',
        'action'
    ])

    return not (False in check)


def ok_response():
    return text('ok')


async def trade(message):
    action = message.get('action').lower()
    if action != 'long' and action != 'short':
        raise NotImplementedError(f'Only Long and Short actions are supported, sent is: {action}')
    logger.debug(f'Trade direction is {action}')

    traders = {
        'bybit': BybitTrader
    }
    trader_class = traders.get(TRADER)
    if not trader_class:
        raise NotImplementedError('Trader chosen is not implemented yet')
    logger.debug(f'Going to trade at {TRADER.capitalize()}')

    trader = trader_class(action=Actions.LONG if action == 'long' else Actions.SHORT,
                          quantity=CAPITAL_IN_USD,
                          logger=logger)

    if action == Actions.LONG:
        await trader.long_entry()
    elif action == Actions.SHORT:
        await trader.short_entry()

    return trader


async def webhook_handler(request: Request) -> HTTPResponse:
    message = request.json
    if not message or not is_valid_message(message=message):
        logger.debug('Not a valid message, ignoring..')
        return ok_response()

    logger.debug('Message is valid, starting to trade in the background')
    request.app.add_task(trade(message=message))

    logger.debug('Sending response to client and closes connection')
    return ok_response()


def create_app():
    app = Sanic('GoingFast')

    app.add_route(webhook_handler, '/webhook', methods=['POST'])

    return app
