from goingfast.traders.base import BaseTrader, Actions
from logging import Logger
from os import environ
from decimal import Decimal

LEVERAGE = int(environ.get('LEVERAGE'))


class BybitTrader(BaseTrader):
    __name__ = 'bybit'
    symbol = 'BTCUSD'
    normalized_symbol = 'BTC/USD'

    def __init__(self, action: Actions, quantity: int, logger: Logger, metadata: dict = None):
        super().__init__(action, quantity, logger, metadata)

        self.leverage = LEVERAGE

    @property
    def trailing_stop_trigger_price(self):
        if self.metadata and self.metadata.get('trailing_stop_trigger_price'):
            return Decimal(self.metadata.get('trailing_stop_trigger_price'))

        return self.entry_price + Decimal(30)

    @property
    def trailing_stop_by(self):
        if self.metadata and self.metadata.get('trailing_stop_by'):
            return Decimal(self.metadata.get('trailing_stop_by'))

        return None

    async def pre_entry(self):
        self.logger.debug('Got long entry command')

        self.logger.debug('Checking if there is a running position')
        has_position = await self.has_position()
        if has_position:
            self.logger.info('There is a running position, bailing..')
            raise AssertionError('Can only trade if there is no running position')

        self.logger.debug('Cancelling all orders')
        await self.cancel_all_orders()

        self.logger.debug('Cancelling all stop orders')
        await self.cancel_all_stop_orders()

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
        self.exit_order = await self.limit_sell_order(amount=self.quantity,
                                                      price=self.tp_price)
        self.logger.info(f'Sucessfully sent limit sell order for {self.quantity} contracts ' +
                         f'at {self.tp_price} with order id: {self.exit_order.get("id")}')

        self.logger.debug('Going to send stop limit sell order')
        self.exit_stop_limit_order = await self.limit_stop_sell_order(amount=self.quantity,
                                                                      stop_price=self.format_number(
                                                                          number=self.stop_limit_trigger_price,
                                                                          precision=0),
                                                                      stop_action_price=self.stop_limit_price)
        self.logger.info(f'Successfully sent limit stop sell order for {self.quantity} contracts at trigger ' +
                         f'{self.stop_limit_trigger_price} selling at {self.stop_limit_price}')

        use_trailing_stop = self.trailing_stop_by is not None
        if use_trailing_stop:
            self.logger.info('Trailing stop variables are set, going to send trailing stop order')
            await self.trailing_stop(trail_by=self.trailing_stop_by,
                                     activation_price=self.trailing_stop_trigger_price)
            self.logger.debug('Trailing stop order sent')

    async def short_entry(self):
        await self.pre_entry()

        self.logger.debug('Going to market sell to bybit')
        self.entry_order = await self.market_sell_order(quantity=self.quantity)
        self.logger.info(f'Successfully sold {self.quantity} contracts with order id: {self.entry_order.get("id")}')

        await self.short_exit()

    async def short_exit(self):
        self.logger.debug('Got exit from short entry command')

        self.logger.debug('Going to send limit buy order')
        self.exit_order = await self.limit_buy_order(amount=self.quantity,
                                                     price=str(self.tp_price))
        self.logger.info(f'Sucessfully sent limit buy order for {self.quantity} contracts ' +
                         f'at {self.tp_price} with order id: {self.exit_order.get("id")}')

        self.logger.debug('Going to send stop limit buy order')
        self.exit_stop_limit_order = await self.limit_stop_buy_order(amount=self.quantity,
                                                                     stop_price=self.stop_limit_trigger_price,
                                                                     stop_action_price=self.stop_limit_price)
        self.logger.info(f'Successfully sent limit buy sell order for {self.quantity} contracts at trigger ' +
                         f'{self.stop_limit_trigger_price} selling at {self.stop_limit_price}')

        use_trailing_stop = self.trailing_stop_by is not None
        if use_trailing_stop:
            self.logger.info('Trailing stop variables are set, going to send trailing stop order')
            await self.trailing_stop(trail_by=self.trailing_stop_by,
                                     activation_price=self.trailing_stop_trigger_price)
            self.logger.debug('Trailing stop order sent')

    async def set_leverage(self, leverage: int):
        post_name = 'userPostLeverageSave'
        get_name = 'userGetLeverage'

        # Get Leverage
        self.logger.debug('Checking current leverage')
        method = getattr(self.client, get_name)
        response = method()
        if int(response.get('result').get(self.symbol).get('leverage')) == leverage:
            self.logger.debug(f'Current leverage is just as configured: {self.leverage}x')
            return response

        # Set Leverage
        self.logger.debug(f'Setting leverage to {self.leverage}x')
        method = getattr(self.client, post_name)
        response = method(params={
            'symbol': self.symbol,
            'leverage': leverage,
        })
        if response.get('ret_code') != 0 or response.get('ret_msg') != 'ok':
            raise AssertionError('Got error message while setting leverage')

        return response

    async def limit_order(self, side, amount, price, reduce_only: bool = True):
        method_name = 'privatePostOrderCreate'

        method = getattr(self.client, method_name)
        order = method(params={
            'side': side,
            'symbol': self.symbol,
            'order_type': 'Limit',
            'qty': str(amount),
            'price': str(price),
            'time_in_force': 'GoodTillCancel',
            'reduce_only': reduce_only
        })
        order.update({
            'id': order.get('result').get('stop_order_id'),
            'price': order.get('result').get('price')
        })

        return order

    async def limit_buy_order(self, amount, price):
        return await self.limit_order(side='Buy',
                                      amount=amount,
                                      price=price)

    async def limit_sell_order(self, amount, price):
        return await self.limit_order(side='Sell',
                                      amount=amount,
                                      price=price)

    async def limit_stop_order(self, side, amount, stop_price, price):
        method_name = 'openapiPostStopOrderCreate'

        method = getattr(self.client, method_name)
        order = method(params={
            'side': side,
            'symbol': self.symbol,
            'order_type': 'Limit',
            'qty': str(amount),
            'price': str(price),
            'stop_px': str(stop_price),
            'base_price': str(self.entry_price),
            'close_on_trigger': True,
            'time_in_force': 'GoodTillCancel'
        })
        order.update({
            'id': order.get('result').get('stop_order_id'),
            'price': order.get('result').get('price')
        })

        return order

    async def limit_stop_sell_order(self, amount, stop_price, stop_action_price):
        return await self.limit_stop_order(side='Sell',
                                           amount=amount,
                                           stop_price=stop_price,
                                           price=stop_action_price)

    async def limit_stop_buy_order(self, amount, stop_price, stop_action_price):
        return await self.limit_stop_order(side='Buy',
                                           amount=amount,
                                           stop_price=stop_price,
                                           price=stop_action_price)

    async def trailing_stop(self, trail_by, activation_price):
        method_name = 'privateLinear_post_position_trading_stop'
        method = getattr(self.client, method_name)
        order = method(params={
            'symbol': self.symbol,
            'trailing_stop': trail_by,
            'new_trailing_active': activation_price
        })

        return order

    async def has_position(self):
        method_name = 'private_get_position_list'
        method = getattr(self.client, method_name)
        response = method(params={
            'symbol': self.symbol
        })
        position_info = response.get('result')
        if not position_info:
            return False

        side = position_info.get('side')

        return side != 'None'

    async def cancel_all_stop_orders(self):
        method_name = 'privatePostStopOrderCancelAll'
        method = getattr(self.client, method_name)
        method(params={
            'symbol': self.symbol
        })

    async def cancel_all_orders(self):
        method_name = 'privatePostOrderCancelAll'
        method = getattr(self.client, method_name)
        method(params={
            'symbol': self.symbol
        })
