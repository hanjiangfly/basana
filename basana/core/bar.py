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

from decimal import Decimal
from typing import Any, Awaitable, Callable, List, Optional, Tuple
import asyncio
import datetime
import logging

from basana.core import dt, event, logs, pair


# 日志记录器，用于记录K线相关的操作和错误
logger = logging.getLogger(__name__)


class InvalidBar(Exception):
    """
    【中文说明】无效K线异常
    
    【功能描述】
    当K线数据不符合有效性规则时抛出的异常。
    用于标识K线数据中的逻辑错误，如价格关系不合理等。
    
    【触发条件】
    - 最高价低于最低价
    - 最高价低于开盘价
    - 最高价低于收盘价
    - 最低价高于开盘价
    - 最低价高于收盘价
    
    【使用场景】
    - K线数据验证
    - 数据质量检查
    - 防止错误数据进入交易系统
    
    【注意事项】
    - 继承自标准Exception类
    - 包含具体的错误信息描述
    """
    pass


class Bar:
    """
    【中文说明】K线柱（蜡烛图/OHLC）类
    
    【功能描述】
    K线柱（也称为蜡烛图或OHLC）是在给定时间段内交易活动的摘要。
    包含开盘价、最高价、最低价、收盘价和成交量等关键交易信息。
    
    【核心属性】
    - datetime: 时间段的开始时间，必须包含时区信息
    - pair: 交易对
    - open: 开盘价
    - high: 最高价
    - low: 最低价
    - close: 收盘价
    - volume: 成交量
    
    【价格关系验证】
    - 最高价 >= 最低价
    - 最高价 >= 开盘价
    - 最高价 >= 收盘价
    - 最低价 <= 开盘价
    - 最低价 <= 收盘价
    
    【使用场景】
    - 技术分析图表绘制
    - 交易策略回测
    - 市场数据分析和可视化
    
    【注意事项】
    - 时间必须包含时区信息
    - 价格关系必须符合逻辑规则
    - 使用Decimal类型确保精度

    A Bar, also known as candlestick or OHLC, is the summary of the trading activity in a given period.

    :param datetime: The beginning of the period. It must have timezone information set.
    :param pair: The trading pair.
    :param open: The opening price.
    :param high: The highest traded price.
    :param low: The lowest traded price.
    :param close: The closing price.
    :param volume: The volume traded.
    """

    def __init__(
            self, datetime: datetime.datetime, pair: pair.Pair,
            open: Decimal, high: Decimal, low: Decimal, close: Decimal, volume: Decimal
    ):
        """
        【中文说明】初始化K线柱对象
        
        【功能描述】
        创建K线柱实例，验证价格关系的有效性，并设置所有属性。
        
        【参数说明】
        - datetime: datetime.datetime - 时间段的开始时间，必须包含时区信息
        - pair: pair.Pair - 交易对
        - open: Decimal - 开盘价
        - high: Decimal - 最高价
        - low: Decimal - 最低价
        - close: Decimal - 收盘价
        - volume: Decimal - 成交量
        
        【验证逻辑】
        检查价格关系的逻辑一致性，确保：
        - 最高价 >= 最低价
        - 最高价 >= 开盘价
        - 最高价 >= 收盘价
        - 最低价 <= 开盘价
        - 最低价 <= 收盘价
        
        【异常情况】
        - 如果价格关系不符合逻辑，抛出InvalidBar异常
        
        【注意事项】
        - 所有价格验证失败都会抛出异常
        - 使用Decimal类型确保计算精度
        """
        # 验证最高价不能低于最低价
        if high < low:
            raise InvalidBar(f"high < low on {datetime}")
        # 验证最高价不能低于开盘价
        elif high < open:
            raise InvalidBar(f"high < open on {datetime}")
        # 验证最高价不能低于收盘价
        elif high < close:
            raise InvalidBar(f"high < close on {datetime}")
        # 验证最低价不能高于开盘价
        elif low > open:
            raise InvalidBar(f"low > open on {datetime}")
        # 验证最低价不能高于收盘价
        elif low > close:
            raise InvalidBar(f"low > close on {datetime}")

        #: 时间段的开始时间
        self.datetime = datetime
        #: 交易对
        self.pair = pair
        #: 开盘价
        self.open = open
        #: 最高价
        self.high = high
        #: 最低价
        self.low = low
        #: 收盘价
        self.close = close
        #: 成交量
        self.volume = volume


