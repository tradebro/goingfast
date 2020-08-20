from goingfast.traders.base import BaseTrader
from os import environ

LEVERAGE = int(environ.get('LEVERAGE'))


class BybitTrader(BaseTrader):
    __name__ = 'bybit'
    symbol = 'BTCUSD'
    normalized_symbol = 'BTC/USD'

    async def long_entry(self):
        self.logger.debug('Got long entry command')
        await self.set_leverage(leverage=LEVERAGE)

        self.logger.debug('Going to market buy to bybit')
        self.entry_order = await self.market_buy_order(quantity=self.quantity)
        self.logger.info(f'Successfully bought {self.quantity} contracts with order id: {self.entry_order.get("id")}')

        await self.long_exit()

    async def long_exit(self):
        self.logger.debug('Got exit from long entry command')

        self.logger.debug('Going to send limit sell order')
        self.exit_order = await self.limit_sell_order(amount=self.quantity,
                                                      price=self.tp_price)
        self.logger.info(f'Sucessfully sent limit sell order for {self.quantity} contracts ' +
                         f'at {self.tp_price} with order id: {self.exit_order}')

        self.logger.debug('Going to send stop limit sell order')
        self.exit_stop_limit_order = await self.limit_stop_sell_order(amount=self.quantity,
                                                                      stop_price=self.stop_limit_trigger_price,
                                                                      stop_action_price=self.stop_limit_price)
        self.logger.info(f'Successfully sent limit stop sell order for {self.quantity} contracts at trigger ' +
                         f'{self.stop_limit_trigger_price} selling at {self.stop_limit_price}')

    async def short_entry(self):
        self.logger.debug('Got short entry command')
        await self.set_leverage(leverage=LEVERAGE)

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
                         f'at {self.tp_price} with order id: {self.exit_order}')

        self.logger.debug('Going to send stop limit buy order')
        self.exit_stop_limit_order = await self.limit_stop_buy_order(amount=self.quantity,
                                                                     stop_price=self.stop_limit_trigger_price,
                                                                     stop_action_price=self.stop_limit_price)
        self.logger.info(f'Successfully sent limit buy sell order for {self.quantity} contracts at trigger ' +
                         f'{self.stop_limit_trigger_price} selling at {self.stop_limit_price}')

    async def set_leverage(self, leverage: int):
        post_name = 'userPostLeverageSave'
        get_name = 'userGetLeverage'

        # Get Leverage
        self.logger.debug('Checking current leverage')
        method = getattr(self.client, get_name)
        response = method()
        if int(response.get('result').get(self.symbol).get('leverage')) == leverage:
            self.logger.debug(f'Current leverage is just as configured: {LEVERAGE}x')
            return response

        # Set Leverage
        self.logger.debug(f'Setting leverage to {LEVERAGE}x')
        method = getattr(self.client, post_name)
        response = method(params={
            'symbol': self.symbol,
            'leverage': leverage,
        })
        if response.get('ret_code') != 0 or response.get('ret_msg') != 'ok':
            raise AssertionError('Got error message while setting leverage')

        return response

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
