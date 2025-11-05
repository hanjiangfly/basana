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
# distributed under the License is distributed on "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
【中文说明】Binance保证金客户端模块
【功能描述】提供Binance保证金账户的API操作，包括全仓保证金和逐仓保证金
【使用场景】用于执行保证金交易相关的操作
【注意事项】需要有效的API密钥和密钥才能访问私有接口
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional
import abc
import json

from . import base


class MarginAccount(metaclass=abc.ABCMeta):
    """
    【中文说明】保证金账户抽象基类
    【功能描述】定义保证金账户的通用接口和操作
    【使用场景】作为全仓保证金和逐仓保证金账户的基类
    【注意事项】包含保证金订单创建、查询、取消等通用操作
    """
    def __init__(self, client: base.BaseClient):
        """
        【中文说明】初始化保证金账户
        【参数说明】
        - client: 基础客户端实例
        """
        self._client = client

    @property
    @abc.abstractmethod
    def is_isolated(self) -> bool:
        """
        【中文说明】是否为逐仓保证金账户
        【功能描述】抽象属性，子类必须实现
        【返回说明】True表示逐仓保证金，False表示全仓保证金
        """
        raise NotImplementedError()

    async def create_order(
            self, symbol: str, side: str, type: str, time_in_force: Optional[str] = None,
            quantity: Optional[Decimal] = None, quote_order_qty: Optional[Decimal] = None,
            price: Optional[Decimal] = None, stop_price: Optional[Decimal] = None,
            new_client_order_id: Optional[str] = None, side_effect_type: Optional[str] = None, **kwargs: Dict[str, Any]
    ) -> dict:
        """
        【中文说明】创建保证金订单
        【功能描述】在保证金账户中创建新订单
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - side: 订单方向，"BUY"或"SELL"
        - type: 订单类型，如"LIMIT", "MARKET"等
        - time_in_force: 订单有效时间，可选
        - quantity: 订单数量，可选
        - quote_order_qty: 订单报价数量，可选
        - price: 订单价格，可选
        - stop_price: 止损价格，可选
        - new_client_order_id: 客户端订单ID，可选
        - side_effect_type: 订单副作用类型，可选
        - kwargs: 其他参数
        【返回说明】订单创建结果
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "isIsolated": self.is_isolated,
            "type": type,
        }
        base.set_optional_params(params, (
            ("timeInForce", time_in_force),
            ("quantity", quantity),
            ("quoteOrderQty", quote_order_qty),
            ("price", price),
            ("stopPrice", stop_price),
            ("newClientOrderId", new_client_order_id),
            ("sideEffectType", side_effect_type),
        ))
        params.update(kwargs)
        return await self._client.make_request("POST", "/sapi/v1/margin/order", data=params, send_sig=True)

    async def query_order(
            self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None
    ) -> dict:
        """
        【中文说明】查询保证金订单
        【功能描述】根据订单ID或客户端订单ID查询保证金订单详情
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - order_id: 订单ID，可选
        - orig_client_order_id: 原始客户端订单ID，可选
        【返回说明】订单详情
        【注意事项】order_id和orig_client_order_id必须设置其中一个
        """
        assert (order_id is not None) ^ (orig_client_order_id is not None), \
            "Either order_id or orig_client_order_id should be set"

        params: Dict[str, Any] = {
            "symbol": symbol,
            "isIsolated": json.dumps(self.is_isolated),
        }
        base.set_optional_params(params, (
            ("orderId", order_id),
            ("origClientOrderId", orig_client_order_id),
        ))
        return await self._client.make_request("GET", "/sapi/v1/margin/order", qs_params=params, send_sig=True)

    async def get_open_orders(
            self, symbol: Optional[str] = None
    ) -> dict:
        """
        【中文说明】获取未成交保证金订单
        【功能描述】查询保证金账户中所有未成交的订单
        【参数说明】
        - symbol: 交易对符号，可选，如"BTCUSDT"
        【返回说明】未成交订单列表
        """
        params: Dict[str, Any] = {"isIsolated": json.dumps(self.is_isolated)}
        if symbol is not None:
            params["symbol"] = symbol
        return await self._client.make_request("GET", "/sapi/v1/margin/openOrders", qs_params=params, send_sig=True)

    async def cancel_order(
            self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None
    ) -> dict:
        """
        【中文说明】取消保证金订单
        【功能描述】根据订单ID或客户端订单ID取消保证金订单
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - order_id: 订单ID，可选
        - orig_client_order_id: 原始客户端订单ID，可选
        【返回说明】取消订单结果
        【注意事项】order_id和orig_client_order_id必须设置其中一个
        """
        assert (order_id is not None) ^ (orig_client_order_id is not None), \
            "Either order_id or orig_client_order_id should be set"

        params: Dict[str, Any] = {
            "symbol": symbol,
            "isIsolated": json.dumps(self.is_isolated),
        }
        base.set_optional_params(params, (
            ("orderId", order_id),
            ("origClientOrderId", orig_client_order_id),
        ))
        return await self._client.make_request("DELETE", "/sapi/v1/margin/order", qs_params=params, send_sig=True)

    async def get_trades(self, symbol: str, order_id: Optional[int] = None) -> List[dict]:
        """
        【中文说明】获取保证金交易记录
        【功能描述】查询保证金账户的交易记录
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - order_id: 订单ID，可选
        【返回说明】交易记录列表
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "isIsolated": json.dumps(self.is_isolated),
        }
        if order_id is not None:
            params["orderId"] = order_id
        return await self._client.make_request("GET", "/sapi/v1/margin/myTrades", qs_params=params, send_sig=True)

    async def create_oco(
            self, symbol: str, side: str, quantity: Decimal, price: Decimal, stop_price: Decimal,
            stop_limit_price: Optional[Decimal] = None, stop_limit_time_in_force: Optional[str] = None,
            list_client_order_id: Optional[str] = None, side_effect_type: Optional[str] = None,
            limit_client_order_id: Optional[str] = None, stop_client_order_id: Optional[str] = None,
            **kwargs: Dict[str, Any]
    ) -> dict:
        """
        【中文说明】创建OCO保证金订单
        【功能描述】创建保证金账户的OCO（一个取消另一个）订单
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - side: 订单方向，"BUY"或"SELL"
        - quantity: 订单数量
        - price: 限价单价格
        - stop_price: 止损价格
        - stop_limit_price: 止损限价单价格，可选
        - stop_limit_time_in_force: 止损限价单有效时间，可选
        - list_client_order_id: 订单列表客户端ID，可选
        - side_effect_type: 订单副作用类型，可选
        - limit_client_order_id: 限价单客户端ID，可选
        - stop_client_order_id: 止损单客户端ID，可选
        - kwargs: 其他参数
        【返回说明】OCO订单创建结果
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "quantity": str(quantity),
            "price": str(price),
            "stopPrice": str(stop_price),
            "isIsolated": self.is_isolated,
        }
        base.set_optional_params(params, (
            ("listClientOrderId", list_client_order_id),
            ("stopLimitPrice", stop_limit_price),
            ("stopLimitTimeInForce", stop_limit_time_in_force),
            ("sideEffectType", side_effect_type),
            ("limitClientOrderId", limit_client_order_id),
            ("stopClientOrderId", stop_client_order_id),
        ))
        params.update(kwargs)
        return await self._client.make_request("POST", "/sapi/v1/margin/order/oco", data=params, send_sig=True)

    async def query_oco_order(
            self, order_list_id: Optional[int] = None, client_order_list_id: Optional[str] = None
    ) -> dict:
        """
        【中文说明】查询OCO保证金订单
        【功能描述】根据订单列表ID或客户端订单列表ID查询OCO订单详情
        【参数说明】
        - order_list_id: 订单列表ID，可选
        - client_order_list_id: 客户端订单列表ID，可选
        【返回说明】OCO订单详情
        【注意事项】order_list_id和client_order_list_id必须设置其中一个
        """
        assert (order_list_id is not None) ^ (client_order_list_id is not None), \
            "Either order_list_id or client_order_list_id should be set"

        params: Dict[str, Any] = {
            "isIsolated": json.dumps(self.is_isolated),
        }
        base.set_optional_params(params, (
            ("orderListId", order_list_id),
            ("origClientOrderId", client_order_list_id),
        ))
        return await self._client.make_request("GET", "/sapi/v1/margin/orderList", qs_params=params, send_sig=True)

    async def cancel_oco_order(
            self, symbol: str, order_list_id: Optional[int] = None, client_order_list_id: Optional[str] = None
    ) -> dict:
        """
        【中文说明】取消OCO保证金订单
        【功能描述】根据订单列表ID或客户端订单列表ID取消OCO订单
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - order_list_id: 订单列表ID，可选
        - client_order_list_id: 客户端订单列表ID，可选
        【返回说明】取消OCO订单结果
        【注意事项】order_list_id和client_order_list_id必须设置其中一个
        """
        assert (order_list_id is not None) ^ (client_order_list_id is not None), \
            "Either order_list_id or client_order_list_id should be set"

        params: Dict[str, Any] = {
            "symbol": symbol,
            "isIsolated": json.dumps(self.is_isolated),
        }
        base.set_optional_params(params, (
            ("orderListId", order_list_id),
            ("origClientOrderId", client_order_list_id),
        ))
        return await self._client.make_request("DELETE", "/sapi/v1/margin/orderList", data=params, send_sig=True)


class CrossMarginAccount(MarginAccount):
    """
    【中文说明】全仓保证金账户类
    【功能描述】提供全仓保证金账户的特定操作
    【使用场景】用于全仓保证金交易
    【注意事项】全仓保证金使用整个账户作为抵押品
    """
    @property
    def is_isolated(self) -> bool:
        """
        【中文说明】是否为逐仓保证金账户
        【功能描述】返回False表示全仓保证金账户
        【返回说明】False
        """
        return False

    async def transfer_from_spot_account(self, asset: str, amount: Decimal) -> dict:
        """
        【中文说明】从现货账户转入全仓保证金账户
        【功能描述】将资产从现货账户转入全仓保证金账户
        【参数说明】
        - asset: 资产名称，如"BTC"
        - amount: 转账数量
        【返回说明】转账结果
        """
        params: Dict[str, Any] = {
            "asset": asset,
            "amount": amount,
            "type": 1,
        }
        return await self._client.make_request("POST", "/sapi/v1/margin/transfer", send_sig=True, data=params)

    async def transfer_to_spot_account(self, asset: str, amount: Decimal) -> dict:
        """
        【中文说明】从全仓保证金账户转出到现货账户
        【功能描述】将资产从全仓保证金账户转出到现货账户
        【参数说明】
        - asset: 资产名称，如"BTC"
        - amount: 转账数量
        【返回说明】转账结果
        """
        params: Dict[str, Any] = {
            "asset": asset,
            "amount": amount,
            "type": 2,
        }
        return await self._client.make_request("POST", "/sapi/v1/margin/transfer", send_sig=True, data=params)

    async def get_account_information(self) -> dict:
        """
        【中文说明】获取全仓保证金账户信息
        【功能描述】查询全仓保证金账户的详细信息
        【返回说明】账户信息
        """
        return await self._client.make_request("GET", "/sapi/v1/margin/account", send_sig=True)

    async def create_listen_key(self) -> dict:
        """
        【中文说明】创建用户数据流监听密钥
        【功能描述】创建用于接收用户数据更新的监听密钥
        【返回说明】监听密钥信息
        """
        return await self._client.make_request("POST", "/sapi/v1/userDataStream", send_key=True)

    async def keep_alive_listen_key(self, listen_key: str) -> dict:
        """
        【中文说明】保持用户数据流监听密钥活跃
        【功能描述】延长用户数据流监听密钥的有效期
        【参数说明】
        - listen_key: 监听密钥
        【返回说明】操作结果
        """
        params: Dict[str, Any] = {
            "listenKey": listen_key,
        }
        return await self._client.make_request("PUT", "/sapi/v1/userDataStream", send_key=True, data=params)


class IsolatedMarginAccount(MarginAccount):
    """
    【中文说明】逐仓保证金账户类
    【功能描述】提供逐仓保证金账户的特定操作
    【使用场景】用于逐仓保证金交易
    【注意事项】逐仓保证金使用特定交易对的资产作为抵押品
    """
    @property
    def is_isolated(self) -> bool:
        """
        【中文说明】是否为逐仓保证金账户
        【功能描述】返回True表示逐仓保证金账户
        【返回说明】True
        """
        return True

    async def transfer_from_spot_account(self, asset: str, symbol: str, amount: Decimal) -> dict:
        """
        【中文说明】从现货账户转入逐仓保证金账户
        【功能描述】将资产从现货账户转入指定交易对的逐仓保证金账户
        【参数说明】
        - asset: 资产名称，如"BTC"
        - symbol: 交易对符号，如"BTCUSDT"
        - amount: 转账数量
        【返回说明】转账结果
        """
        params: Dict[str, Any] = {
            "asset": asset,
            "symbol": symbol,
            "amount": str(amount),
            "transFrom": "SPOT",
            "transTo": "ISOLATED_MARGIN",
        }
        return await self._client.make_request("POST", "/sapi/v1/margin/isolated/transfer", send_sig=True, data=params)

    async def transfer_to_spot_account(self, asset: str, symbol: str, amount: Decimal) -> dict:
        """
        【中文说明】从逐仓保证金账户转出到现货账户
        【功能描述】将资产从指定交易对的逐仓保证金账户转出到现货账户
        【参数说明】
        - asset: 资产名称，如"BTC"
        - symbol: 交易对符号，如"BTCUSDT"
        - amount: 转账数量
        【返回说明】转账结果
        """
        params: Dict[str, Any] = {
            "asset": asset,
            "symbol": symbol,
            "amount": str(amount),
            "transFrom": "ISOLATED_MARGIN",
            "transTo": "SPOT",
        }
        return await self._client.make_request("POST", "/sapi/v1/margin/isolated/transfer", send_sig=True, data=params)

    async def get_account_information(self) -> dict:
        """
        【中文说明】获取逐仓保证金账户信息
        【功能描述】查询逐仓保证金账户的详细信息
        【返回说明】账户信息
        """
        return await self._client.make_request("GET", "/sapi/v1/margin/isolated/account", send_sig=True)

    async def create_listen_key(self, symbol: str) -> dict:
        """
        【中文说明】创建逐仓保证金用户数据流监听密钥
        【功能描述】创建用于接收逐仓保证金用户数据更新的监听密钥
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        【返回说明】监听密钥信息
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
        }
        return await self._client.make_request("POST", "/sapi/v1/userDataStream/isolated", send_key=True, data=params)

    async def keep_alive_listen_key(self, symbol: str, listen_key: str) -> dict:
        """
        【中文说明】保持逐仓保证金用户数据流监听密钥活跃
        【功能描述】延长逐仓保证金用户数据流监听密钥的有效期
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - listen_key: 监听密钥
        【返回说明】操作结果
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "listenKey": listen_key,
        }
        return await self._client.make_request("PUT", "/sapi/v1/userDataStream/isolated", send_key=True, data=params)
