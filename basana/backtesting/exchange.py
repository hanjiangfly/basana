# Basana
#
# Copyright 2022 Gabriel Martin Becedillas Ruiz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
回测交易所模块

实现回测交易所的核心功能，包括：
- 订单管理（市价单、限价单、止损单、止损限价单）
- 余额管理
- 借贷管理
- 价格管理
- 事件驱动模拟

支持基于K线数据的订单执行模拟。
"""

from collections import defaultdict
from decimal import Decimal
from typing import cast, Callable, Dict, List, Optional, Sequence, Tuple
import dataclasses
import logging
import uuid

from basana.backtesting import account_balances, config, errors, fees, lending, loan_mgr, liquidity, \
    orders, order_mgr, prices, requests
from basana.core import bar, dispatcher, enums, event, logs
from basana.core.pair import Pair, PairInfo
from basana.backtesting.lending import base as lending_base


logger = logging.getLogger(__name__)

# 类型别名定义
BarEventHandler = bar.BarEventHandler
Error = errors.Error
Fill = orders.Fill
LiquidityStrategyFactory = Callable[[], liquidity.LiquidityStrategy]
OrderEvent = order_mgr.OrderEvent
OrderEventHandler = order_mgr.OrderEventHandler
OrderInfo = orders.OrderInfo
OrderOperation = enums.OrderOperation


@dataclasses.dataclass
class Balance:
    """账户余额信息。

    :param available: 可用余额。
    :param hold: 冻结余额（为挂单预留）。
    :param borrowed: 借入余额。
    """
    #: 可用余额。
    available: Decimal
    #: 总余额（available + hold - borrowed）。
    total: Decimal = dataclasses.field(init=False)
    #: 冻结余额（为挂单预留）。
    hold: Decimal
    #: 借入余额。
    borrowed: Decimal

    def __post_init__(self):
        """初始化后计算总余额。"""
        self.total = self.available + self.hold - self.borrowed


class CreatedOrder(OrderInfo):
    """已创建订单信息。"""
    pass


@dataclasses.dataclass
class CanceledOrder:
    """已取消订单信息。

    :param id: 订单ID。
    """
    #: 订单ID。
    id: str


@dataclasses.dataclass
class OpenOrder:
    """挂单信息。

    :param id: 订单ID。
    :param operation: 订单操作类型。
    :param amount: 原始数量。
    :param amount_filled: 已成交数量。
    """
    #: 订单ID。
    id: str
    #: 订单操作类型。
    operation: OrderOperation
    #: 原始数量。
    amount: Decimal
    #: 已成交数量。
    amount_filled: Decimal


class Exchange:
    """回测交易所类。

    实现回测交易所，支持市价单、限价单、止损单和止损限价单，基于汇总交易活动（:class:`basana.BarEvent`）模拟订单执行。

    :param dispatcher: 事件分发器。
    :param initial_balances: 每个货币/符号等的初始余额。
    :param liquidity_strategy_factory: 返回新流动性策略的可调用对象。
    :param fee_strategy: 用于计算费用的策略。
    :param default_pair_info: 如果未使用 :meth:`Exchange.set_pair_info` 设置特定交易对信息时的默认交易对信息。
    :param bid_ask_spread: 用于 :meth:`Exchange.get_bid_ask` 的买卖价差。
    :param lending_strategy: 用于管理借贷的策略。
    :param immediate_order_processing: 如果为True，订单将在添加后立即处理，使用最后一个可用K线的收盘价。
        如果为False，订单将在下一个K线事件中处理。
    """
    def __init__(
            self,
            dispatcher: dispatcher.BacktestingDispatcher,
            initial_balances: Dict[str, Decimal],
            liquidity_strategy_factory: LiquidityStrategyFactory = liquidity.VolumeShareImpact,
            fee_strategy: fees.FeeStrategy = fees.NoFee(),
            default_pair_info: Optional[PairInfo] = PairInfo(base_precision=0, quote_precision=2),
            bid_ask_spread: Decimal = Decimal("0.5"),
            lending_strategy: lending.LendingStrategy = lending.NoLoans(),
            immediate_order_processing: bool = False
    ):
        self._dispatcher = dispatcher
        self._balances = account_balances.AccountBalances(initial_balances)
        self._bar_event_source: Dict[Pair, event.FifoQueueEventSource] = defaultdict(event.FifoQueueEventSource)
        self._config = config.Config(None, default_pair_info)
        self._prices = prices.Prices(bid_ask_spread, self._config)
        self._loan_mgr = loan_mgr.LoanManager(
            lending_strategy,
            lending_base.ExchangeContext(
                dispatcher=dispatcher,
                account_balances=self._balances,
                prices=self._prices,
                config=self._config
            )
        )
        self._order_mgr = order_mgr.OrderManager(
            order_mgr.ExchangeContext(
                dispatcher=dispatcher, account_balances=self._balances, prices=self._prices,
                fee_strategy=fee_strategy, liquidity_strategy_factory=liquidity_strategy_factory,
                loan_mgr=self._loan_mgr, config=self._config
            ),
            immediate_order_processing=immediate_order_processing
        )

    async def get_balance(self, symbol: str) -> Balance:
        """获取指定货币/符号等的余额。

        :param symbol: 货币/符号等。
        :return: 余额信息。
        """
        return self._get_balance(symbol)

    async def get_balances(self) -> Dict[str, Balance]:
        """获取所有余额。

        :return: 包含所有余额的字典。
        """
        ret = {}
        for symbol in self._balances.get_symbols():
            ret[symbol] = self._get_balance(symbol)
        return ret

    async def get_bid_ask(self, pair: Pair) -> Tuple[Decimal, Decimal]:
        """获取最新的买卖价格。

        使用最后一个K线的收盘价和初始化时指定的买卖价差计算。

        :param pair: 交易对。
        :return: 买卖价格元组（买价，卖价）。
        """
        return self._prices.get_bid_ask(pair)

    async def create_order(self, order_request: requests.ExchangeOrder) -> CreatedOrder:
        """创建订单。

        :param order_request: 订单请求对象。
        :return: 已创建的订单信息。
        :raises Error: 如果订单无法创建。
        """
        # 验证请求参数。
        pair_info = await self.get_pair_info(order_request.pair)
        order_request.validate(pair_info)

        order = order_request.create_order(uuid.uuid4().hex)
        self._order_mgr.add_order(order)
        logger.debug(logs.StructuredMessage("请求已接受", order_id=order.id))
        order_info = order.get_order_info()
        return CreatedOrder(
            id=order_info.id, pair=order_info.pair, is_open=order_info.is_open, operation=order_info.operation,
            amount=order_info.amount, amount_filled=order_info.amount_filled,
            amount_remaining=order_info.amount_remaining, quote_amount_filled=order_info.quote_amount_filled,
            fees=order_info.fees, limit_price=order_info.limit_price, stop_price=order_info.stop_price,
            loan_ids=order_info.loan_ids, fills=order_info.fills,
        )

    async def create_market_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, auto_borrow: bool = False,
            auto_repay: bool = False
    ) -> CreatedOrder:
        """
        Creates a market order.

        A market order is an order to immediately buy or sell at the best available price.
        Generally, this type of order will be executed on the next bar using the open price as a reference, and
        according to the rules defined by the liquidity strategy.
        If the order is not filled on the next bar, due to lack of liquidity or funds, the order will be canceled.

        If the order can't be created an :class:`Error` will be raised.

        :param operation: The order operation.
        :param pair: The pair to trade.
        :param amount: The base amount to buy/sell.
        :param auto_borrow: Automatically borrow missing funds.
        :param auto_repay: Automatically repay open loans once the order gets filled.
        """
        return await self.create_order(requests.MarketOrder(
            operation, pair, amount, auto_borrow=auto_borrow, auto_repay=auto_repay
        ))

    async def create_limit_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, limit_price: Decimal,
            auto_borrow: bool = False, auto_repay: bool = False
    ) -> CreatedOrder:
        """
        Creates a limit order.

        A limit order is an order to buy or sell at a specific price or better.
        A buy limit order can only be executed at the limit price or lower, and a sell limit order can only be executed
        at the limit price or higher.

        If the order can't be created an :class:`Error` will be raised.

        :param operation: The order operation.
        :param pair: The pair to trade.
        :param amount: The base amount to buy/sell.
        :param limit_price: The limit price.
        :param auto_borrow: Automatically borrow missing funds.
        :param auto_repay: Automatically repay open loans once the order gets filled.
        """
        return await self.create_order(requests.LimitOrder(
            operation, pair, amount, limit_price, auto_borrow=auto_borrow, auto_repay=auto_repay
        ))

    async def create_stop_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, stop_price: Decimal,
            auto_borrow: bool = False, auto_repay: bool = False
    ) -> CreatedOrder:
        """
        Creates a stop order.

        A stop order, also referred to as a stop-loss order, is an order to buy or sell once the price reaches a
        specified price, known as the stop price.
        When the stop price is reached, a stop order becomes a market order.

        * A buy stop order is entered at a stop price above the current market price. Investors generally use a buy
          stop order to limit a loss or to protect a profit on an instrument that they have sold short.
        * A sell stop order is entered at a stop price below the current market price. Investors generally use a sell
          stop order to limit a loss or to protect a profit on an instrument that they own.

        If the order can't be created an :class:`Error` will be raised.

        :param operation: The order operation.
        :param pair: The pair to trade.
        :param amount: The base amount to buy/sell.
        :param stop_price: The stop price.
        :param auto_borrow: Automatically borrow missing funds.
        :param auto_repay: Automatically repay open loans once the order gets filled.
        """
        return await self.create_order(requests.StopOrder(
            operation, pair, amount, stop_price, auto_borrow=auto_borrow, auto_repay=auto_repay
        ))

    async def create_stop_limit_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, stop_price: Decimal, limit_price: Decimal,
            auto_borrow: bool = False, auto_repay: bool = False
    ) -> CreatedOrder:
        """
        Creates a stop limit order.

        A stop-limit order is an order to buy or sell that combines the features of a stop order and a limit order.
        Once the stop price is reached, a stop-limit order becomes a limit order that will be executed at a specified
        price (or better).

        If the order can't be created an :class:`Error` will be raised.

        :param operation: The order operation.
        :param pair: The pair to trade.
        :param amount: The base amount to buy/sell.
        :param stop_price: The stop price.
        :param limit_price: The limit price.
        :param auto_borrow: Automatically borrow missing funds.
        :param auto_repay: Automatically repay open loans once the order gets filled.
        """
        return await self.create_order(requests.StopLimitOrder(
            operation, pair, amount, stop_price, limit_price, auto_borrow=auto_borrow, auto_repay=auto_repay
        ))

    async def cancel_order(self, order_id: str) -> CanceledOrder:
        """
        Cancels an order.

        If the order doesn't exist, or its not open, an :class:`Error` will be raised.

        :param order_id: The order id.
        """
        self._order_mgr.cancel_order(order_id)
        return CanceledOrder(id=order_id)

    async def get_order_info(self, order_id: str) -> OrderInfo:
        """
        Returns information about an order.

        If the order doesn't exist, or its not open, an :class:`Error` will be raised.

        :param order_id: The order id.
        """
        order = self._order_mgr.get_order(order_id)
        if not order:
            raise errors.NotFound("Order not found")
        return order.get_order_info()

    async def get_open_orders(self, pair: Optional[Pair] = None) -> List[OpenOrder]:
        """
        Returns open orders.

        :param pair: If set, only open orders matching this pair will be returned, otherwise all open orders will be
            returned.
        """
        return [
            OpenOrder(
                id=order.id,
                operation=order.operation,
                amount=order.amount,
                amount_filled=order.amount_filled
            )
            for order in self._order_mgr.get_open_orders()
            if pair is None or order.pair == pair
        ]

    async def get_orders(self, pair: Optional[Pair] = None, is_open: Optional[bool] = None) -> List[OrderInfo]:
        """
        Returns orders filtered by various conditions.

        :param pair: If set, only orders matching this pair will be returned.
        :param is_open: If set, only open or closed orders will be returned.
        """

        orders = self._order_mgr.get_all_orders()
        if pair:
            orders = filter(lambda order: order.pair == pair, orders)
        if is_open is not None:
            orders = filter(lambda order: order.is_open == is_open, orders)
        return [order.get_order_info() for order in orders]

    def add_bar_source(self, bar_source: event.EventSource):
        """
        Adds an event source that produces :class:`basana.BarEvent` instances.

        These will be used to drive the backtest.

        :param bar_source: An event source that produces :class:`basana.BarEvent` instances.
        """
        self._dispatcher.subscribe(bar_source, self._on_bar_event)

    def subscribe_to_bar_events(self, pair: Pair, event_handler: BarEventHandler):
        """
        Registers an async callable that will be called when a new bar is available.

        :param pair: The trading pair.
        :param event_handler: An async callable that receives a basana.BarEvent.
        """
        # Get/create the event source for the given pair.
        event_source = self._bar_event_source[pair]
        self._dispatcher.subscribe(event_source, cast(dispatcher.EventHandler, event_handler))

    def subscribe_to_order_events(self, event_handler: OrderEventHandler):
        """
        Registers an async callable that will be called when an order is accepted or updated.

        :param event_handler: The event handler.
        """
        self._order_mgr.subscribe_to_order_events(event_handler)

    async def get_pair_info(self, pair: Pair) -> PairInfo:
        """
        Returns information about a trading pair.

        :param pair: The trading pair.
        """
        return self._get_pair_info(pair)

    def set_pair_info(self, pair: Pair, pair_info: PairInfo):
        """
        Set information about a trading pair.

        :param pair: The trading pair.
        :param pair_info: The pair information.
        """
        self._config.set_pair_info(pair, pair_info)

    def set_symbol_precision(self, symbol: str, precision: int):
        """
        Set precision for a symbol.

        :param symbol: The symbol.
        :param precision: The precision.
        """
        self._config.set_symbol_info(symbol, config.SymbolInfo(precision=precision))

    async def create_loan(self, symbol: str, amount: Decimal) -> lending.LoanInfo:
        """
        Creates a loan.

        :param symbol: The symbol to borrow.
        :param amount: The amount to borrow.
        """

        return self._loan_mgr.create_loan(symbol, amount)

    async def get_loans(
            self, borrowed_symbol: Optional[str] = None, is_open: Optional[bool] = None
    ) -> List[lending.LoanInfo]:
        """
        Returns loans filtered by various conditions.

        :param borrowed_symbol: If set, only loans matching this borrowed symbol will be returned.
        :param is_open: If set, only open or closed loans will be returned.
        """
        return self._loan_mgr.get_loans(borrowed_symbol=borrowed_symbol, is_open=is_open)

    async def get_loan(self, loan_id: str) -> lending.LoanInfo:
        """
        Returns information about a loan.

        :param loan_id: The loan id.
        """
        loan_info = self._loan_mgr.get_loan(loan_id)
        if not loan_info:
            raise errors.NotFound("Loan not found")
        return loan_info

    async def repay_loan(self, loan_id: str):
        """
        Repays a loan fully.

        :param loan_id: The loan id.
        """
        return self._loan_mgr.repay_loan(loan_id)

    def _get_pair_info(self, pair: Pair) -> PairInfo:
        return self._config.get_pair_info(pair)

    async def _on_bar_event(self, event: event.Event):
        assert isinstance(event, bar.BarEvent), f"{event} is not an instance of bar.BarEvent"

        self._prices.on_bar_event(event)
        self._order_mgr.on_bar_event(event)

        # Forward the event if necessary.
        event_source = self._bar_event_source.get(event.bar.pair)
        if event_source:
            event_source.push(event)

    def _get_all_orders(self) -> Sequence[orders.Order]:
        return list(self._order_mgr.get_all_orders())

    def _get_dispatcher(self) -> dispatcher.BacktestingDispatcher:
        return self._dispatcher

    def _get_balance(self, symbol: str) -> Balance:
        available = self._balances.get_available_balance(symbol)
        hold = self._balances.get_balance_on_hold(symbol)
        borrowed = self._balances.get_borrowed_balance(symbol)
        return Balance(
            available=available, hold=hold, borrowed=borrowed
        )
