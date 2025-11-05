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
【中文说明】Binance逐仓保证金模块
【功能描述】提供Binance逐仓保证金账户的管理和操作功能
【使用场景】用于逐仓保证金账户的余额查询、资金转账和事件订阅
【核心功能】
- IsolatedBalance类：逐仓保证金余额信息
- IsolatedMarginUserDataChannel类：逐仓保证金用户数据流通道
- Account类：逐仓保证金账户操作接口
- 资金转账：现货账户与逐仓保证金账户之间的资金转移
- 事件订阅：用户数据和订单更新事件
【注意事项】逐仓保证金模式下，每个交易对独立管理风险，适合风险隔离策略
"""

from decimal import Decimal
from typing import Optional, Dict
import datetime

from . import client, config, helpers, margin, user_data, websockets, websocket_mgr
from .client import margin as margin_client
from basana.core.config import get_config_value
from basana.core.pair import Pair
import basana as bs


# Forward declarations
OrderEvent = user_data.OrderEvent
OrderEventHandler = user_data.OrderEventHandler
OrderUpdate = user_data.OrderUpdate
UserDataEvent = user_data.Event
UserDataEventHandler = user_data.UserDataEventHandler


class IsolatedBalance:
    """
    【中文说明】逐仓保证金余额类
    【功能描述】封装逐仓保证金账户中特定交易对的余额信息
    【使用场景】用于管理逐仓保证金账户中单个交易对的资产余额
    【余额组成】包含基础资产和计价资产的独立余额信息
    """
    def __init__(self, json: dict):
        """
        【中文说明】初始化逐仓保证金余额
        【功能描述】从JSON数据创建逐仓保证金余额对象
        【参数说明】
        - json: 逐仓保证金余额JSON数据
        """
        self.json = json

    @property
    def base_asset(self) -> str:
        """
        【中文说明】基础资产符号
        【功能描述】获取交易对的基础资产符号
        【返回说明】字符串类型的基础资产符号
        """
        return self.json["baseAsset"]["asset"]

    @property
    def base_asset_balance(self) -> margin.Balance:
        """
        【中文说明】基础资产余额
        【功能描述】获取基础资产的余额信息
        【返回说明】Balance类型的基础资产余额
        """
        return margin.Balance(self.json["baseAsset"])

    @property
    def quote_asset(self) -> str:
        """
        【中文说明】计价资产符号
        【功能描述】获取交易对的计价资产符号
        【返回说明】字符串类型的计价资产符号
        """
        return self.json["quoteAsset"]["asset"]

    @property
    def quote_asset_balance(self) -> margin.Balance:
        """
        【中文说明】计价资产余额
        【功能描述】获取计价资产的余额信息
        【返回说明】Balance类型的计价资产余额
        """
        return margin.Balance(self.json["quoteAsset"])


class IsolatedMarginUserDataChannel(websockets.Channel):
    """
    【中文说明】逐仓保证金用户数据流通道类
    【功能描述】管理逐仓保证金账户的WebSocket用户数据流连接
    【使用场景】用于订阅逐仓保证金账户特定交易对的实时用户数据更新
    【继承关系】继承自websockets.Channel
    【功能特性】按交易对管理listenKey，支持多个交易对的独立数据流
    """
    def __init__(self, pair: bs.Pair):
        """
        【中文说明】初始化逐仓保证金用户数据流通道
        【功能描述】创建逐仓保证金用户数据流通道实例
        【参数说明】
        - pair: 交易对对象
        """
        self._pair = pair
        self._listen_key = None

    @property
    def alias(self) -> str:
        """
        【中文说明】通道别名
        【功能描述】获取通道的唯一标识符（包含交易对符号）
        【返回说明】字符串类型的通道别名
        """
        symbol = helpers.pair_to_symbol(self._pair)
        return f"isolated_margin_user_data_{symbol.lower()}"

    @property
    def stream(self) -> str:
        """
        【中文说明】数据流名称
        【功能描述】获取WebSocket数据流的名称（listenKey）
        【返回说明】字符串类型的数据流名称
        【注意事项】需要先调用resolve_stream_name方法
        """
        assert self._listen_key, "resolve_stream_name not called"
        return self._listen_key

    async def resolve_stream_name(self, api_client: client.APIClient):
        """
        【中文说明】解析数据流名称
        【功能描述】从API客户端获取逐仓保证金账户特定交易对的listenKey
        【参数说明】
        - api_client: Binance API客户端实例
        """
        symbol = helpers.pair_to_symbol(self._pair)
        self._listen_key = (await api_client.isolated_margin_account.create_listen_key(symbol))["listenKey"]

    def keep_alive_period(self, config_overrides: dict = {}) -> Optional[datetime.timedelta]:
        """
        【中文说明】保活间隔
        【功能描述】获取用户数据流的保活间隔时间
        【参数说明】
        - config_overrides: 配置覆盖字典，可选
        【返回说明】timedelta类型的保活间隔
        """
        return datetime.timedelta(
            seconds=get_config_value(
                config.DEFAULTS, "api.websockets.isolated_margin.user_data_stream.heartbeat", overrides=config_overrides
            )
        )

    async def keep_alive(self, api_client: client.APIClient):
        """
        【中文说明】保活操作
        【功能描述】延长用户数据流listenKey的有效期
        【参数说明】
        - api_client: Binance API客户端实例
        【注意事项】需要定期调用以保持连接有效
        """
        assert self._listen_key, "resolve_stream_name not called"
        symbol = helpers.pair_to_symbol(self._pair)
        await api_client.isolated_margin_account.keep_alive_listen_key(symbol, self._listen_key)


class Account(margin.Account):
    """
    【中文说明】逐仓保证金账户类
    【功能描述】提供逐仓保证金账户的操作接口，包括余额查询、资金转账和事件订阅
    【使用场景】用于管理Binance逐仓保证金账户
    【继承关系】继承自margin.Account
    【账户特性】逐仓模式下每个交易对独立管理风险，适合精确风险控制
    """
    def __init__(self, cli: margin_client.IsolatedMarginAccount, ws_mgr: websocket_mgr.WebsocketManager):
        """
        【中文说明】初始化逐仓保证金账户
        【功能描述】创建逐仓保证金账户实例
        【参数说明】
        - cli: 逐仓保证金API客户端
        - ws_mgr: WebSocket管理器
        """
        self._cli = cli
        self._ws_mgr = ws_mgr

    @property
    def client(self) -> margin_client.IsolatedMarginAccount:
        """
        【中文说明】API客户端
        【功能描述】获取逐仓保证金账户的API客户端
        【返回说明】IsolatedMarginAccount类型的API客户端
        """
        return self._cli

    async def get_balances(self) -> Dict[Pair, IsolatedBalance]:
        """
        【中文说明】获取账户余额
        【功能描述】查询逐仓保证金账户的所有交易对余额
        【返回说明】字典类型，键为交易对，值为IsolatedBalance对象
        """
        account_info = await self.client.get_account_information()
        ret = {}
        for isolated_balance in account_info["assets"]:
            isolated_balance = IsolatedBalance(isolated_balance)
            pair = Pair(isolated_balance.base_asset, isolated_balance.quote_asset)
            ret[pair] = isolated_balance
        return ret

    async def transfer_from_spot_account(self, asset: str, pair: Pair, amount: Decimal) -> dict:
        """
        【中文说明】从现货账户转入资金
        【功能描述】将资金从现货账户转移到逐仓保证金账户的特定交易对
        【参数说明】
        - asset: 资产符号（如"BTC", "USDT"等）
        - pair: 交易对对象
        - amount: 转账数量
        【返回说明】转账操作的响应结果
        【注意事项】如果转账失败会抛出Error异常
        """
        return await self.client.transfer_from_spot_account(asset, helpers.pair_to_symbol(pair), amount)

    async def transfer_to_spot_account(self, asset: str, pair: Pair, amount: Decimal) -> dict:
        """
        【中文说明】转出资金到现货账户
        【功能描述】将资金从逐仓保证金账户的特定交易对转移到现货账户
        【参数说明】
        - asset: 资产符号（如"BTC", "USDT"等）
        - pair: 交易对对象
        - amount: 转账数量
        【返回说明】转账操作的响应结果
        【注意事项】如果转账失败会抛出Error异常
        """
        return await self.client.transfer_to_spot_account(asset, helpers.pair_to_symbol(pair), amount)

    def subscribe_to_user_data_events(self, pair: Pair, event_handler: UserDataEventHandler):
        """
        【中文说明】订阅用户数据事件
        【功能描述】注册异步回调函数处理逐仓保证金账户特定交易对的用户数据事件
        【参数说明】
        - pair: 交易对对象
        - event_handler: 用户数据事件处理器
        【使用场景】用于接收特定交易对的账户余额更新、订单状态变化等实时数据
        """
        self._ws_mgr.subscribe_to_user_data_events(
            IsolatedMarginUserDataChannel(pair),
            lambda ws_cli: user_data.WebSocketEventSource(ws_cli),
            event_handler
        )

    def subscribe_to_order_events(self, pair: Pair, event_handler: OrderEventHandler):
        """
        【中文说明】订阅订单事件
        【功能描述】注册异步回调函数处理逐仓保证金账户特定交易对的订单更新事件
        【参数说明】
        - pair: 交易对对象
        - event_handler: 订单事件处理器
        【使用场景】用于接收特定交易对的订单创建、成交、取消等实时更新
        """
        self._ws_mgr.subscribe_to_order_events(
            IsolatedMarginUserDataChannel(pair),
            lambda ws_cli: user_data.WebSocketEventSource(ws_cli),
            event_handler
        )
