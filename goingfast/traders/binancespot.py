from goingfast.traders.base import BaseTrader, Actions
from logging import Logger


class BinanceSpot(BaseTrader):
    __name__ = 'binance'

    def __init__(self, action: Actions, quantity: int, logger: Logger):
        if action == Actions.SHORT:
            raise NotImplementedError('Unable to short in spot trading')

        super().__init__(action, quantity, logger)

    async def long_entry(self):
        pass

    async def long_exit(self):
        pass

    async def short_entry(self):
        raise NotImplementedError('Unable to short in spot trading')

    async def short_exit(self):
        raise NotImplementedError('Unable to short in spot trading')
