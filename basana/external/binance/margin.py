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
【中文说明】Binance保证金管理模块
【功能描述】提供Binance保证金账户的订单管理和查询功能
【使用场景】用于保证金账户的订单创建、查询、取消和OCO订单管理
【核心功能】
- 保证金特定数据模型：Balance、Trade、CreatedOrder等
- 账户抽象基类：Account
- 订单管理：创建、查询、取消各种订单类型
- OCO订单支持：一个取消另一个订单
【注意事项】支持全仓和逐仓保证金账户的通用操作接口
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
import abc

from . import common, helpers, margin_requests
from .client import margin as margin_client
from basana.core.enums import OrderOperation
from basana.core.pair import Pair


class CanceledOCOOrder(common.CanceledOCOOrder):
    """
    【中文说明】已取消OCO订单类
    【功能描述】继承自common.CanceledOCOOrder，表示已取消的OCO订单
    【使用场景】用于处理OCO订单取消操作的结果
    """
    pass


class CanceledOrder(common.CanceledOrder):
    """
    【中文说明】已取消订单类
    【功能描述】继承自common.CanceledOrder，表示已取消的普通订单
    【使用场景】用于处理订单取消操作的结果
    """
    pass


class OpenOrder(common.OpenOrder):
    """
    【中文说明】开放订单类
    【功能描述】继承自common.OpenOrder，表示当前开放的订单
    【使用场景】用于查询和管理当前未完成的订单
    """
    pass


class CreatedOCOOrder(common.CreatedOCOOrder):
    """
    【中文说明】已创建OCO订单类
    【功能描述】继承自common.CreatedOCOOrder，表示已创建的OCO订单
    【使用场景】用于处理OCO订单创建操作的结果
    """
    pass


class Fill(common.Fill):
    """
    【中文说明】成交记录类
    【功能描述】继承自common.Fill，表示订单的成交记录
    【使用场景】用于查询订单的成交明细
    """
    pass


class OCOOrderInfo(common.OCOOrderInfo):
    """
    【中文说明】OCO订单信息类
    【功能描述】继承自common.OCOOrderInfo，表示OCO订单的详细信息
    【使用场景】用于查询OCO订单的状态和详情
    """
    pass


class OrderInfo(common.OrderInfo):
    """
    【中文说明】订单信息类
    【功能描述】继承自common.OrderInfo，表示订单的详细信息
    【使用场景】用于查询订单的状态、成交记录和费用信息
    """
    pass


class Balance(common.Balance):
    """
    【中文说明】保证金余额类
    【功能描述】扩展common.Balance，增加保证金特有的借贷余额属性
    【使用场景】用于查询保证金账户的余额信息
    """
    @property
    def borrowed(self) -> Decimal:
        """
        【中文说明】借贷余额
        【功能描述】获取账户中借入的余额数量
        【返回说明】Decimal类型的借贷余额
        """
        return Decimal(self.json["borrowed"])


class Trade(common.Trade):
    """
    【中文说明】保证金交易类
    【功能描述】扩展common.Trade，增加保证金特有的隔离属性
    【使用场景】用于查询保证金账户的交易记录
    """
    @property
    def is_isolated(self) -> bool:
        """
        【中文说明】是否为隔离交易
        【功能描述】判断该交易是否为逐仓保证金交易
        【返回说明】布尔值，True表示逐仓交易，False表示全仓交易
        """
        return self.json["isIsolated"]


class CreatedOrder(common.CreatedOrder):
    """
    【中文说明】已创建订单类
    【功能描述】扩展common.CreatedOrder，增加成交记录属性
    【使用场景】用于处理订单创建操作的结果，包含成交明细
    """
    @property
    def fills(self) -> List[Fill]:
        """
        【中文说明】成交记录列表
        【功能描述】获取订单的成交记录列表
        【返回说明】Fill对象列表，包含每笔成交的详细信息
        【注意事项】仅在FULL响应模式下可用
        """
        return [Fill(fill) for fill in self.json.get("fills", [])]


