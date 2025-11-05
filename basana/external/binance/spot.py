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
Binance现货交易模块

此模块提供了Binance现货交易的核心功能，包括：
- 账户余额管理
- 订单创建、查询和取消
- OCO订单管理
- 用户数据流订阅
- 订单事件处理

主要类：
- Account: 现货账户管理类
- SpotUserDataChannel: 现货用户数据流通道
- 各种订单类型和交易相关的数据类
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
import datetime

from . import client, common, config, helpers, spot_requests, user_data, websockets, websocket_mgr
from .client import spot as spot_client
from basana.core.config import get_config_value
from basana.core.enums import OrderOperation
from basana.core.pair import Pair


# Forward declarations
Balance = common.Balance
CanceledOCOOrder = common.CanceledOCOOrder
CanceledOrder = common.CanceledOrder
CreatedOCOOrder = common.CreatedOCOOrder
OCOOrderInfo = common.OCOOrderInfo
OCOOrderWrapper = common.OCOOrderWrapper
OrderEvent = user_data.OrderEvent
OrderEventHandler = user_data.OrderEventHandler
OrderInfo = common.OrderInfo
OrderUpdate = user_data.OrderUpdate
UserDataEvent = user_data.Event
UserDataEventHandler = user_data.UserDataEventHandler


class Trade(common.Trade):
    """交易数据类，继承自common.Trade
    
    表示单个交易记录，包含交易相关的详细信息。
    """
    
    @property
    def order_list_id(self) -> Optional[str]:
        """获取订单列表ID
        
        :return: 订单列表ID，如果没有则为None
        """
        ret = self.json.get("orderListId")
        ret = None if ret in [None, -1] else str(ret)
        return ret


class Fill(common.Fill):
    """成交数据类，继承自common.Fill
    
    表示订单的成交记录，包含成交价格、数量等信息。
    """
    
    @property
    def trade_id(self) -> str:
        """获取交易ID
        
        :return: 交易ID字符串
        """
        return str(self.json["tradeId"])


class CreatedOrder(common.CreatedOrder):
    """已创建订单类，继承自common.CreatedOrder
    
    表示新创建的订单信息。
    """
    
    @property
    def order_list_id(self) -> Optional[str]:
        """获取订单列表ID
        
        :return: 订单列表ID，如果没有则为None
        """
        ret = self.json["orderListId"]
        ret = None if ret == -1 else str(ret)
        return ret

    @property
    def fills(self) -> List[Fill]:
        """获取成交列表
        
        仅适用于FULL响应类型。
        
        :return: 成交记录列表
        """
        return [Fill(fill) for fill in self.json.get("fills", [])]


class OpenOrder(common.OpenOrder):
    """未完成订单类，继承自common.OpenOrder
    
    表示当前未完成的订单信息。
    """
    
    @property
    def order_list_id(self) -> Optional[str]:
        """获取订单列表ID
        
        :return: 订单列表ID，如果没有则为None
        """
        ret = self.json.get("orderListId")
        ret = None if ret in [None, -1] else str(ret)
        return ret

    @property
    def quote_amount(self) -> Optional[Decimal]:
        """获取报价货币数量
        
        :return: 订单在报价货币中的数量，如果没有则为None
        """
        return helpers.get_optional_decimal(self.json, "origQuoteOrderQty", True)


class SpotUserDataChannel(websockets.Channel):
    """现货用户数据流通道类，继承自websockets.Channel
    
    用于管理Binance现货用户数据流的WebSocket连接。
    """
    
    def __init__(self):
        """初始化现货用户数据流通道"""
        self._listen_key = None

    @property
    def alias(self) -> str:
        """获取通道别名
        
        :return: 通道别名字符串
        """
        return "spot_user_data"

    @property
    def stream(self) -> str:
        """获取流名称
        
        :return: 监听密钥
        :raises AssertionError: 如果resolve_stream_name未被调用
        """
        assert self._listen_key, "resolve_stream_name not called"
        return self._listen_key

    async def resolve_stream_name(self, api_client: client.APIClient):
        """解析流名称
        
        从API客户端获取监听密钥。
        
        :param api_client: API客户端实例
        """
        self._listen_key = (await api_client.spot_account.create_listen_key())["listenKey"]

    def keep_alive_period(self, config_overrides: dict = {}) -> Optional[datetime.timedelta]:
        """获取心跳保持周期
        
        :param config_overrides: 配置覆盖字典
        :return: 心跳间隔时间
        """
        return datetime.timedelta(
            seconds=get_config_value(
                config.DEFAULTS, "api.websockets.spot.user_data_stream.heartbeat", overrides=config_overrides
            )
        )

    async def keep_alive(self, api_client: client.APIClient):
        """保持连接活跃
        
        发送心跳包以保持WebSocket连接活跃。
        
        :param api_client: API客户端实例
        :raises AssertionError: 如果resolve_stream_name未被调用
        """
        assert self._listen_key, "resolve_stream_name not called"
        await api_client.spot_account.keep_alive_listen_key(self._listen_key)


