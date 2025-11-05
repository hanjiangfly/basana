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
【中文说明】Binance保证金订单请求模块
【功能描述】提供Binance保证金交易的各种订单类型封装和创建功能
【使用场景】用于创建和管理保证金账户的市价单、限价单、止损限价单和OCO订单
【核心功能】
- ExchangeOrder：交易所订单抽象基类
- MarketOrder：市价单
- LimitOrder：限价单
- StopLimitOrder：止损限价单
- OCOOrder：OCO订单（一个取消另一个）
【注意事项】所有订单都支持保证金交易的特殊参数，如side_effect_type
"""

from decimal import Decimal
from typing import Any, Dict, Optional
import abc

from . import helpers
from basana.core.enums import OrderOperation
from basana.core.pair import Pair


class ExchangeOrder(metaclass=abc.ABCMeta):
    """
    【中文说明】交易所订单抽象基类
    【功能描述】定义保证金订单的通用接口和基础属性
    【使用场景】作为所有保证金订单类型的基类，提供统一的订单创建接口
    【继承关系】所有具体订单类都继承自此类
    """
    def __init__(
            self, operation: OrderOperation, pair: Pair, amount: Optional[Decimal],
            client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ):
        """
        【中文说明】初始化交易所订单
        【功能描述】创建订单对象的基础属性
        【参数说明】
        - operation: 订单操作类型（买入/卖出）
        - pair: 交易对对象
        - amount: 订单数量（基础货币）
        - client_order_id: 客户端订单ID，可选
        - kwargs: 其他订单参数
        """
        self._operation = operation
        self._pair = pair
        self._amount = amount
        self._client_order_id = client_order_id
        self._kwargs = kwargs

    @abc.abstractmethod
    async def create_order(self, margin_account_cli) -> dict:
        """
        【中文说明】创建订单
        【功能描述】抽象方法，在具体订单类中实现具体的订单创建逻辑
        【参数说明】
        - margin_account_cli: 保证金账户客户端实例
        【返回说明】订单创建结果的字典
        """
        raise NotImplementedError()


class MarketOrder(ExchangeOrder):
    """
    【中文说明】市价单类
    【功能描述】封装Binance保证金市价单的创建和参数管理
    【使用场景】用于以当前市场价格立即成交的保证金订单
    【继承关系】继承自ExchangeOrder
    【订单特性】支持按数量或按计价货币金额下单
    """
    def __init__(
            self, operation: OrderOperation, pair: Pair, amount: Optional[Decimal] = None,
            quote_amount: Optional[Decimal] = None, client_order_id: Optional[str] = None,
            side_effect_type: str = "NO_SIDE_EFFECT", **kwargs: Dict[str, Any]
    ):
        """
        【中文说明】初始化市价单
        【功能描述】创建市价单对象
        【参数说明】
        - operation: 订单操作类型（买入/卖出）
        - pair: 交易对对象
        - amount: 订单数量（基础货币），与quote_amount二选一
        - quote_amount: 订单金额（计价货币），与amount二选一
        - client_order_id: 客户端订单ID，可选
        - side_effect_type: 订单副作用类型，如"MARGIN_BUY"、"AUTO_REPAY"等
        - kwargs: 其他订单参数
        """
        assert (amount is not None) ^ (quote_amount is not None), "Either amount or quote_amount should be set"
        super().__init__(operation, pair, amount, client_order_id=client_order_id, **kwargs)
        self._quote_amount = quote_amount
        self._side_effect_type = side_effect_type

    async def create_order(self, margin_account_cli) -> dict:
        """
        【中文说明】创建市价单
        【功能描述】调用Binance API创建保证金市价单
        【参数说明】
        - margin_account_cli: 保证金账户客户端实例
        【返回说明】订单创建结果的字典
        """
        return await margin_account_cli.create_order(
            helpers.pair_to_symbol(self._pair), helpers.order_operation_to_side(self._operation), "MARKET",
            quantity=self._amount, quote_order_qty=self._quote_amount, new_client_order_id=self._client_order_id,
            side_effect_type=self._side_effect_type, **self._kwargs
        )


class LimitOrder(ExchangeOrder):
    """
    【中文说明】限价单类
    【功能描述】封装Binance保证金限价单的创建和参数管理
    【使用场景】用于以指定价格或更好价格成交的保证金订单
    【继承关系】继承自ExchangeOrder
    【订单特性】支持设置价格和订单时效
    """
    def __init__(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, limit_price: Decimal,
            side_effect_type: str = "NO_SIDE_EFFECT", time_in_force: str = "GTC", client_order_id: Optional[str] = None,
            **kwargs: Dict[str, Any]
    ):
        """
        【中文说明】初始化限价单
        【功能描述】创建限价单对象
        【参数说明】
        - operation: 订单操作类型（买入/卖出）
        - pair: 交易对对象
        - amount: 订单数量（基础货币）
        - limit_price: 限价价格
        - side_effect_type: 订单副作用类型
        - time_in_force: 订单时效，如"GTC"、"IOC"、"FOK"等
        - client_order_id: 客户端订单ID，可选
        - kwargs: 其他订单参数
        """
        super().__init__(operation, pair, amount, client_order_id=client_order_id, **kwargs)
        self._limit_price = limit_price
        self._time_in_force = time_in_force
        self._side_effect_type = side_effect_type

    async def create_order(self, margin_account_cli) -> dict:
        """
        【中文说明】创建限价单
        【功能描述】调用Binance API创建保证金限价单
        【参数说明】
        - margin_account_cli: 保证金账户客户端实例
        【返回说明】订单创建结果的字典
        """
        return await margin_account_cli.create_order(
            helpers.pair_to_symbol(self._pair), helpers.order_operation_to_side(self._operation), "LIMIT",
            quantity=self._amount, price=self._limit_price, time_in_force=self._time_in_force,
            new_client_order_id=self._client_order_id, side_effect_type=self._side_effect_type, **self._kwargs
        )


class StopLimitOrder(ExchangeOrder):
    """
    【中文说明】止损限价单类
    【功能描述】封装Binance保证金止损限价单的创建和参数管理
    【使用场景】用于在价格达到止损价时以限价方式成交的保证金订单
    【继承关系】继承自ExchangeOrder
    【订单特性】支持设置止损价和限价，实现风险控制
    """
    def __init__(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, stop_price: Decimal, limit_price: Decimal,
            side_effect_type: str = "NO_SIDE_EFFECT", time_in_force: str = "GTC",
            client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ):
        """
        【中文说明】初始化止损限价单
        【功能描述】创建止损限价单对象
        【参数说明】
        - operation: 订单操作类型（买入/卖出）
        - pair: 交易对对象
        - amount: 订单数量（基础货币）
        - stop_price: 止损触发价格
        - limit_price: 限价价格
        - side_effect_type: 订单副作用类型
        - time_in_force: 订单时效
        - client_order_id: 客户端订单ID，可选
        - kwargs: 其他订单参数
        """
        super().__init__(operation, pair, amount, client_order_id=client_order_id, **kwargs)
        self._stop_price = stop_price
        self._limit_price = limit_price
        self._time_in_force = time_in_force
        self._side_effect_type = side_effect_type

    async def create_order(self, margin_account_cli) -> dict:
        """
        【中文说明】创建止损限价单
        【功能描述】调用Binance API创建保证金止损限价单
        【参数说明】
        - margin_account_cli: 保证金账户客户端实例
        【返回说明】订单创建结果的字典
        """
        return await margin_account_cli.create_order(
            helpers.pair_to_symbol(self._pair), helpers.order_operation_to_side(self._operation),
            "STOP_LOSS_LIMIT", quantity=self._amount, stop_price=self._stop_price, price=self._limit_price,
            time_in_force=self._time_in_force, new_client_order_id=self._client_order_id,
            side_effect_type=self._side_effect_type, **self._kwargs
        )


class OCOOrder:
    """
    【中文说明】OCO订单类
    【功能描述】封装Binance保证金OCO订单（一个取消另一个）的创建和参数管理
    【使用场景】用于同时创建限价单和止损单，其中一个成交另一个自动取消
    【订单特性】支持复杂的条件订单组合，实现自动风险管理
    """
    def __init__(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, limit_price: Decimal, stop_price: Decimal,
            stop_limit_price: Optional[Decimal] = None, side_effect_type: str = "NO_SIDE_EFFECT",
            stop_limit_time_in_force: str = "GTC", list_client_order_id: Optional[str] = None,
            limit_client_order_id: Optional[str] = None, stop_client_order_id: Optional[str] = None,
            **kwargs: Dict[str, Any]
    ):
        """
        【中文说明】初始化OCO订单
        【功能描述】创建OCO订单对象
        【参数说明】
        - operation: 订单操作类型（买入/卖出）
        - pair: 交易对对象
        - amount: 订单数量（基础货币）
        - limit_price: 限价单价格
        - stop_price: 止损单触发价格
        - stop_limit_price: 止损限价单价格，可选
        - side_effect_type: 订单副作用类型
        - stop_limit_time_in_force: 止损限价单时效
        - list_client_order_id: OCO订单列表客户端ID，可选
        - limit_client_order_id: 限价单客户端ID，可选
        - stop_client_order_id: 止损单客户端ID，可选
        - kwargs: 其他订单参数
        """
        self._operation = operation
        self._pair = pair
        self._amount = amount
        self._limit_price = limit_price
        self._stop_price = stop_price
        self._stop_limit_price = stop_limit_price
        self._stop_limit_time_in_force = None if stop_limit_price is None else stop_limit_time_in_force
        self._list_client_order_id = list_client_order_id
        self._side_effect_type = side_effect_type
        self._limit_client_order_id = limit_client_order_id
        self._stop_client_order_id = stop_client_order_id
        self._kwargs = kwargs

    async def create_order(self, margin_account_cli) -> dict:
        """
        【中文说明】创建OCO订单
        【功能描述】调用Binance API创建保证金OCO订单
        【参数说明】
        - margin_account_cli: 保证金账户客户端实例
        【返回说明】OCO订单创建结果的字典
        """
        return await margin_account_cli.create_oco(
            helpers.pair_to_symbol(self._pair), helpers.order_operation_to_side(self._operation),
            self._amount, self._limit_price, self._stop_price, stop_limit_price=self._stop_limit_price,
            stop_limit_time_in_force=self._stop_limit_time_in_force, list_client_order_id=self._list_client_order_id,
            side_effect_type=self._side_effect_type, limit_client_order_id=self._limit_client_order_id,
            stop_client_order_id=self._stop_client_order_id, **self._kwargs
        )
