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
【中文说明】Binance客户端模块初始化文件
【功能描述】提供统一的Binance API客户端接口，整合现货、全仓保证金和逐仓保证金账户功能
【使用场景】用于创建和管理Binance交易所的API客户端实例
【注意事项】需要提供有效的API密钥和密钥才能访问私有接口
"""

from typing import Any, Dict, Optional

import aiohttp

from . import base, margin, spot
from basana.core import token_bucket


Error = base.Error


class APIClient:
    """
    【中文说明】Binance API客户端主类
    【功能描述】提供统一的Binance API访问接口，支持现货、全仓保证金和逐仓保证金账户
    【使用场景】用于执行Binance交易所的各种API操作
    【注意事项】API密钥和密钥必须同时设置或同时不设置
    """
    def __init__(
            self, api_key: Optional[str] = None, api_secret: Optional[str] = None,
            session: Optional[aiohttp.ClientSession] = None, tb: Optional[token_bucket.TokenBucketLimiter] = None,
            config_overrides: dict = {}
    ):
        """
        【中文说明】初始化API客户端
        【参数说明】
        - api_key: API密钥，可选
        - api_secret: API密钥，可选  
        - session: aiohttp客户端会话，可选
        - tb: 令牌桶限流器，可选
        - config_overrides: 配置覆盖项，可选
        【注意事项】api_key和api_secret必须同时设置或同时不设置
        """
        self._client = base.BaseClient(
            api_key=api_key, api_secret=api_secret, session=session, tb=tb, config_overrides=config_overrides
        )

    async def get_exchange_info(self, symbol: Optional[str] = None) -> dict:
        """
        【中文说明】获取交易所信息
        【功能描述】查询Binance交易所的交易对信息和交易规则
        【参数说明】
        - symbol: 交易对符号，可选，如"BTCUSDT"
        【返回说明】包含交易所信息的字典
        """
        params = {}
        if symbol:
            params["symbol"] = symbol
        return await self._client.make_request("GET", "/api/v3/exchangeInfo", qs_params=params)

    @property
    def spot_account(self) -> spot.SpotAccount:
        """
        【中文说明】现货账户属性
        【功能描述】获取现货账户操作接口
        【返回说明】SpotAccount实例
        """
        return spot.SpotAccount(self._client)

    @property
    def cross_margin_account(self) -> margin.CrossMarginAccount:
        """
        【中文说明】全仓保证金账户属性
        【功能描述】获取全仓保证金账户操作接口
        【返回说明】CrossMarginAccount实例
        """
        return margin.CrossMarginAccount(self._client)

    @property
    def isolated_margin_account(self) -> margin.IsolatedMarginAccount:
        """
        【中文说明】逐仓保证金账户属性
        【功能描述】获取逐仓保证金账户操作接口
        【返回说明】IsolatedMarginAccount实例
        """
        return margin.IsolatedMarginAccount(self._client)

    async def get_order_book(self, symbol: str, limit: Optional[int] = None) -> dict:
        """
        【中文说明】获取订单簿数据
        【功能描述】查询指定交易对的订单簿深度信息
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - limit: 深度限制，可选，默认100，最大5000
        【返回说明】包含订单簿数据的字典
        """
        params: Dict[str, Any] = {"symbol": symbol}
        if limit is not None:
            params["limit"] = limit
        return await self._client.make_request("GET", "/api/v3/depth", qs_params=params)

    async def get_candlestick_data(
            self, symbol: str, interval: str, start_time: Optional[int] = None, end_time: Optional[int] = None,
            limit: Optional[int] = None
    ) -> list:
        """
        【中文说明】获取K线数据
        【功能描述】查询指定交易对的K线数据
        【参数说明】
        - symbol: 交易对符号，如"BTCUSDT"
        - interval: K线间隔，如"1m", "1h", "1d"等
        - start_time: 开始时间戳，可选
        - end_time: 结束时间戳，可选
        - limit: 返回数据条数限制，可选
        【返回说明】K线数据列表
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "interval": interval,
        }
        base.set_optional_params(params, (
            ("startTime", start_time),
            ("endTime", end_time),
            ("limit", limit),
        ))
        return await self._client.make_request("GET", "/api/v3/klines", qs_params=params)
