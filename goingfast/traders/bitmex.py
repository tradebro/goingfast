from goingfast.traders.base import BaseTrader, Actions
from logging import Logger
from os import environ
from decimal import Decimal
import ujson

LEVERAGE = int(environ.get('LEVERAGE'))


class BitmexTrader(BaseTrader):
    __name__ = 'bitmex'
    symbol = 'XBTUSD'
    normalized_symbol = 'XBT/USD'

    def __init__(self, action: Actions, quantity: int, logger: Logger, metadata: dict = None):
        super().__init__(action, quantity, logger, metadata)

        self.leverage = LEVERAGE

    async def pre_entry(self):
        self.logger.debug('Got long entry command')

        self.logger.debug('Checking if there is a running position')
        has_position = await self.has_position()
        if has_position:
            self.logger.info('There is a running position, bailing..')
            raise AssertionError('Can only trade if there is no running position')

        self.logger.debug('Cancelling all orders')
        await self.cancel_all_orders()

        await self.set_leverage(leverage=self.leverage)

    async def long_entry(self):
        await self.pre_entry()

        self.logger.debug('Going to market buy to bybit')
        self.entry_order = await self.market_buy_order(quantity=self.quantity)
        self.logger.info(f'Successfully bought {self.quantity} contracts with order id: {self.entry_order.get("id")}')

        self.client.verbose = True

        await self.long_exit()

    async def long_exit(self):
        self.logger.debug('Got exit from long entry command')

        self.logger.debug('Going to send limit sell order')
        self.exit_order = await self.limit_sell_order(amount=self.quantity, price=self.tp_price)
        self.logger.info(
            f'Sucessfully sent limit sell order for {self.quantity} contracts '
            + f'at {self.tp_price} with order id: {self.exit_order.get("id")}'
        )

        self.logger.debug('Going to send stop limit sell order')
        self.exit_stop_limit_order = await self.limit_stop_sell_order(
            amount=self.quantity,
            stop_price=self.format_number(number=self.stop_limit_trigger_price, precision=0),
            stop_action_price=self.stop_limit_price,
        )
        self.logger.info(
            f'Successfully sent limit stop sell order for {self.quantity} contracts at trigger '
            + f'{self.stop_limit_trigger_price} selling at {self.stop_limit_price}'
        )

    async def short_entry(self):
        await self.pre_entry()

        self.logger.debug('Going to market sell to bybit')
        self.entry_order = await self.market_sell_order(quantity=self.quantity)
        self.logger.info(f'Successfully sold {self.quantity} contracts with order id: {self.entry_order.get("id")}')

        await self.short_exit()

    async def short_exit(self):
        self.logger.debug('Got exit from short entry command')

        self.logger.debug('Going to send limit buy order')
        self.exit_order = await self.limit_buy_order(amount=self.quantity, price=str(self.tp_price))
        self.logger.info(
            f'Sucessfully sent limit buy order for {self.quantity} contracts '
            + f'at {self.tp_price} with order id: {self.exit_order.get("id")}'
        )

        self.logger.debug('Going to send stop limit buy order')
        self.exit_stop_limit_order = await self.limit_stop_buy_order(
            amount=self.quantity, stop_price=self.stop_limit_trigger_price, stop_action_price=self.stop_limit_price
        )
        self.logger.info(
            f'Successfully sent limit buy sell order for {self.quantity} contracts at trigger '
            + f'{self.stop_limit_trigger_price} selling at {self.stop_limit_price}'
        )

    async def set_leverage(self, leverage: int):
        post_name = 'privatePostPositionLeverage'

        # Set Leverage
        self.logger.debug(f'Setting leverage to {self.leverage}x')
        method = getattr(self.client, post_name)
        response = method(params={'symbol': self.symbol, 'leverage': leverage})
        if response.get('ret_code') != 0 or response.get('ret_msg') != 'ok':
            raise AssertionError('Got error message while setting leverage')

        return response

    async def limit_order(self, side, amount, price, reduce_only: bool = True):
        method_name = 'privatePostOrder'

        method = getattr(self.client, method_name)
        order = method(
            params={
                'side': side,
                'symbol': self.symbol,
                'ordType': 'Limit',
                'orderQty': str(amount),
                'price': str(price),
                'timeInForce': 'GoodTillCancel',
                'execInst': 'ReduceOnly' if reduce_only else 'LastPrice',
            }
        )
        order.update({'id': order.get('orderID')})

        return order

    async def limit_buy_order(self, amount, price):
        return await self.limit_order(side='Buy', amount=amount, price=price)

    async def limit_sell_order(self, amount, price):
        return await self.limit_order(side='Sell', amount=amount, price=price)

    async def limit_stop_order(self, side, amount, stop_price, price):
        method_name = 'privatePostOrder'

        method = getattr(self.client, method_name)
        order = method(
            params={
                'side': side,
                'symbol': self.symbol,
                'ordType': 'StopLimit',
                'orderQty': str(amount),
                'price': str(price),
                'stopPx': stop_price,
                'timeInForce': 'GoodTillCancel',
                'execInst': 'ReduceOnly',
            }
        )
        order.update({'id': order.get('orderID')})

        return order

    async def limit_stop_sell_order(self, amount, stop_price, stop_action_price):
        return await self.limit_stop_order(side='Sell', amount=amount, stop_price=stop_price, price=stop_action_price)

    async def limit_stop_buy_order(self, amount, stop_price, stop_action_price):
        return await self.limit_stop_order(side='Buy', amount=amount, stop_price=stop_price, price=stop_action_price)

    async def market_stop_order(self, side, amount, stop_price):
        method_name = 'privatePostOrder'

        method = getattr(self.client, method_name)
        order = method(
            params={
                'side': side,
                'symbol': self.symbol,
                'ordType': 'Stop',
                'orderQty': str(amount),
                'stopPx': stop_price,
                'timeInForce': 'GoodTillCancel',
                'execInst': 'ReduceOnly',
            }
        )
        order.update({'id': order.get('orderID')})

        return order

    async def market_stop_buy_order(self, quantity, stop_price):
        return await self.market_stop_order(side='Buy', amount=quantity, stop_price=stop_price)

    async def market_stop_sell_order(self, quantity, stop_price):
        return await self.market_stop_order(side='Sell', amount=quantity, stop_price=stop_price)

    async def trailing_stop(self, side, trail_by, quantity):
        method_name = 'privatePostOrder'
        trail_by = Decimal(trail_by) if side == 'Sell' else Decimal(-1) * Decimal(trail_by)

        method = getattr(self.client, method_name)
        order = method(
            params={
                'side': side,
                'symbol': self.symbol,
                'ordType': 'MarketIfTouched',
                'pegPriceType': 'TrailingStopPeg',
                'pegOffsetValue': trail_by,
                'orderQty': quantity,
                'execInst': 'LastPrice',
            }
        )
        order.update({'id': order.get('orderID')})

        return order

    async def trailing_stop_buy(self, trail_by, quantity):
        return await self.trailing_stop(side='Buy', trail_by=trail_by, quantity=quantity)

    async def trailing_stop_sell(self, trail_by, quantity):
        return await self.trailing_stop(side='Sell', trail_by=trail_by, quantity=quantity)

    async def has_position(self):
        method_name = 'privateGetPosition'
        method = getattr(self.client, method_name)
        response = method(params={'filter': ujson.dumps({'filter': self.symbol})})

        return len(response) == 0

    async def cancel_all_orders(self):
        method_name = 'privateDeleteOrderAll'
        method = getattr(self.client, method_name)
        method(params={'symbol': self.symbol})
