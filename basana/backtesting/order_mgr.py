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
订单管理模块

提供回测系统中的订单管理功能，包括：
- 订单生命周期管理
- 订单处理与执行
- 余额和冻结管理
- 借贷和还款管理

支持即时订单处理和基于K线事件的订单处理。
"""

from collections import defaultdict
from decimal import Decimal
from typing import Any, Awaitable, cast, Callable, Dict, Generator, Iterable, List, Optional
import dataclasses
import datetime
import decimal
import logging

from basana.backtesting import account_balances, config, errors, fees, helpers, lending, loan_mgr, liquidity, prices
from basana.backtesting.orders import Order, OrderInfo
from basana.backtesting.value_map import ValueMap, ValueMapDict
from basana.core import dispatcher, helpers as core_helpers, logs
from basana.core.bar import Bar, BarEvent
from basana.core.enums import OrderOperation
from basana.core.pair import Pair
import basana as bs


logger = logging.getLogger(__name__)

# 类型别名定义
LiquidityStrategyFactory = Callable[[], liquidity.LiquidityStrategy]
OrderEventHandler = Callable[["OrderEvent"], Awaitable[Any]]


@dataclasses.dataclass
class ExchangeContext:
    """交易所上下文。

    提供对账户余额、价格、费用等不同服务的访问。

    :param dispatcher: 事件分发器。
    :param account_balances: 账户余额管理器。
    :param prices: 价格管理器。
    :param fee_strategy: 费用策略。
    :param liquidity_strategy_factory: 流动性策略工厂。
    :param loan_mgr: 借贷管理器。
    :param config: 配置管理器。
    """
    dispatcher: dispatcher.BacktestingDispatcher
    account_balances: account_balances.AccountBalances
    prices: prices.Prices
    fee_strategy: fees.FeeStrategy
    liquidity_strategy_factory: LiquidityStrategyFactory
    loan_mgr: loan_mgr.LoanManager
    config: config.Config


class OrderEvent(bs.Event):
    """订单更新事件。

    :param when: 事件时间。
    :param order: 订单信息。
    """

    def __init__(self, when: datetime.datetime, order: OrderInfo):
        super().__init__(when)
        #: 订单信息。
        self.order: OrderInfo = order


class OrderManager:
    """订单管理器。

    在回测环境中管理订单和完整生命周期。

    此类负责接受订单、根据K线事件处理订单以及管理冻结和余额更新。

    :param exchange_ctx: 交易所上下文，提供对账户余额、价格、费用等不同服务的访问。
    :param immediate_order_processing: 如果为True，订单将在添加后立即处理，使用最后一个可用K线的收盘价。
        如果为False，订单将在下一个K线事件中处理。
    """

    def __init__(self, exchange_ctx: ExchangeContext, immediate_order_processing: bool = False):
        self._ctx = exchange_ctx
        self._iop = immediate_order_processing
        self._liquidity_strategies: Dict[Pair, liquidity.LiquidityStrategy] = defaultdict(
            exchange_ctx.liquidity_strategy_factory
        )
        self._orders = helpers.ExchangeObjectContainer[Order]()
        self._holds_by_order: Dict[str, ValueMap] = {}
        self._order_updates = core_helpers.LazyProxy(bs.FifoQueueEventSource)

    def on_bar_event(self, bar_event: BarEvent):
        """处理K线事件。

        :param bar_event: K线事件。
        """
        liquidity_strategy = self._liquidity_strategies[bar_event.bar.pair]
        liquidity_strategy.on_bar(bar_event.bar)
        for order in filter(lambda o: o.pair == bar_event.bar.pair, self._orders.get_open()):
            self._process_order(order, bar_event.bar, liquidity_strategy)

    def add_order(self, order: Order):
        """添加订单。

        :param order: 订单对象。
        :raises errors.NotEnoughBalance: 如果余额不足。
        """
        try:
            # 在订单被接受之前，我们需要冻结订单成交时将扣除的任何所需余额。
            if required_balances := self._estimate_required_balances(order):
                if order.auto_borrow:
                    self._borrow(required_balances, order)
                self._ctx.account_balances.update(hold_updates=required_balances)
                self._holds_by_order[order.id] = required_balances

            # 订单已被接受。
            self._orders.add(order)
        except errors.NotEnoughBalance as e:
            logger.debug(logs.StructuredMessage(
                "余额不足无法接受订单", order=order.get_debug_info(), error=str(e)
            ))
            raise

        # 如果启用了即时订单处理，我们使用最后一个可用K线处理订单。
        # 否则，我们等待下一个K线事件。
        push_order_update = True
        if self._iop:
            try:
                last_bar = self._ctx.prices.get_last_bar(order.pair)
            except errors.NotFound:
                logger.debug(logs.StructuredMessage(
                    "即时订单处理无可用价格", order=order.get_debug_info()
                ))
                push_order_update = not self._order_not_filled(order)
            else:
                now = self._ctx.dispatcher.now()
                bar = Bar(
                    datetime=now, pair=order.pair,
                    open=last_bar.close, high=last_bar.close, low=last_bar.close, close=last_bar.close,
                    volume=last_bar.volume
                )
                liquidity_strategy = self._liquidity_strategies[order.pair]
                # 如果订单在处理期间未更新，我们为正在添加的订单推送更新。
                push_order_update = not self._process_order(order, bar, liquidity_strategy)

        if push_order_update:
            self._push_order_update(order)

    def get_order(self, order_id: str) -> Optional[Order]:
        """根据ID获取订单。

        :param order_id: 订单ID。
        :return: 订单对象，如果不存在则返回None。
        """
        return self._orders.get(order_id)

    def get_all_orders(self) -> Iterable[Order]:
        """获取所有订单。

        :return: 所有订单的可迭代集合。
        """
        return self._orders.get_all()

    def get_open_orders(self) -> Generator[Order, None, None]:
        """获取所有打开状态的订单。

        :return: 打开状态订单的生成器。
        """
        return self._orders.get_open()

    def cancel_order(self, order_id: str):
        """取消订单。

        :param order_id: 订单ID。
        :raises errors.Error: 如果订单不存在或无法取消。
        """
        order = self._orders.get(order_id)
        if order is None:
            raise errors.Error("订单未找到")
        if not order.is_open:
            raise errors.Error("订单 {} 处于 {} 状态，无法取消".format(order_id, order.state))
        order.cancel()
        self._order_closed(order)
        self._push_order_update(order)

    def subscribe_to_order_events(self, event_handler: OrderEventHandler):
        """注册订单事件处理程序。

        注册一个异步可调用对象，当订单更新时将被调用。

        :param event_handler: 事件处理程序。
        """
        self._ctx.dispatcher.subscribe(self._order_updates.obj, cast(dispatcher.EventHandler, event_handler))

    def _update_balances(self, order: Order, balance_updates: ValueMapDict):
        # If we have holds associated with the order, it may be time to release some/all of those.
        hold_updates = {}
        order_holds = self._holds_by_order.get(order.id, ValueMap())
        if order_holds:
            if order.is_open:
                hold_updates = {
                    symbol: max(amount, -order_holds.get(symbol, Decimal(0)))
                    for symbol, amount in balance_updates.items()
                    if amount < Decimal(0) and symbol in order_holds
                }
            else:
                hold_updates = {symbol: -amount for symbol, amount in order_holds.items()}

        # Update holds and balances.
        if balance_updates or hold_updates:
            self._ctx.account_balances.update(balance_updates=balance_updates, hold_updates=hold_updates)

        # Update holds by order.
        if order_holds:
            if order.is_open:
                order_holds += hold_updates
            else:
                del self._holds_by_order[order.id]

    def _borrow(self, required_balances: ValueMap, order: Order):
        post_hold = {
            symbol: self._ctx.account_balances.get_available_balance(symbol) - required_amount
            for symbol, required_amount in required_balances.items()
        }
        balances_short = {
            symbol: -amount for symbol, amount in post_hold.items() if amount < Decimal(0)
        }

        loan_ids: List[str] = []
        try:
            # Create a loan for every balance that we're short on.
            for symbol, amount in balances_short.items():
                logger.debug(logs.StructuredMessage(
                    "Borrowing for order", order_id=order.id, symbol=symbol, amount=amount
                ))
                loan = self._ctx.loan_mgr.create_loan(symbol, amount)
                loan_ids.append(loan.id)
        except Exception as e:
            logger.debug(logs.StructuredMessage(
                "Failed to borrow", order_id=order.id, symbol=symbol, amount=amount, error=str(e)
            ))
            # If there are any errors borrowing money we'll rollback everything before propagating the exception.
            for loan_id in loan_ids:
                logger.debug(logs.StructuredMessage("Canceling loan", order_id=order.id, loan_id=loan_id))
                self._ctx.loan_mgr.cancel_loan(loan_id)
            raise

        # Add loans to order.
        for loan_id in loan_ids:
            order.add_loan(loan_id)

    def _repay_loans(self, order: Order):
        if order.operation == OrderOperation.BUY:
            credit_symbol = order.pair.base_symbol
        else:
            credit_symbol = order.pair.quote_symbol

        candidate_loans = [
            loan for loan in self._ctx.loan_mgr.get_loans(is_open=True)
            if loan.borrowed_symbol == credit_symbol
        ]
        # Try to cancel bigger loans first.
        candidate_loans.sort(key=lambda loan: loan.borrowed_amount, reverse=True)
        loan_ids: List[str] = []
        for loan in candidate_loans:
            try:
                self._ctx.loan_mgr.repay_loan(loan.id)
                loan_ids.append(loan.id)
                loan = cast(lending.LoanInfo, self._ctx.loan_mgr.get_loan(loan.id))
                logger.debug(logs.StructuredMessage("Repayed loan", loan=dataclasses.asdict(loan)))
            except errors.NotEnoughBalance:
                pass

        # Add loans to order.
        for loan_id in loan_ids:
            order.add_loan(loan_id)

    def _order_closed(self, order: Order):
        # The order is closed and there might be balances on hold that have to be released.
        self._update_balances(order, {})
        # If the order has auto_repay set and is filled, either fully or partially, then we need to cancel matching open
        # loans
        if order.auto_repay and order.amount_filled:
            self._repay_loans(order)

    def _order_not_filled(self, order: Order) -> bool:
        assert order.is_open

        ret = False
        order.not_filled()
        logger.debug(logs.StructuredMessage("Order not filled", order_id=order.id, order_state=order.state))
        if not order.is_open:
            self._order_closed(order)
            self._push_order_update(order)
            ret = True
        return ret

    def _process_order(
            self, order: Order, bar: Bar, liquidity_strategy: liquidity.LiquidityStrategy
    ) -> bool:

        # Calculate balance updates for the current bar.
        logger.debug(logs.StructuredMessage(
            "Processing order", order=order.get_debug_info(),
            bar={"open": bar.open, "high": bar.high, "low": bar.low, "close": bar.close, "volume": bar.volume}
        ))
        prev_state = order.state
        balance_updates = ValueMap(order.get_balance_updates(bar, liquidity_strategy))
        assert order.state == prev_state, "The order state should not change inside get_balance_updates"
        self._round_balance_updates(balance_updates, order.pair)
        logger.debug(logs.StructuredMessage(
            "Order balance updates", order_id=order.id, balance_updates=balance_updates
        ))
        # Base and quote symbols must be present in the balance updates, otherwise the order can't be filled.
        if order.pair.base_symbol not in balance_updates or order.pair.quote_symbol not in balance_updates:
            return self._order_not_filled(order)

        # Get fees, round them, and combine them with the balance updates.
        fees = ValueMap(self._ctx.fee_strategy.calculate_fees(order, balance_updates))
        self._round_fees(fees, order.pair)
        logger.debug(logs.StructuredMessage(
            "Order fees", order_id=order.id, fees=fees
        ))

        ret = False
        try:
            # Update balances. This may fail if there is not enough balance, so we do this first.
            final_updates = balance_updates + fees
            final_updates.prune()
            self._update_balances(order, final_updates)
            # Update the liquidity strategy.
            liquidity_strategy.take_liquidity(abs(balance_updates[bar.pair.base_symbol]))
            # Update the order and release any pending balance on hold if the order is now closed.
            order.add_fill(self._ctx.dispatcher.now(), balance_updates, fees)
            logger.debug(logs.StructuredMessage(
                "Order updated", order_id=order.id, final_updates=final_updates, order_state=order.state
            ))
            if not order.is_open:
                self._order_closed(order)
            self._push_order_update(order)
            ret = True

        except errors.NotEnoughBalance as e:
            logger.debug(logs.StructuredMessage(
                "Balance short processing order", order=order.get_debug_info(), error=str(e)
            ))
            ret = self._order_not_filled(order)
        return ret

    def _round_balance_updates(self, balance_updates: ValueMap, pair: Pair):
        pair_info = self._ctx.config.get_pair_info(pair)

        # For the base amount we truncate instead of rounding to avoid exceeding available liquidity.
        if (base_amount := balance_updates.get(pair.base_symbol)) is not None:
            balance_updates[pair.base_symbol] = core_helpers.truncate_decimal(base_amount, pair_info.base_precision)

        # For the quote amount we simply round.
        if (quote_amount := balance_updates.get(pair.quote_symbol)) is not None:
            balance_updates[pair.quote_symbol] = core_helpers.round_decimal(quote_amount, pair_info.quote_precision)

        balance_updates.prune()

    def _round_fees(self, fees: ValueMap, pair: Pair):
        pair_info = self._ctx.config.get_pair_info(pair)
        precisions = {
            pair.base_symbol: pair_info.base_precision,
            pair.quote_symbol: pair_info.quote_precision,
        }
        for symbol, precision in precisions.items():
            if (amount := fees.get(symbol)) is not None:
                fees[symbol] = core_helpers.round_decimal(amount, precision, rounding=decimal.ROUND_UP)

        fees.prune()

    def _estimate_required_balances(self, order: Order) -> ValueMap:
        # Get an estimated fill price. If the order can't provide one, use the last price available.
        estimated_fill_price = order.calculate_estimated_fill_price()
        if not estimated_fill_price:
            try:
                estimated_fill_price = self._ctx.prices.get_last_price(order.pair)
            except errors.NotFound:
                pass

        # Build a dictionary of balance updates suitable for calculating fees.
        base_sign = helpers.get_base_sign_for_operation(order.operation)
        estimated_balance_updates = ValueMap({
            order.pair.base_symbol: order.amount * base_sign
        })
        if estimated_fill_price:
            estimated_balance_updates[order.pair.quote_symbol] = order.amount * estimated_fill_price * -base_sign
        self._round_balance_updates(estimated_balance_updates, order.pair)

        # Calculate fees.
        fees = ValueMap()
        if len(estimated_balance_updates) == 2:
            fees += self._ctx.fee_strategy.calculate_fees(order, estimated_balance_updates)
            self._round_fees(fees, order.pair)
        estimated_balance_updates += fees

        # Return only negative balance updates as required balances.
        return ValueMap({
            symbol: -amount for symbol, amount in estimated_balance_updates.items()
            if amount < Decimal(0)
        })

    def _push_order_update(self, order: Order):
        # Checking dispatcher.now_available is necessary to avoid calling dispatcher.now() when no events have been
        # processed yet.
        now = self._ctx.dispatcher.now() if self._ctx.dispatcher.now_available else None
        if now and self._order_updates.initialized:
            self._order_updates.push(OrderEvent(now, order.get_order_info()))