class BarEvent(event.Event):
    """
    【中文说明】K线事件类
    
    【功能描述】
    封装K线柱的事件类，用于在事件驱动系统中传递K线数据。
    继承自Event基类，包含事件发生时间和对应的K线柱数据。
    
    【核心属性】
    - when: 事件发生的时间，必须包含时区信息
    - bar: 关联的K线柱对象
    
    【架构角色】
    - 在事件驱动架构中作为K线数据的载体
    - 与事件分发器（EventDispatcher）协同工作
    - 支持K线数据的异步处理
    
    【使用场景】
    - 实时K线数据推送
    - 技术指标计算
    - 交易策略执行
    
    【注意事项】
    - 时间必须包含时区信息
    - bar属性包含完整的K线数据

    An event for :class:`Bar` instances.

    :param when: The datetime when the event occurred. It must have timezone information set.
    :param bar: The bar.
    """

    def __init__(self, when: datetime.datetime, bar: Bar):
        """
        【中文说明】初始化K线事件对象
        
        【功能描述】
        创建K线事件实例，设置事件时间和关联的K线柱。
        
        【参数说明】
        - when: datetime.datetime - 事件发生的时间，必须包含时区信息
        - bar: Bar - 关联的K线柱对象
        
        【内部操作】
        - 调用父类Event的初始化方法设置时间
        - 设置bar属性引用K线柱对象
        
        【注意事项】
        - 时间必须包含时区信息
        - bar对象应该包含有效的K线数据
        """
        # 调用父类初始化方法设置事件时间
        super().__init__(when)

        #: 关联的K线柱对象
        self.bar = bar


