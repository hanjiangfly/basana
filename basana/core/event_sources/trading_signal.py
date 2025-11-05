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

from typing import cast, Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple, Union
import datetime

from basana.core import dispatcher, enums, errors, event, helpers, pair


class BaseTradingSignal(event.Event):
    """
    交易信号的基础类。
    
    功能描述：
        表示一个交易信号事件，包含一个或多个交易对及其对应的持仓方向。
        这是所有交易信号事件的基类，支持多交易对信号。
    
    设计原理解释：
        继承自event.Event，具有时间戳属性。
        使用字典存储交易对和持仓方向的映射，支持灵活的多个交易对管理。
    
    使用场景说明：
        用于表示复杂的交易策略信号，可以同时指示多个交易对的持仓变化。
        适用于投资组合管理、套利策略等需要同时操作多个资产对的场景。
    """
    def __init__(self, when: datetime.datetime):
        """
        初始化基础交易信号。
        
        参数说明：
            when: datetime.datetime - 信号发生的时间，必须包含时区信息
        
        设计原理解释：
            调用父类Event的初始化方法设置时间戳。
            初始化内部字典用于存储交易对和持仓方向的映射。
        """
        super().__init__(when)
        self._positions: Dict[pair.Pair, enums.Position] = {}

    def add_pair(self, pair: pair.Pair, position: enums.Position):
        """
        向信号添加交易对。
        
        参数说明：
            pair: pair.Pair - 要交易的交易对
            position: enums.Position - 要切换到的持仓方向（多头、空头或中性）
        
        设计原理解释：
            使用字典存储交易对和持仓方向的映射，允许同一个信号包含多个交易对。
            这种设计支持复杂的交易策略，如配对交易或投资组合再平衡。
        
        使用场景说明：
            当交易策略需要同时操作多个交易对时使用，例如：
            - 套利策略同时买入一个资产并卖出另一个资产
            - 投资组合再平衡调整多个资产的持仓比例
        """
        self._positions[pair] = position

    def get_pairs(self) -> Iterable[Tuple[pair.Pair, enums.Position]]:
        """
        获取信号中的所有交易对及其持仓方向。
        
        返回值说明：
            Iterable[Tuple[pair.Pair, enums.Position]] - 包含交易对和持仓方向的迭代器
        
        设计原理解释：
            返回字典的items()视图，提供对内部存储的交易对和持仓方向的只读访问。
        
        使用场景说明：
            用于遍历信号中的所有交易指令，例如在策略执行器中处理每个交易对。
        """
        return self._positions.items()

    def get_position(self, pair: pair.Pair) -> enums.Position:
        """
        获取指定交易对的持仓方向。
        
        参数说明：
            pair: pair.Pair - 要查询的交易对
        
        返回值说明：
            enums.Position - 该交易对的持仓方向
        
        设计原理解释：
            从内部字典中查找指定交易对的持仓方向，如果不存在会抛出KeyError。
        
        使用场景说明：
            用于查询特定交易对的持仓指令，例如在风险控制模块中检查单个资产的持仓限制。
        """
        return self._positions[pair]


