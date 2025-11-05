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
Binance现货账户仓位管理示例

【中文说明】
此示例演示了如何在Binance现货账户中实现仓位管理策略，包括：
- 现货账户订单管理
- 实时仓位跟踪
- 止损机制
- 订单状态更新处理

【主要组件】
- OrderInfo: 订单信息数据结构
- PositionInfo: 仓位信息数据结构  
- SpotAccountPositionManager: 现货账户仓位管理器

【与回测版本的区别】
- 使用Binance现货账户API
- 支持实时订单状态更新
- 无自动借贷功能（现货账户不支持做空）

【使用场景】
- 实时交易系统
- 现货账户管理
- 风险控制
"""

from collections import defaultdict
from decimal import Decimal
from typing import cast, Dict, Optional
import asyncio
import copy
import dataclasses
import datetime
import logging

from basana.core.logs import StructuredMessage
from basana.external.binance import exchange, spot
import basana as bs


logger = logging.getLogger(__name__)


@dataclasses.dataclass
class OrderInfo:
    """
    【中文说明】
    订单信息数据类，用于跟踪和管理订单状态
    
    【功能描述】
    - 存储订单的基本信息：ID、操作类型、是否开放、已成交数量、成交价格
    - 提供从订单信息和订单更新中更新数据的方法
    
    【属性说明】
    - id: 订单唯一标识符
    - operation: 订单操作类型（买入/卖出）
    - is_open: 订单是否仍在开放状态
    - amount_filled: 已成交数量
    - fill_price: 成交价格（可能为None）
    """
    
    def update_from_order_info(self, order_info: spot.OrderInfo):
        """
        【中文说明】
        从订单信息对象更新当前订单信息
        
        【参数说明】
        - order_info: 从交易所获取的订单信息对象
        
        【功能描述】
        - 验证订单ID匹配
        - 更新订单状态、已成交数量和成交价格
        """
        assert order_info.id == self.id
        self.is_open = order_info.is_open
        self.amount_filled = order_info.amount_filled
        self.fill_price = order_info.fill_price

    def update_from_order_update(self, order_update: spot.OrderUpdate):
        """
        【中文说明】
        从订单更新事件更新当前订单信息
        
        【参数说明】
        - order_update: 订单更新事件对象
        
        【功能描述】
        - 验证订单ID匹配
        - 更新订单状态、已成交数量和成交价格
        """
        assert order_update.id == self.id
        self.is_open = order_update.is_open
        self.amount_filled = order_update.amount_filled
        self.fill_price = order_update.fill_price

    id: str
    operation: bs.OrderOperation
    is_open: bool
    amount_filled: Decimal
    fill_price: Optional[Decimal]


@dataclasses.dataclass
class PositionInfo:
    """
    【中文说明】
    仓位信息数据类，用于跟踪和管理交易对仓位状态
    
    【功能描述】
    - 存储仓位的当前状态、目标状态和订单信息
    - 计算当前仓位、平均价格和未实现盈亏
    - 提供仓位状态检查和目标达成判断
    
    【属性说明】
    - pair: 交易对
    - pair_info: 交易对精度信息
    - initial: 初始仓位数量
    - initial_avg_price: 初始平均价格
    - target: 目标仓位数量
    - order: 关联的订单信息
    """
    
    pair: bs.Pair
    pair_info: bs.PairInfo
    initial: Decimal
    initial_avg_price: Decimal
    target: Decimal
    order: OrderInfo

    def __post_init__(self):
        """
        【中文说明】
        数据类初始化后验证方法
        
        【功能描述】
        - 验证初始仓位和初始平均价格的一致性
        - 确保两者同时为0或同时不为0
        """
        # Both initial and initial_avg_price should be set to 0, or none of them.
        assert (self.initial == Decimal(0)) is (self.initial_avg_price == Decimal(0)), \
                f"initial={self.initial}, initial_avg_price={self.initial_avg_price}"

    @property
    def current(self) -> Decimal:
        """
        【中文说明】
        计算当前仓位数量
        
        【返回值】
        - 当前仓位数量（考虑订单成交情况）
        
        【计算逻辑】
        - 买入订单：初始仓位 + 已成交数量
        - 卖出订单：初始仓位 - 已成交数量
        """
        delta = self.order.amount_filled if self.order.operation == bs.OrderOperation.BUY else -self.order.amount_filled
        return self.initial + delta

    @property
    def avg_price(self) -> Decimal:
        """
        【中文说明】
        计算当前仓位的平均价格
        
        【返回值】
        - 当前仓位的平均价格
        
        【计算逻辑】
        - 仓位为0时返回0
        - 从空仓到持仓：使用订单成交价格
        - 从持仓到空仓：使用初始平均价格
        - 多空转换：根据当前仓位方向选择价格
        - 同向调整：加权平均计算新价格
        """
        # If the current position is 0, then the average price is 0.
        current = self.current
        if current == Decimal(0):
            return Decimal(0)

        # If the current position is not 0, then the order will have a fill price.
        order_fill_price = cast(Decimal, self.order.fill_price)

        # If we're going from a neutral position to a non-neutral position, the order fill price is returned.
        if self.initial == 0:
            ret = order_fill_price
        # If we are closing the position, going from a non-neutral position to a neutral position, the initial average
        # price is returned.
        elif self.target == 0:
            ret = self.initial_avg_price
        # Going from long to short, or the other way around.
        elif self.initial * self.target < 0:
            # If we are on the target side, the order fill price is returned.
            if current * self.target > 0:
                ret = order_fill_price
            # If we're still on the initial side, the initial average price is returned.
            else:
                ret = self.initial_avg_price
        # Rebalancing on the same side.
        else:
            assert self.initial * self.target > 0
            # Reducing the position.
            if self.target > 0 and self.order.operation == bs.OrderOperation.SELL \
                    or self.target < 0 and self.order.operation == bs.OrderOperation.BUY:
                ret = self.initial_avg_price
            # Increasing the position.
            else:
                ret = (abs(self.initial) * self.initial_avg_price + self.order.amount_filled * order_fill_price) \
                    / (abs(self.initial) + self.order.amount_filled)

        return ret

    @property
    def order_open(self) -> bool:
        """
        【中文说明】
        检查关联订单是否仍在开放状态
        
        【返回值】
        - 订单是否开放
        """
        return self.order.is_open

    @property
    def target_reached(self) -> bool:
        """
        【中文说明】
        检查是否已达到目标仓位
        
        【返回值】
        - 当前仓位是否等于目标仓位
        """
        return self.current == self.target

    def calculate_unrealized_pnl_pct(self, bid: Decimal, ask: Decimal) -> Decimal:
        """
        【中文说明】
        计算未实现盈亏百分比
        
        【参数说明】
        - bid: 当前买价
        - ask: 当前卖价
        
        【返回值】
        - 未实现盈亏百分比
        
        【计算逻辑】
        - 多头仓位：使用买价作为退出价格
        - 空头仓位：使用卖价作为退出价格
        - 盈亏 = (退出价格 - 平均价格) * 当前仓位
        - 盈亏百分比 = 盈亏 / (平均价格 * 当前仓位绝对值) * 100
        """
        pnl_pct = Decimal(0)
        current = self.current
        avg_price = self.avg_price
        if current and avg_price:
            exit_price = bid if current > 0 else ask
            pnl = (exit_price - avg_price) * current
            pnl_pct = pnl / abs(avg_price * current) * Decimal(100)
        return pnl_pct


class SpotAccountPositionManager:
    """
    【中文说明】
    Binance现货账户仓位管理器
    
    【功能描述】
    - 管理现货账户中的订单和仓位
    - 响应交易信号调整仓位
    - 实现止损机制
    - 跟踪订单状态更新
    
    【核心特性】
    - 多交易对仓位管理
    - 异步操作支持
    - 线程安全的仓位访问
    - 实时止损检查
    """
    
    def __init__(
            self, exchange: exchange.Exchange, position_amount: Decimal, quote_symbol: str,
            stop_loss_pct: Decimal, checkpoint_fname: str
    ):
        """
        【中文说明】
        初始化仓位管理器
        
        【参数说明】
        - exchange: Binance交易所实例
        - position_amount: 每个仓位的资金量（计价货币单位）
        - quote_symbol: 计价货币符号
        - stop_loss_pct: 止损百分比
        - checkpoint_fname: 检查点文件名
        
        【验证条件】
        - position_amount必须大于0
        - stop_loss_pct必须大于0
        """
        assert position_amount > 0
        assert stop_loss_pct > 0

        self._exchange = exchange
        self._position_amount = position_amount
        self._quote_symbol = quote_symbol
        self._positions: Dict[bs.Pair, PositionInfo] = {}
        self._pos_mutex: Dict[bs.Pair, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._stop_loss_pct = stop_loss_pct
        self._checkpoint_fname = checkpoint_fname
        self._last_check_loss: Optional[datetime.datetime] = None

    async def get_position_info(self, pair: bs.Pair) -> Optional[PositionInfo]:
        """
        【中文说明】
        获取指定交易对的仓位信息
        
        【参数说明】
        - pair: 交易对
        
        【返回值】
        - 仓位信息对象（如果存在），否则返回None
        
        【功能描述】
        - 线程安全地获取仓位信息
        - 如果订单仍在开放状态，从交易所获取最新订单信息
        - 返回深拷贝的仓位信息以避免并发修改
        """
        async with self._pos_mutex[pair]:
            pos_info = self._positions.get(pair)
            if pos_info and pos_info.order_open:
                order_info = await self._exchange.spot_account.get_order_info(pair, order_id=pos_info.order.id)
                pos_info.order.update_from_order_info(order_info)
            return copy.deepcopy(pos_info)

    async def check_loss(self):
        """
        【中文说明】
        检查所有非中性仓位的未实现盈亏并执行止损
        
        【功能描述】
        - 获取所有仓位的当前信息
        - 筛选出非中性仓位
        - 计算每个仓位的未实现盈亏百分比
        - 如果亏损超过止损阈值，强制平仓
        """
        positions = []
        coros = [self.get_position_info(pair) for pair in self._positions.keys()]
        if coros:
            positions.extend(await asyncio.gather(*coros))

        # Check unrealized PnL for all non-neutral positions.
        non_neutral = [pos_info for pos_info in positions if pos_info.current != Decimal(0)]
        if not non_neutral:
            return

        # Get bid and ask prices and calculate unrealized PnL.
        bids_and_asks = await asyncio.gather(*[self._exchange.get_bid_ask(pos_info.pair) for pos_info in non_neutral])
        for pos_info, (bid, ask) in zip(non_neutral, bids_and_asks):
            pnl_pct = pos_info.calculate_unrealized_pnl_pct(bid, ask)
            logger.info(StructuredMessage(
                f"Position for {pos_info.pair}", current=pos_info.current, target=pos_info.target,
                order_open=pos_info.order_open,
                avg_price=bs.round_decimal(pos_info.avg_price, pos_info.pair_info.quote_precision),
                pnl_pct=bs.round_decimal(pnl_pct, 2)
            ))
            if pnl_pct <= self._stop_loss_pct * -1:
                logger.info(f"Stop loss for {pos_info.pair}")
                await self.switch_position(pos_info.pair, bs.Position.NEUTRAL, force=True)

    async def switch_position(self, pair: bs.Pair, target_position: bs.Position, force: bool = False):
        """
        【中文说明】
        切换指定交易对的仓位到目标状态
        
        【参数说明】
        - pair: 交易对
        - target_position: 目标仓位状态（多头/空头/中性）
        - force: 是否强制切换（忽略当前状态）
        
        【功能描述】
        - 取消之前的开放订单
        - 计算目标仓位数量
        - 创建市价单调整仓位
        - 更新仓位跟踪信息
        """
        current_pos_info = await self.get_position_info(pair)

        # Unless force is set, we can ignore the request if we're already there.
        if not force and any([
                current_pos_info is None and target_position == bs.Position.NEUTRAL,
                (
                    current_pos_info is not None
                    and signed_to_position(current_pos_info.target) == target_position
                    and current_pos_info.target_reached
                )
        ]):
            return

        # Exclusive access to the position since we're going to modify it.
        async with self._pos_mutex[pair]:
            # Cancel the previous order.
            if current_pos_info and current_pos_info.order_open:
                logger.info(StructuredMessage("Canceling order", order_ids=current_pos_info.order.id))
                await self._exchange.spot_account.cancel_order(pair, order_id=current_pos_info.order.id)
                order_info = await self._exchange.spot_account.get_order_info(
                    pair, order_id=current_pos_info.order.id
                )
                current_pos_info.order.update_from_order_info(order_info)

            (bid, ask), pair_info = await asyncio.gather(
                self._exchange.get_bid_ask(pair),
                self._exchange.get_pair_info(pair),
            )

            # 1. Calculate the target balance.
            # If the target position is neutral, the target balance is 0, otherwise we need to convert
            # self._position_amount, which is expressed in self._quote_symbol units, into base units.
            if target_position == bs.Position.NEUTRAL:
                target = Decimal(0)
            else:
                if pair.quote_symbol == self._quote_symbol:
                    target = self._position_amount / ((bid + ask) / 2)
                else:
                    quote_bid, quote_ask = await self._exchange.get_bid_ask(
                        bs.Pair(pair.base_symbol, self._quote_symbol)
                    )
                    target = self._position_amount / ((quote_bid + quote_ask) / 2)

                if target_position == bs.Position.SHORT:
                    target *= -1
                target = bs.truncate_decimal(target, pair_info.base_precision)

            # 2. Calculate the difference between the target balance and our current balance.
            current = Decimal(0) if current_pos_info is None else current_pos_info.current
            delta = target - current
            logger.info(StructuredMessage("Switch position", pair=pair, current=current, target=target, delta=delta))
            if delta == 0:
                return

            # 3. Create the order.
            order_size = abs(delta)
            operation = bs.OrderOperation.BUY if delta > 0 else bs.OrderOperation.SELL
            logger.info(StructuredMessage(
                "Creating market order", operation=operation, pair=pair, order_size=order_size
            ))
            created_order = await self._exchange.spot_account.create_market_order(operation, pair, order_size)
            logger.info(StructuredMessage("Order created", id=created_order.id))
            order = await self._exchange.spot_account.get_order_info(pair, order_id=created_order.id)

            # 4. Keep track of the position.
            initial_avg_price = Decimal(0) if current_pos_info is None else current_pos_info.avg_price
            pos_info = PositionInfo(
                pair=pair, pair_info=pair_info, initial=current, initial_avg_price=initial_avg_price, target=target,
                order=OrderInfo(
                    id=order.id, operation=order.operation, is_open=order.is_open,
                    amount_filled=order.amount_filled, fill_price=order.fill_price,
                )
            )
            self._positions[pair] = pos_info

    async def on_trading_signal(self, trading_signal: bs.TradingSignal):
        """
        【中文说明】
        处理交易信号事件
        
        【参数说明】
        - trading_signal: 交易信号对象
        
        【功能描述】
        - 解析交易信号中的交易对和目标仓位
        - 现货账户不支持做空，将做空信号转换为中性
        - 异步切换所有交易对的仓位
        - 异常处理和日志记录
        """
        pairs = list(trading_signal.get_pairs())
        logger.info(StructuredMessage("Trading signal", pairs=pairs))

        try:
            coros = []
            for pair, target_position in pairs:
                # No borrowing with spot account.
                if target_position == bs.Position.SHORT:
                    target_position = bs.Position.NEUTRAL
                coros.append(self.switch_position(pair, target_position))
            await asyncio.gather(*coros)
        except Exception as e:
            logger.exception(e)

    async def on_bar_event(self, bar_event: bs.BarEvent):
        """
        【中文说明】
        处理K线事件
        
        【参数说明】
        - bar_event: K线事件对象
        
        【功能描述】
        - 记录K线收盘价
        - 定期检查止损（每个K线周期检查一次）
        """
        bar = bar_event.bar
        logger.info(StructuredMessage(bar.pair, close=bar.close))
        if self._last_check_loss is None or self._last_check_loss < bar_event.when:
            self._last_check_loss = bar_event.when
            await self.check_loss()

    async def on_order_event(self, order_event: spot.OrderEvent):
        """
        【中文说明】
        处理订单事件
        
        【参数说明】
        - order_event: 订单事件对象
        
        【功能描述】
        - 记录订单更新信息
        - 更新仓位信息中的订单状态
        - 确保订单成交数量只增不减
        """
        order_update = order_event.order_update
        pair = await self._exchange.symbol_to_pair(order_update.symbol)
        logger.info(StructuredMessage(
            "Order updated", id=order_update.id, pair=pair, is_open=order_update.is_open, amount=order_update.amount,
            amount_filled=order_update.amount_filled, avg_fill_price=order_update.fill_price
        ))

        # Update the position info.
        async with self._pos_mutex[pair]:
            pos_info = self._positions[pair]
            if order_update.id  == pos_info.order.id and order_update.amount_filled >= pos_info.order.amount_filled:
                pos_info.order.update_from_order_update(order_update)


def signed_to_position(signed):
    """
    【中文说明】
    将有符号数值转换为仓位状态
    
    【参数说明】
    - signed: 有符号数值（正数表示多头，负数表示空头，0表示中性）
    
    【返回值】
    - 对应的仓位状态枚举值
    
    【转换逻辑】
    - 正数 -> 多头
    - 负数 -> 空头
    - 零 -> 中性
    """
    if signed > 0:
        return bs.Position.LONG
    elif signed < 0:
        return bs.Position.SHORT
    else:
        return bs.Position.NEUTRAL