class RealTimeTradesToBar(event.FifoQueueEventSource, event.Producer):
    """
    【中文说明】实时交易转K线生成器
    
    【功能描述】
    将实时交易数据转换为K线柱的事件源和生产者。
    接收实时交易数据，按时间窗口聚合交易信息，生成对应的K线柱事件。
    
    【核心功能】
    - 接收实时交易数据（时间、价格、数量）
    - 按固定时间窗口聚合交易数据
    - 计算每个时间窗口的OHLC（开盘、最高、最低、收盘）和成交量
    - 生成K线事件并推送到事件队列
    
    【参数说明】
    - pair: pair.Pair - 交易对
    - bar_duration: int - K线时间窗口长度（秒）
    - skip_first_bar: bool - 是否跳过第一个不完整的K线（默认True）
    - flush_delay: float - 刷新延迟时间（秒），用于确保窗口内所有交易都被处理
    
    【内部状态】
    - _trades: 存储待处理的交易数据列表
    - _next_trade_ge: 下一个交易的最小时间限制
    - _skip_first_bar: 是否跳过第一个K线的标志
    
    【使用场景】
    - 实时交易数据转换为K线数据
    - 实时技术分析
    - 实时交易策略执行

    Converts real-time trades to bars.
    """

    def __init__(self, pair: pair.Pair, bar_duration: int, skip_first_bar: bool = True, flush_delay: float = 0.5):
        """
        【中文说明】初始化实时交易转K线生成器
        
        【功能描述】
        创建实时交易转K线生成器实例，设置交易对、K线时长等参数。
        
        【参数说明】
        - pair: pair.Pair - 交易对
        - bar_duration: int - K线时间窗口长度（秒），必须大于0
        - skip_first_bar: bool - 是否跳过第一个不完整的K线，默认True
        - flush_delay: float - 刷新延迟时间（秒），必须大于等于0
        
        【验证检查】
        - bar_duration必须大于0
        - flush_delay必须大于等于0
        
        【内部初始化】
        - 设置交易对和K线参数
        - 初始化交易数据存储列表
        - 设置时间顺序验证标志
        """
        # 验证K线时长必须大于0
        assert bar_duration > 0
        # 验证刷新延迟必须大于等于0
        assert flush_delay >= 0
        # 调用父类初始化，设置生产者为自己
        super().__init__(producer=self)
        # 交易对
        self._pair = pair
        # K线时间窗口长度（秒）
        self._bar_duration = bar_duration
        # 交易数据存储列表：每个元素为(时间, 价格, 数量)的元组
        self._trades: List[Tuple[datetime.datetime, Decimal, Decimal]] = []
        # 是否跳过第一个不完整K线的标志
        self._skip_first_bar = skip_first_bar
        # 下一个交易的最小时间限制，用于验证交易顺序
        self._next_trade_ge: Optional[datetime.datetime] = None
        # 刷新延迟时间（秒）
        self._flush_delay = flush_delay

    def on_error(self, error: Any):
        """
        【中文说明】错误处理回调
        
        【功能描述】
        处理在K线生成过程中发生的错误。
        
        【参数说明】
        - error: Any - 错误对象，可以是异常或其他错误信息
        
        【使用场景】
        - 交易数据顺序错误
        - K线生成过程中的其他异常
        
        【注意事项】
        - 使用日志记录错误信息
        - 不会中断K线生成过程
        """
        # 记录错误信息到日志
        logger.error(error)

    def push_trade(self, when: datetime.datetime, price: Decimal, amount: Decimal):
        """
        【中文说明】推送交易数据
        
        【功能描述】
        接收新的交易数据，验证时间顺序，并将其添加到待处理交易列表中。
        
        【参数说明】
        - when: datetime.datetime - 交易发生时间
        - price: Decimal - 交易价格
        - amount: Decimal - 交易数量
        
        【验证逻辑】
        - 检查交易时间是否按顺序到达
        - 如果交易时间早于预期的最小时间，记录错误并忽略该交易
        
        【内部操作】
        - 验证交易时间顺序
        - 将交易数据添加到_trades列表
        - 更新_next_trade_ge时间限制
        
        【注意事项】
        - 交易应该按时间顺序到达
        - 无序交易会被记录错误但不会导致异常
        """
        # 交易必须按时间顺序到达
        # 检查交易时间是否早于预期的最小时间
        if self._next_trade_ge and when < self._next_trade_ge:
            # 记录交易顺序错误
            self.on_error(logs.StructuredMessage(
                "Trade pushed out of order", last=self._next_trade_ge, current=when, pair=self._pair
            ))
            return

        # 将交易数据添加到待处理列表
        self._trades.append((when, price, amount))
        # 更新下一个交易的最小时间限制
        self._next_trade_ge = when

    def _flush(self, begin: datetime.datetime, end: datetime.datetime):
        """
        【中文说明】刷新当前时间窗口的交易数据
        
        【功能描述】
        处理指定时间窗口内的所有交易数据，计算OHLC和成交量，生成K线事件。
        
        【参数说明】
        - begin: datetime.datetime - 时间窗口的开始时间
        - end: datetime.datetime - 时间窗口的结束时间
        
        【算法逻辑】
        1. 遍历所有交易数据，过滤出在[begin, end]时间窗口内的交易
        2. 计算该窗口的开盘价、最高价、最低价、收盘价和总成交量
        3. 如果窗口内有交易且不跳过第一个K线，则生成K线事件
        4. 清理已处理的交易数据，保留未来窗口的交易
        
        【内部操作】
        - 更新_next_trade_ge时间限制
        - 计算OHLC价格和成交量
        - 生成并推送K线事件
        - 清理已处理的交易数据
        
        【注意事项】
        - 时间窗口必须满足end > begin
        - 第一个K线可能被跳过以避免不完整数据
        - 交易数据按时间顺序处理
        """
        # 记录调试信息：开始刷新时间窗口
        logger.debug(logs.StructuredMessage("Flushing", begin=begin, end=end, pair=self._pair))
        # 验证时间窗口的有效性：结束时间必须大于开始时间
        assert end > begin

        # 更新下一个交易的最小时间限制
        # 如果之前没有限制，使用窗口结束时间；否则取最大值
        self._next_trade_ge = end if self._next_trade_ge is None else max(self._next_trade_ge, end)
        # 初始化OHLC和成交量变量
        open = Decimal(0)
        high = Decimal(0)
        low = Decimal(0)
        close = Decimal(0)
        volume = Decimal(0)
        # 未来交易数据的起始索引，用于分割已处理和未处理的交易
        future_trades_begin = None

        # 计算给定时间窗口内的开盘价、最高价、最低价、收盘价和成交量
        for i, (when, price, amount) in enumerate(self._trades):
            # 如果交易时间早于窗口开始时间，记录顺序错误
            if when < begin:
                self.on_error(logs.StructuredMessage(
                    "Trade is out of order", datetime=when, begin=begin, end=end, pair=self._pair
                ))
                continue
            # 如果交易属于未来窗口，则停止处理当前窗口
            if when > end:
                future_trades_begin = i
                break

            # 设置开盘价：第一个有效交易的价格
            open = price if not open else open
            # 更新最高价：取当前最高价和交易价格的最大值
            high = price if not high else max(high, price)
            # 更新最低价：取当前最低价和交易价格的最小值
            low = price if not low else min(low, price)
            # 设置收盘价：最后一个有效交易的价格
            close = price
            # 累加成交量
            volume += amount

        # 如果窗口内有交易且不跳过第一个K线，则构建K线并发布事件
        if volume and not self._skip_first_bar:
            # 创建K线柱对象
            bar = Bar(begin, self._pair, open, high, low, close, volume)
            # 创建K线事件并推送到事件队列
            self.push(BarEvent(end, bar))
        # 重置跳过第一个K线的标志（只在第一次刷新后有效）
        self._skip_first_bar = False

        # 清理已处理的交易数据
        # 如果没有未来交易，清空整个列表；否则保留未来窗口的交易
        self._trades = [] if future_trades_begin is None else self._trades[future_trades_begin:]

    async def main(self):
        """
        【中文说明】主循环：持续生成K线
        
        【功能描述】
        异步主循环，按固定时间间隔生成K线事件。
        计算当前时间窗口，等待窗口结束，然后刷新该窗口的交易数据。
        
        【算法流程】
        1. 计算当前时间窗口的开始和结束时间
        2. 等待到窗口结束时间加上刷新延迟
        3. 刷新当前窗口的交易数据
        4. 移动到下一个时间窗口
        5. 重复循环
        
        【时间计算】
        - 开始时间：对齐到bar_duration的整数倍
        - 结束时间：开始时间 + bar_duration - 1毫秒
        - 睡眠时间：结束时间 - 当前时间 + 刷新延迟
        
        【注意事项】
        - 使用异步睡眠避免阻塞事件循环
        - 包含刷新延迟以确保窗口内所有交易都被处理
        - 无限循环，直到生产者被停止
        """
        # 获取当前UTC时间
        now = dt.utc_now()
        # 计算当前时间窗口的开始时间：对齐到bar_duration的整数倍
        begin = now - datetime.timedelta(seconds=now.timestamp() % self._bar_duration)
        # 计算当前时间窗口的结束时间：开始时间 + bar_duration - 1毫秒
        end = begin + datetime.timedelta(seconds=self._bar_duration, milliseconds=-1)
        # 主循环：持续生成K线
        while True:
            # 计算需要睡眠的时间：窗口结束时间 - 当前时间 + 刷新延迟
            sleep_time = (end - dt.utc_now()).total_seconds() + self._flush_delay
            # 如果睡眠时间大于0，等待到窗口结束
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
            # 刷新当前时间窗口的交易数据
            self._flush(begin, end)
            # 移动到下一个时间窗口
            begin += datetime.timedelta(seconds=self._bar_duration)
            end += datetime.timedelta(seconds=self._bar_duration)


BarEventHandler = Callable[[BarEvent], Awaitable[Any]]