class Account:
    """现货账户管理类
    
    提供Binance现货账户的各种操作功能，包括余额查询、订单管理、用户数据订阅等。
    """
    
    def __init__(self, cli: spot_client.SpotAccount, ws_mgr: websocket_mgr.WebsocketManager):
        """初始化现货账户
        
        :param cli: 现货账户API客户端
        :param ws_mgr: WebSocket管理器
        """
        self._cli = cli
        self._ws_mgr = ws_mgr

    async def get_balances(self) -> Dict[str, Balance]:
        """获取所有余额
        
        :return: 资产余额字典，键为资产符号，值为Balance对象
        """
        account_info = await self._cli.get_account_information()
        return {balance["asset"].upper(): Balance(balance) for balance in account_info["balances"]}

    async def create_order(self, order_request: spot_requests.ExchangeOrder) -> CreatedOrder:
        """创建订单
        
        :param order_request: 订单请求对象
        :return: 已创建的订单信息
        """
        created_order = await order_request.create_order(self._cli)
        return CreatedOrder(created_order)

    async def create_market_order(
            self, operation: OrderOperation, pair: Pair, amount: Optional[Decimal] = None,
            quote_amount: Optional[Decimal] = None, client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ) -> CreatedOrder:
        """创建市价订单

        参考 https://binance-docs.github.io/apidocs/spot/en/#new-order-trade 获取更多信息。
        如果订单无法创建，将抛出 :class:`basana.external.binance.exchange.Error` 异常。

        :param operation: 订单操作类型（买入/卖出）
        :param pair: 交易对
        :param amount: 以基础货币计价的买卖数量
        :param quote_amount: 以报价货币计价的买卖数量
        :param client_order_id: 客户端订单ID
        :param kwargs: 其他将传递给API的关键字参数

        .. note::

          * amount 和 quote_amount 只能设置其中一个，不能同时设置。
        """

        return await self.create_order(spot_requests.MarketOrder(
            operation, pair, amount=amount, quote_amount=quote_amount, client_order_id=client_order_id, **kwargs
        ))

    async def create_limit_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, limit_price: Decimal,
            time_in_force: str = "GTC", client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ) -> CreatedOrder:
        """创建限价订单

        参考 https://binance-docs.github.io/apidocs/spot/en/#new-order-trade 获取更多信息。
        如果订单无法创建，将抛出 :class:`basana.external.binance.exchange.Error` 异常。

        :param operation: 订单操作类型（买入/卖出）
        :param pair: 交易对
        :param amount: 以基础货币计价的买卖数量
        :param limit_price: 限价价格
        :param time_in_force: 订单有效时间（默认为GTC）
        :param client_order_id: 客户端订单ID
        :param kwargs: 其他将传递给API的关键字参数
        """

        return await self.create_order(spot_requests.LimitOrder(
            operation, pair, amount, limit_price, time_in_force=time_in_force, client_order_id=client_order_id,
            **kwargs
        ))

    async def create_stop_limit_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, stop_price: Decimal, limit_price: Decimal,
            time_in_force: str = "GTC", client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ) -> CreatedOrder:
        """创建止损限价订单

        参考 https://binance-docs.github.io/apidocs/spot/en/#new-order-trade 获取更多信息。
        如果订单无法创建，将抛出 :class:`basana.external.binance.exchange.Error` 异常。

        :param operation: 订单操作类型（买入/卖出）
        :param pair: 交易对
        :param amount: 以基础货币计价的买卖数量
        :param stop_price: 止损价格
        :param limit_price: 限价价格
        :param time_in_force: 订单有效时间（默认为GTC）
        :param client_order_id: 客户端订单ID
        :param kwargs: 其他将传递给API的关键字参数
        """

        return await self.create_order(spot_requests.StopLimitOrder(
            operation, pair, amount, stop_price, limit_price, time_in_force=time_in_force,
            client_order_id=client_order_id, **kwargs
        ))

    async def get_order_info(
            self, pair: Pair, order_id: Optional[str] = None, client_order_id: Optional[str] = None,
            include_trades: bool = True
    ) -> OrderInfo:
        """获取订单信息

        :param pair: 交易对
        :param order_id: 订单ID
        :param client_order_id: 客户端订单ID
        :param include_trades: 是否在订单信息中包含交易记录

        .. note::

          * order_id 和 client_order_id 只能设置其中一个，不能同时设置。
          * 包含交易记录需要向Binance发送额外的请求。
        """
        order_book_symbol = helpers.pair_to_symbol(pair)
        order_info = await self._cli.query_order(
            order_book_symbol, order_id=None if order_id is None else int(order_id),
            orig_client_order_id=client_order_id
        )
        trades = []
        if include_trades:
            trades = [
                Trade(trade) for trade in await self._cli.get_trades(order_book_symbol, order_id=order_info["orderId"])
            ]
        return OrderInfo(order_info, trades)

    async def get_open_orders(self, pair: Optional[Pair] = None) -> List[OpenOrder]:
        """获取未完成订单

        :param pair: 如果设置，只返回匹配该交易对的未完成订单，否则返回所有未完成订单
        :return: 未完成订单列表
        """

        order_book_symbol = None
        if pair:
            order_book_symbol = helpers.pair_to_symbol(pair)
        return [
            OpenOrder(open_order) for open_order in await self._cli.get_open_orders(order_book_symbol)
        ]

    async def cancel_order(
            self, pair: Pair, order_id: Optional[str] = None, client_order_id: Optional[str] = None,
    ) -> CanceledOrder:
        """取消订单

        如果订单无法取消，将抛出 :class:`basana.external.binance.exchange.Error` 异常。

        :param pair: 交易对
        :param order_id: 订单ID
        :param client_order_id: 客户端订单ID

        .. note::

          * order_id 和 client_order_id 只能设置其中一个，不能同时设置。
        """
        canceled_order = await self._cli.cancel_order(
            helpers.pair_to_symbol(pair), order_id=None if order_id is None else int(order_id),
            orig_client_order_id=client_order_id
        )
        return CanceledOrder(canceled_order)

    async def create_oco_order(
            self, operation: OrderOperation, pair: Pair, amount: Decimal, limit_price: Decimal, stop_price: Decimal,
            stop_limit_price: Optional[Decimal] = None, stop_limit_time_in_force: str = "GTC",
            list_client_order_id: Optional[str] = None, limit_client_order_id: Optional[str] = None,
            stop_client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ) -> CreatedOCOOrder:
        """创建OCO订单（一个取消另一个）

        参考 https://binance-docs.github.io/apidocs/spot/en/#new-oco-trade 获取更多信息。
        如果订单无法创建，将抛出 :class:`basana.external.binance.exchange.Error` 异常。

        :param operation: 订单操作类型（买入/卖出）
        :param pair: 交易对
        :param amount: 以基础货币计价的买卖数量
        :param limit_price: 限价价格
        :param stop_price: 止损价格
        :param stop_limit_price: 止损限价价格
        :param stop_limit_time_in_force: 止损限价订单的有效时间
        :param list_client_order_id: 订单列表的客户端ID
        :param limit_client_order_id: 限价订单的客户端ID
        :param stop_client_order_id: 止损订单的客户端ID
        :param kwargs: 其他将传递给API的关键字参数
        """
        order_req = spot_requests.OCOOrder(
            operation, pair, amount, limit_price, stop_price, stop_limit_price=stop_limit_price,
            stop_limit_time_in_force=stop_limit_time_in_force, list_client_order_id=list_client_order_id,
            limit_client_order_id=limit_client_order_id, stop_client_order_id=stop_client_order_id,
            **kwargs
        )
        created_order = await order_req.create_order(self._cli)
        return CreatedOCOOrder(created_order)

    async def get_oco_order_info(
            self, order_list_id: Optional[str] = None, client_order_list_id: Optional[str] = None,
    ) -> OCOOrderInfo:
        """获取OCO订单信息

        :param order_list_id: 订单列表ID
        :param client_order_list_id: 订单列表的客户端ID

        .. note::

          * order_list_id 和 client_order_list_id 只能设置其中一个，不能同时设置。
        """
        order_info = await self._cli.query_oco_order(
            order_list_id=None if order_list_id is None else int(order_list_id),
            client_order_list_id=client_order_list_id
        )
        return OCOOrderInfo(order_info)

    async def cancel_oco_order(
            self, pair: Pair, order_list_id: Optional[str] = None, client_order_list_id: Optional[str] = None,
    ) -> CanceledOCOOrder:
        """取消OCO订单

        如果订单无法取消，将抛出 :class:`basana.external.binance.exchange.Error` 异常。

        :param pair: 交易对
        :param order_list_id: 订单列表ID
        :param client_order_list_id: 订单列表的客户端ID

        .. note::

          * order_list_id 和 client_order_list_id 只能设置其中一个，不能同时设置。
        """

        canceled_order = await self._cli.cancel_oco_order(
            helpers.pair_to_symbol(pair),
            order_list_id=None if order_list_id is None else int(order_list_id),
            client_order_list_id=client_order_list_id
        )
        return CanceledOCOOrder(canceled_order)

    def subscribe_to_user_data_events(self, event_handler: UserDataEventHandler):
        """
        注册异步回调函数，用于处理新的用户数据事件。

        按照 https://developers.binance.com/docs/binance-spot-api-docs/user-data-stream 定义的方式工作。

        :param event_handler: 事件处理器
        """

        self._ws_mgr.subscribe_to_user_data_events(
            SpotUserDataChannel(),
            lambda ws_cli: user_data.WebSocketEventSource(ws_cli),
            event_handler
        )

    def subscribe_to_order_events(self, event_handler: OrderEventHandler):
        """
        注册异步回调函数，用于处理新的订单更新。

        按照 https://developers.binance.com/docs/binance-spot-api-docs/user-data-stream#order-update 定义的方式工作。

        :param event_handler: 事件处理器
        """

        self._ws_mgr.subscribe_to_order_events(
            SpotUserDataChannel(),
            lambda ws_cli: user_data.WebSocketEventSource(ws_cli),
            event_handler
        )