class Account(metaclass=abc.ABCMeta):
    """
    【中文说明】保证金账户抽象基类
    【功能描述】定义保证金账户的通用操作接口
    【使用场景】作为全仓和逐仓保证金账户的基类，提供统一的订单管理功能
    【继承关系】CrossMargin和IsolatedMargin账户类继承自此类
    """
    @property
    @abc.abstractmethod
    def client(self) -> margin_client.MarginAccount:
        """
        【中文说明】API客户端
        【功能描述】抽象属性，获取保证金账户的API客户端实例
        【返回说明】MarginAccount类型的API客户端
        """
        raise NotImplementedError()

    async def create_order(self, order_request: margin_requests.ExchangeOrder) -> CreatedOrder:
        """
        【中文说明】创建订单
        【功能描述】使用订单请求对象创建保证金订单
        【参数说明】
        - order_request: 订单请求对象，如MarketOrder、LimitOrder等
        【返回说明】CreatedOrder类型的已创建订单对象
        """
        created_order = await order_request.create_order(self.client)
        return CreatedOrder(created_order)

    async def create_market_order(
            self, operation: OrderOperation, pair: Pair, amount: Optional[Decimal] = None,
            quote_amount: Optional[Decimal] = None, client_order_id: Optional[str] = None,
            side_effect_type: str = "NO_SIDE_EFFECT", **kwargs: Dict[str, Any]
    ) -> CreatedOrder:
        """
        【中文说明】创建市价单
        【功能描述】创建保证金账户的市价订单
        【参数说明】
        - operation: 订单操作类型（买入/卖出）
        - pair: 交易对对象
        - amount: 订单数量（基础货币），与quote_amount二选一
        - quote_amount: 订单金额（计价货币），与amount二选一
        - client_order_id: 客户端订单ID，可选
        - side_effect_type: 订单副作用类型，如"NO_SIDE_EFFECT"、"MARGIN_BUY"、"AUTO_REPAY"
        - kwargs: 其他订单参数
        【返回说明】CreatedOrder类型的已创建订单对象
        【注意事项】如果订单创建失败会抛出Error异常
        """
        return await self.create_order(margin_requests.MarketOrder(
            operation, pair, amount=amount, quote_amount=quote_amount, client_order_id=client_order_id,
            side_effect_type=side_effect_type, **kwargs
        ))

    async def create_limit_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, limit_price: Decimal,
            side_effect_type: str = "NO_SIDE_EFFECT", time_in_force: str = "GTC", client_order_id: Optional[str] = None,
            **kwargs: Dict[str, Any]
    ) -> CreatedOrder:
        """
        【中文说明】创建限价单
        【功能描述】创建保证金账户的限价订单
        【参数说明】
        - operation: 订单操作类型（买入/卖出）
        - pair: 交易对对象
        - amount: 订单数量（基础货币）
        - limit_price: 限价价格
        - side_effect_type: 订单副作用类型
        - time_in_force: 订单时效，如"GTC"、"IOC"、"FOK"等
        - client_order_id: 客户端订单ID，可选
        - kwargs: 其他订单参数
        【返回说明】CreatedOrder类型的已创建订单对象
        【注意事项】如果订单创建失败会抛出Error异常
        """
        return await self.create_order(margin_requests.LimitOrder(
            operation, pair, amount, limit_price, side_effect_type=side_effect_type, time_in_force=time_in_force,
            client_order_id=client_order_id, **kwargs
        ))

    async def create_stop_limit_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, stop_price: Decimal, limit_price: Decimal,
            side_effect_type: str = "NO_SIDE_EFFECT", time_in_force: str = "GTC",
            client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ) -> CreatedOrder:
        """
        【中文说明】创建止损限价单
        【功能描述】创建保证金账户的止损限价订单
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
        【返回说明】CreatedOrder类型的已创建订单对象
        【注意事项】如果订单创建失败会抛出Error异常
        """
        return await self.create_order(margin_requests.StopLimitOrder(
            operation, pair, amount, stop_price, limit_price, side_effect_type=side_effect_type,
            time_in_force=time_in_force, client_order_id=client_order_id, **kwargs
        ))

    async def get_order_info(
            self, pair: Pair, order_id: Optional[str] = None, client_order_id: Optional[str] = None,
            include_trades: bool = True
    ) -> OrderInfo:
        """
        【中文说明】获取订单信息
        【功能描述】查询保证金账户的订单详细信息
        【参数说明】
        - pair: 交易对对象
        - order_id: 订单ID，与client_order_id二选一
        - client_order_id: 客户端订单ID，与order_id二选一
        - include_trades: 是否包含成交记录，默认为True
        【返回说明】OrderInfo类型的订单信息对象
        【注意事项】包含成交记录需要向Binance发送额外请求
        """
        order_book_symbol = helpers.pair_to_symbol(pair)
        order_info = await self.client.query_order(
            order_book_symbol, order_id=None if order_id is None else int(order_id),
            orig_client_order_id=client_order_id
        )
        trades = []
        if include_trades:
            trades = [
                Trade(trade) for trade in
                await self.client.get_trades(order_book_symbol, order_id=order_info["orderId"])
            ]
        return OrderInfo(order_info, trades)

    async def get_open_orders(self, pair: Optional[Pair] = None) -> List[OpenOrder]:
        """
        【中文说明】获取开放订单
        【功能描述】查询保证金账户的当前开放订单
        【参数说明】
        - pair: 交易对对象，可选，如果指定则只返回该交易对的订单
        【返回说明】OpenOrder对象列表
        """
        order_book_symbol = None
        if pair:
            order_book_symbol = helpers.pair_to_symbol(pair)
        return [
            OpenOrder(open_order) for open_order in await self.client.get_open_orders(order_book_symbol)
        ]

    async def cancel_order(
            self, pair: Pair, order_id: Optional[str] = None, client_order_id: Optional[str] = None,
    ) -> CanceledOrder:
        """
        【中文说明】取消订单
        【功能描述】取消保证金账户的指定订单
        【参数说明】
        - pair: 交易对对象
        - order_id: 订单ID，与client_order_id二选一
        - client_order_id: 客户端订单ID，与order_id二选一
        【返回说明】CanceledOrder类型的已取消订单对象
        【注意事项】如果订单取消失败会抛出Error异常
        """
        canceled_order = await self.client.cancel_order(
            helpers.pair_to_symbol(pair), order_id=None if order_id is None else int(order_id),
            orig_client_order_id=client_order_id
        )
        return CanceledOrder(canceled_order)

    async def create_oco_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, limit_price: Decimal, stop_price: Decimal,
            stop_limit_price: Optional[Decimal] = None, side_effect_type: str = "NO_SIDE_EFFECT",
            stop_limit_time_in_force: str = "GTC", list_client_order_id: Optional[str] = None,
            limit_client_order_id: Optional[str] = None, stop_client_order_id: Optional[str] = None,
            **kwargs: Dict[str, Any]
    ) -> CreatedOCOOrder:
        """
        【中文说明】创建OCO订单
        【功能描述】创建保证金账户的OCO订单（一个取消另一个）
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
        【返回说明】CreatedOCOOrder类型的已创建OCO订单对象
        【注意事项】如果订单创建失败会抛出Error异常
        """
        order_req = margin_requests.OCOOrder(
            operation, pair, amount, limit_price, stop_price, stop_limit_price=stop_limit_price,
            side_effect_type=side_effect_type, stop_limit_time_in_force=stop_limit_time_in_force,
            list_client_order_id=list_client_order_id, limit_client_order_id=limit_client_order_id,
            stop_client_order_id=stop_client_order_id, **kwargs
        )
        created_order = await order_req.create_order(self.client)
        return CreatedOCOOrder(created_order)

    async def get_oco_order_info(
            self, order_list_id: Optional[str] = None, client_order_list_id: Optional[str] = None,
    ) -> OCOOrderInfo:
        """
        【中文说明】获取OCO订单信息
        【功能描述】查询保证金账户的OCO订单详细信息
        【参数说明】
        - order_list_id: 订单列表ID，与client_order_list_id二选一
        - client_order_list_id: 客户端订单列表ID，与order_list_id二选一
        【返回说明】OCOOrderInfo类型的OCO订单信息对象
        """
        order_info = await self.client.query_oco_order(
            order_list_id=None if order_list_id is None else int(order_list_id),
            client_order_list_id=client_order_list_id
        )
        return OCOOrderInfo(order_info)

    async def cancel_oco_order(
            self, pair: Pair, order_list_id: Optional[str] = None, client_order_list_id: Optional[str] = None,
    ) -> CanceledOCOOrder:
        """
        【中文说明】取消OCO订单
        【功能描述】取消保证金账户的指定OCO订单
        【参数说明】
        - pair: 交易对对象
        - order_list_id: 订单列表ID，与client_order_list_id二选一
        - client_order_list_id: 客户端订单列表ID，与order_list_id二选一
        【返回说明】CanceledOCOOrder类型的已取消OCO订单对象
        【注意事项】如果订单取消失败会抛出Error异常
        """
        canceled_order = await self.client.cancel_oco_order(
            helpers.pair_to_symbol(pair),
            order_list_id=None if order_list_id is None else int(order_list_id),
            client_order_list_id=client_order_list_id
        )
        return CanceledOCOOrder(canceled_order)
