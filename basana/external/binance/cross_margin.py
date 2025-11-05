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
【中文说明】Binance全仓保证金模块
【功能描述】提供Binance全仓保证金账户的管理和操作功能
【使用场景】用于全仓保证金账户的余额查询、资金转账和事件订阅
【核心功能】
- CrossMarginUserDataChannel类：全仓保证金用户数据流通道
- Account类：全仓保证金账户操作接口
- 资金转账：现货账户与保证金账户之间的资金转移
- 事件订阅：用户数据和订单更新事件
【注意事项】全仓保证金模式下，所有保证金资产共享一个风险池
"""

from decimal import Decimal
from typing import Optional, Dict
import datetime

from . import client, config, margin, user_data, websockets, websocket_mgr
from .client import margin as margin_client
from basana.core.config import get_config_value


# Forward declarations
OrderEvent = user_data.OrderEvent
OrderEventHandler = user_data.OrderEventHandler
OrderUpdate = user_data.OrderUpdate
UserDataEvent = user_data.Event
UserDataEventHandler = user_data.UserDataEventHandler


class CrossMarginUserDataChannel(websockets.Channel):
    """
    【中文说明】全仓保证金用户数据流通道类
    【功能描述】管理全仓保证金账户的WebSocket用户数据流连接
    【使用场景】用于订阅全仓保证金账户的实时用户数据更新
    【继承关系】继承自websockets.Channel
    【功能特性】自动管理listenKey的创建和保活
    """
    def __init__(self):
        self._listen_key = None

    @property
    def alias(self) -> str:
        """
        【中文说明】通道别名
        【功能描述】获取通道的唯一标识符
        【返回说明】字符串类型的通道别名
        """
        return "cross_margin_user_data"

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
        【功能描述】从API客户端获取全仓保证金账户的listenKey
        【参数说明】
        - api_client: Binance API客户端实例
        """
        self._listen_key = (await api_client.cross_margin_account.create_listen_key())["listenKey"]

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
                config.DEFAULTS, "api.websockets.cross_margin.user_data_stream.heartbeat", overrides=config_overrides
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
        await api_client.cross_margin_account.keep_alive_listen_key(self._listen_key)


class Account(margin.Account):
    """
    【中文说明】全仓保证金账户类
    【功能描述】提供全仓保证金账户的操作接口，包括余额查询、资金转账和事件订阅
    【使用场景】用于管理Binance全仓保证金账户
    【继承关系】继承自margin.Account
    【账户特性】全仓模式下所有保证金资产共享风险，适合风险分散策略
    """
    def __init__(self, cli: margin_client.CrossMarginAccount, ws_mgr: websocket_mgr.WebsocketManager):
        """
        【中文说明】初始化全仓保证金账户
        【功能描述】创建全仓保证金账户实例
        【参数说明】
        - cli: 全仓保证金API客户端
        - ws_mgr: WebSocket管理器
        """
        self._cli = cli
        self._ws_mgr = ws_mgr

    @property
    def client(self) -> margin_client.CrossMarginAccount:
        """
        【中文说明】API客户端
        【功能描述】获取全仓保证金账户的API客户端
        【返回说明】CrossMarginAccount类型的API客户端
        """
        return self._cli

    async def get_balances(self) -> Dict[str, margin.Balance]:
        """
        【中文说明】获取账户余额
        【功能描述】查询全仓保证金账户的所有资产余额
        【返回说明】字典类型，键为资产符号，值为Balance对象
        """
        account_info = await self.client.get_account_information()
        return {balance["asset"].upper(): margin.Balance(balance) for balance in account_info["userAssets"]}

    async def transfer_from_spot_account(self, asset: str, amount: Decimal) -> dict:
        """
        【中文说明】从现货账户转入资金
        【功能描述】将资金从现货账户转移到全仓保证金账户
        【参数说明】
        - asset: 资产符号（如"BTC", "USDT"等）
        - amount: 转账数量
        【返回说明】转账操作的响应结果
        【注意事项】如果转账失败会抛出Error异常
        """
        return await self.client.transfer_from_spot_account(asset, amount)

    async def transfer_to_spot_account(self, asset: str, amount: Decimal) -> dict:
        """
        【中文说明】转出资金到现货账户
        【功能描述】将资金从全仓保证金账户转移到现货账户
        【参数说明】
        - asset: 资产符号（如"BTC", "USDT"等）
        - amount: 转账数量
        【返回说明】转账操作的响应结果
        【注意事项】如果转账失败会抛出Error异常
        """
        return await self.client.transfer_to_spot_account(asset, amount)

    def subscribe_to_user_data_events(self, event_handler: UserDataEventHandler):
        """
        【中文说明】订阅用户数据事件
        【功能描述】注册异步回调函数处理全仓保证金账户的用户数据事件
        【参数说明】
        - event_handler: 用户数据事件处理器
        【使用场景】用于接收账户余额更新、订单状态变化等实时数据
        """
        self._ws_mgr.subscribe_to_user_data_events(
            CrossMarginUserDataChannel(),
            lambda ws_cli: user_data.WebSocketEventSource(ws_cli),
            event_handler
        )

    def subscribe_to_order_events(self, event_handler: OrderEventHandler):
        """
        【中文说明】订阅订单事件
        【功能描述】注册异步回调函数处理全仓保证金账户的订单更新事件
        【参数说明】
        - event_handler: 订单事件处理器
        【使用场景】用于接收订单创建、成交、取消等实时更新
        """
        self._ws_mgr.subscribe_to_order_events(
            CrossMarginUserDataChannel(),
            lambda ws_cli: user_data.WebSocketEventSource(ws_cli),
            event_handler
        )