class TradingSignal(BaseTradingSignal):
    """
    单交易对交易信号类。
    
    功能描述：
        表示一个针对单个交易对的交易信号事件，指示采取多头、空头或中性持仓。
        这是BaseTradingSignal的特化版本，专门用于单交易对场景。
    
    设计原理解释：
        继承自BaseTradingSignal，但限制为只能包含一个交易对。
        提供向后兼容性支持，允许使用旧的OrderOperation枚举。
    
    使用场景说明：
        适用于大多数单交易对交易策略，如趋势跟踪、均值回归等。
        提供了从旧的OrderOperation到新的Position枚举的平滑迁移路径。
    """

    def __init__(
            self, when: datetime.datetime, op_or_pos: Union[enums.OrderOperation, enums.Position], pair: pair.Pair
    ):
        """
        初始化单交易对交易信号。
        
        参数说明：
            when: datetime.datetime - 信号发生的时间，必须包含时区信息
            op_or_pos: Union[enums.OrderOperation, enums.Position] - 持仓方向或订单操作（用于向后兼容）
            pair: pair.Pair - 要交易的交易对
        
        设计原理解释：
            1. 首先调用父类初始化方法
            2. 检查是否为旧的OrderOperation类型，如果是则发出弃用警告并转换为Position
            3. 将交易对和持仓方向添加到信号中
        
        使用场景说明：
            创建新的交易信号时使用，支持新旧两种参数类型以确保向后兼容。
        """
        super().__init__(when)

        if isinstance(op_or_pos, enums.OrderOperation):
            helpers.deprecation_warning(
                "Support for bs.OrderOperation in trading signals will be removed soon."
                " Switch to bs.Position"
            )
            op_or_pos = {
                enums.OrderOperation.BUY: enums.Position.LONG,
                enums.OrderOperation.SELL: enums.Position.SHORT,
            }[op_or_pos]
        self.add_pair(pair, op_or_pos)

    @property
    def pair(self) -> pair.Pair:
        """
        获取交易对。
        
        返回值说明：
            pair.Pair - 信号对应的交易对
        
        设计原理解释：
            由于此类只支持单交易对，从内部字典中获取第一个交易对。
        
        使用场景说明：
            在需要获取信号对应的交易对时使用，例如在订单执行器中确定交易标的。
        """
        pair, _ = next(iter(self.get_pairs()))
        return pair

    @property
    def position(self) -> enums.Position:
        """
        获取持仓方向。
        
        返回值说明：
            enums.Position - 信号的持仓方向（多头、空头或中性）
        
        设计原理解释：
            查询当前交易对的持仓方向，由于是单交易对信号，直接返回对应值。
        
        使用场景说明：
            在需要确定持仓方向时使用，例如在策略逻辑中判断是多头还是空头信号。
        """
        return self.get_position(self.pair)

    @property
    def operation(self) -> enums.OrderOperation:
        """
        获取订单操作（已弃用）。
        
        返回值说明：
            enums.OrderOperation - 对应的订单操作（买入或卖出）
        
        设计原理解释：
            为了向后兼容，将Position枚举映射回旧的OrderOperation枚举。
            只支持多头和空头持仓的映射，中性持仓无法映射会抛出错误。
        
        使用场景说明：
            在旧的代码中使用，新代码应该使用position属性代替。
            注意：此属性已弃用，将在未来版本中移除。
        """
        position = self.position
        op = {
            enums.Position.LONG: enums.OrderOperation.BUY,
            enums.Position.SHORT: enums.OrderOperation.SELL,
        }.get(position)
        if op is None:
            raise errors.Error("{} can't be mapped to an operation".format(position))
        return op


class TradingSignalSource(event.FifoQueueEventSource):
    """
    交易信号事件源的基类。
    
    功能描述：
        生成BaseTradingSignal事件的事件源的基类，使用先进先出队列管理事件。
        提供交易信号事件的分发机制，允许订阅者接收交易信号。
    
    设计原理解释：
        继承自event.FifoQueueEventSource，提供事件队列管理功能。
        与事件分发器（EventDispatcher）集成，实现事件的异步分发。
    
    使用场景说明：
        用于创建各种交易信号源，如技术指标信号、机器学习模型信号、外部API信号等。
        适用于构建事件驱动的交易系统，其中信号源产生信号，订阅者处理信号。
    """

    def __init__(
            self, dispatcher: dispatcher.EventDispatcher, producer: Optional[event.Producer] = None,
            events: List[event.Event] = []
    ):
        """
        初始化交易信号事件源。
        
        参数说明：
            dispatcher: dispatcher.EventDispatcher - 事件分发器，用于分发交易信号事件
            producer: Optional[event.Producer] - 可选的事件生产者，与此事件源关联
            events: List[event.Event] - 可选的初始事件列表，用于预加载事件
        
        设计原理解释：
            调用父类FifoQueueEventSource的初始化方法，设置生产者和初始事件。
            存储事件分发器引用，用于后续的事件订阅和分发。
        
        使用场景说明：
            在创建交易信号源时使用，例如在策略初始化阶段创建信号生成器。
        """
        super().__init__(producer=producer, events=events)
        self._dispatcher = dispatcher

    def subscribe_to_trading_signals(self, event_handler: Callable[[BaseTradingSignal], Awaitable[Any]]):
        """
        订阅交易信号事件。
        
        参数说明：
            event_handler: Callable[[BaseTradingSignal], Awaitable[Any]] - 
                异步可调用对象，当新的交易信号可用时被调用，接收一个交易信号作为参数
        
        设计原理解释：
            使用事件分发器的订阅功能，将此事件源与事件处理函数关联。
            当事件源产生新的交易信号时，分发器会调用注册的事件处理函数。
        
        使用场景说明：
            在策略执行器或订单管理器中调用，用于接收和处理交易信号。
            例如，当技术指标产生买入信号时，执行相应的下单操作。
        """
        self._dispatcher.subscribe(self, cast(dispatcher.EventHandler, event_handler))
