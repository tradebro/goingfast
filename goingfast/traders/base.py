from abc import abstractmethod
from decimal import Decimal
from os import environ
from logging import Logger
import enum
import ccxt

STOP_DELTA = Decimal(environ.get('STOP_DELTA'))
TP_DELTA = Decimal(environ.get('TP_DELTA'))
API_KEY = environ.get('API_KEY')
API_SECRET = environ.get('API_SECRET')


class Actions(enum.Enum):
    LONG = 'long'
    SHORT = 'short'


class BaseTrader:
    __name__ = 'base'
    symbol = ''

    def __init__(self, action: Actions, quantity: int, logger: Logger):
        self.action = action
        self.quantity = quantity
        self.logger = logger

        self.entry_order = dict()
        self.exit_order = dict()
        self.exit_stop_limit_order = dict()
        self.exit_stop_market_order = dict()

    @property
    def entry_price(self) -> Decimal:
        if not self.entry_order:
            return Decimal(0)
        return Decimal(self.entry_order.get('price'))

    @property
    def stop_limit_trigger_price(self) -> Decimal:
        if self.action == Actions.LONG:
            return self.entry_price - STOP_DELTA
        elif self.action == Actions.SHORT:
            return self.entry_price + STOP_DELTA
        else:
            return Decimal(0)

    @property
    def stop_limit_price(self) -> Decimal:
        if self.action == Actions.LONG:
            return self.stop_limit_trigger_price - Decimal(5)
        elif self.action == Actions.SHORT:
            return self.stop_limit_trigger_price + Decimal(5)
        else:
            return Decimal(0)

    @property
    def stop_market_price(self) -> Decimal:
        if self.action == Actions.LONG:
            return self.stop_limit_trigger_price - Decimal(10)
        elif self.action == Actions.SHORT:
            return self.stop_limit_trigger_price + Decimal(10)
        else:
            return Decimal(0)

    @property
    def tp_price(self):
        if self.action == Actions.LONG:
            return self.entry_price + TP_DELTA
        elif self.action == Actions.SHORT:
            return self.entry_price - TP_DELTA
        else:
            return Decimal(0)

    @property
    def client(self):
        exc_class = getattr(ccxt, self.__name__)
        if not exc_class:
            raise NotImplementedError('This exchange is not implemented yet')

        return exc_class({
            'apiKey': API_KEY,
            'secret': API_SECRET,
            'timeout': 30000,
            'enableRateLimit': True,
        })

    @abstractmethod
    async def long_entry(self):
        raise NotImplementedError()

    @abstractmethod
    async def long_exit(self):
        raise NotImplementedError()

    @abstractmethod
    async def short_entry(self):
        raise NotImplementedError()

    @abstractmethod
    async def short_exit(self):
        raise NotImplementedError()

    async def market_buy_order(self, quantity):
        if not self.client.has['createMarketOrder']:
            raise AttributeError('The selected exchange does not support market orders')
        order = self.client.create_market_buy_order(symbol=self.symbol,
                                                    amount=quantity)
        return order

    async def market_sell_order(self, quantity):
        if not self.client.has['createMarketOrder']:
            raise AttributeError('The selected exchange does not support market orders')
        order = self.client.create_market_sell_order(symbol=self.symbol,
                                                     amount=quantity)
        return order

    async def limit_buy_order(self, amount, price):
        order = self.client.create_order(symbol=self.symbol,
                                         type='limit',
                                         side='buy',
                                         amount=amount,
                                         price=price)
        return order

    async def limit_sell_order(self, amount, price):
        order = self.client.create_order(symbol=self.symbol,
                                         type='limit',
                                         side='sell',
                                         amount=amount,
                                         price=price)
        return order

    @staticmethod
    def format_number(number, precision: int = 2) -> str:
        return '{:0.0{}f}'.format(number, precision)
