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
【中文说明】Binance现货客户端模块
【功能描述】提供Binance现货账户的API操作
【使用场景】用于执行现货交易相关的操作
【注意事项】需要有效的API密钥和密钥才能访问私有接口
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional


from . import base


# https://binance-docs.github.io/apidocs/spot/en/#spot-account-trade
class SpotAccount:
    """
    【中文说明】现货账户类
    【功能描述】提供Binance现货账户的各种操作接口
    【使用场景】用于现货交易、账户查询、订单管理等
    【注意事项】包含现货交易的所有核心功能
    """
    def __init__(self, client: base.BaseClient):
        """
        【中文说明】初始化现货账户
        【参数说明】
        - client: 基础客户端实例
        """
        self._client = client

    async def get_account_information(self) -> dict:
        """
        【中文说明】获取现货账户信息
        【功能描述】查询现货账户的详细信息，包括余额、权限等
        【返回说明】账户信息字典
        """
        return await self._client.make_request("GET", "/api/v3/account", send_sig=True)

    async def create_order(
            self, symbol: str, side: str, type: str, time_in_force: Optional[str] = None,
            quantity: Optional[Decimal] = None, quote_order_qty: Optional[Decimal] = None,
            price: Optional[Decimal] = None, stop_price: Optional[Decimal] = None,
            new_client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ) -> dict:
        """
        【中文说明】创建现货订单
        【功能描述】在现货账户中创建新订单
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
        - kwargs: 其他参数
        【返回说明】订单创建结果
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": type,
        }
        base.set_optional_params(params, (
            ("timeInForce", time_in_force),
            ("quantity", quantity),
            ("quoteOrderQty", quote_order_qty),
            ("price", price),
            ("stopPrice", stop_price),
            ("newClientOrderId", new_client_order_id),
        ))
        params.update(kwargs)
        return await self._client.make_request("POST", "/api/v3/order", data=params, send_sig=True)

    async def query_order(
            self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None
    ) -> dict:
        """
        【中文说明】查询现货订单
        【功能描述】根据订单ID或客户端订单ID查询现货订单详情
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - order_id: 订单ID，可选
        - orig_client_order_id: 原始客户端订单ID，可选
        【返回说明】订单详情
        【注意事项】order_id和orig_client_order_id必须设置其中一个
        """
        assert (order_id is not None) ^ (orig_client_order_id is not None), \
            "Either order_id or orig_client_order_id should be set"

        params: Dict[str, Any] = {"symbol": symbol}
        base.set_optional_params(params, (
            ("orderId", order_id),
            ("origClientOrderId", orig_client_order_id),
        ))
        return await self._client.make_request("GET", "/api/v3/order", qs_params=params, send_sig=True)

    async def get_open_orders(
            self, symbol: Optional[str] = None
    ) -> dict:
        """
        【中文说明】获取未成交现货订单
        【功能描述】查询现货账户中所有未成交的订单
        【参数说明】
        - symbol: 交易对符号，可选，如"BTCUSDT"
        【返回说明】未成交订单列表
        """
        params: Dict[str, Any] = {}
        if symbol is not None:
            params["symbol"] = symbol
        return await self._client.make_request("GET", "/api/v3/openOrders", qs_params=params, send_sig=True)

    async def cancel_order(
            self, symbol: str, order_id: Optional[int] = None, orig_client_order_id: Optional[str] = None
    ) -> dict:
        """
        【中文说明】取消现货订单
        【功能描述】根据订单ID或客户端订单ID取消现货订单
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - order_id: 订单ID，可选
        - orig_client_order_id: 原始客户端订单ID，可选
        【返回说明】取消订单结果
        【注意事项】order_id和orig_client_order_id必须设置其中一个
        """
        assert (order_id is not None) ^ (orig_client_order_id is not None), \
            "Either order_id or orig_client_order_id should be set"

        params: Dict[str, Any] = {"symbol": symbol}
        base.set_optional_params(params, (
            ("orderId", order_id),
            ("origClientOrderId", orig_client_order_id),
        ))
        return await self._client.make_request("DELETE", "/api/v3/order", qs_params=params, send_sig=True)

    async def get_trades(self, symbol: str, order_id: Optional[int] = None) -> List[dict]:
        """
        【中文说明】获取现货交易记录
        【功能描述】查询现货账户的交易记录
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - order_id: 订单ID，可选
        【返回说明】交易记录列表
        """
        params: Dict[str, Any] = {"symbol": symbol}
        if order_id is not None:
            params["orderId"] = order_id
        return await self._client.make_request("GET", "/api/v3/myTrades", qs_params=params, send_sig=True)

    async def create_oco(
            self, symbol: str, side: str, quantity: Decimal, price: Decimal, stop_price: Decimal,
            stop_limit_price: Optional[Decimal] = None, stop_limit_time_in_force: Optional[str] = None,
            list_client_order_id: Optional[str] = None, limit_client_order_id: Optional[str] = None,
            stop_client_order_id: Optional[str] = None, **kwargs: Dict[str, Any]
    ) -> dict:
        """
        【中文说明】创建OCO现货订单
        【功能描述】创建现货账户的OCO（一个取消另一个）订单
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - side: 订单方向，"BUY"或"SELL"
        - quantity: 订单数量
        - price: 限价单价格
        - stop_price: 止损价格
        - stop_limit_price: 止损限价单价格，可选
        - stop_limit_time_in_force: 止损限价单有效时间，可选
        - list_client_order_id: 订单列表客户端ID，可选
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
        }
        base.set_optional_params(params, (
            ("listClientOrderId", list_client_order_id),
            ("stopLimitPrice", stop_limit_price),
            ("stopLimitTimeInForce", stop_limit_time_in_force),
            ("limitClientOrderId", limit_client_order_id),
            ("stopClientOrderId", stop_client_order_id),
        ))
        params.update(kwargs)
        return await self._client.make_request("POST", "/api/v3/order/oco", data=params, send_sig=True)

    async def cancel_oco_order(
            self, symbol: str, order_list_id: Optional[int] = None, client_order_list_id: Optional[str] = None
    ) -> dict:
        """
        【中文说明】取消OCO现货订单
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
            "symbol": symbol
        }
        base.set_optional_params(params, (
            ("orderListId", order_list_id),
            ("origClientOrderId", client_order_list_id),
        ))
        return await self._client.make_request("DELETE", "/api/v3/orderList", data=params, send_sig=True)

    async def query_oco_order(
            self, order_list_id: Optional[int] = None, client_order_list_id: Optional[str] = None
    ) -> dict:
        """
        【中文说明】查询OCO现货订单
        【功能描述】根据订单列表ID或客户端订单列表ID查询OCO订单详情
        【参数说明】
        - order_list_id: 订单列表ID，可选
        - client_order_list_id: 客户端订单列表ID，可选
        【返回说明】OCO订单详情
        【注意事项】order_list_id和client_order_list_id必须设置其中一个
        """
        assert (order_list_id is not None) ^ (client_order_list_id is not None), \
            "Either order_list_id or client_order_list_id should be set"

        params: Dict[str, Any] = {}
        base.set_optional_params(params, (
            ("orderListId", order_list_id),
            ("origClientOrderId", client_order_list_id),
        ))
        return await self._client.make_request("GET", "/api/v3/orderList", qs_params=params, send_sig=True)

    async def create_listen_key(self) -> dict:
        """
        【中文说明】创建用户数据流监听密钥
        【功能描述】创建用于接收现货用户数据更新的监听密钥
        【返回说明】监听密钥信息
        """
        return await self._client.make_request("POST", "/api/v3/userDataStream", send_key=True)

    async def keep_alive_listen_key(self, listen_key: str) -> dict:
        """
        【中文说明】保持用户数据流监听密钥活跃
        【功能描述】延长现货用户数据流监听密钥的有效期
        【参数说明】
        - listen_key: 监听密钥
        【返回说明】操作结果
        """
        params: Dict[str, Any] = {
            "listenKey": listen_key,
        }
        return await self._client.make_request("PUT", "/api/v3/userDataStream", send_key=True, data=params)
