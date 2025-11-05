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
【中文说明】Binance客户端基础模块
【功能描述】提供Binance API客户端的基础功能，包括错误处理、HTTP请求和参数设置
【使用场景】作为其他Binance客户端模块的基础类
【注意事项】包含API请求的通用逻辑和错误处理机制
"""

from decimal import Decimal
from typing import Any, Dict, Optional, Sequence, Tuple
from urllib.parse import urljoin
import asyncio
import copy
import time

import aiohttp

from basana.core import token_bucket, helpers as core_helpers
from basana.core.config import get_config_value
from basana.external.binance import config, helpers


class Error(Exception):
    """
    【中文说明】Binance API错误异常类
    【功能描述】封装Binance交易所返回的错误信息
    【使用场景】在API请求失败时抛出
    【注意事项】包含HTTP状态码、错误代码和错误消息
    """
    def __init__(self, msg: str, code: Optional[int], resp: aiohttp.ClientResponse, json_response: Optional[Any]):
        """
        【中文说明】初始化错误异常
        【参数说明】
        - msg: 错误消息
        - code: 错误代码，可选
        - resp: HTTP响应对象
        - json_response: JSON响应体，可选
        """
        super().__init__(msg)
        #: 【中文说明】错误消息
        self.msg = msg
        #: 【中文说明】错误代码，如果可用
        self.code = code
        #: 【中文说明】HTTP状态码
        self.http_status = resp.status
        #: 【中文说明】HTTP原因短语
        self.http_reason = resp.reason
        #: 【中文说明】响应体，如果是JSON格式
        self.json_response = json_response


def raise_for_error(resp: aiohttp.ClientResponse, json_response):
    """
    【中文说明】检查并抛出API错误
    【功能描述】检查HTTP响应和JSON响应，如果存在错误则抛出Error异常
    【参数说明】
    - resp: HTTP响应对象
    - json_response: JSON响应体
    """
    msg = None
    code = None
    if isinstance(json_response, dict):
        msg = json_response.get("msg")
        code = json_response.get("code")
    if msg is None and not resp.ok:
        msg = "{} {}".format(resp.status, resp.reason)
    if msg is not None:
        raise Error(msg, code, resp, json_response)


class BaseClient:
    """
    【中文说明】Binance基础客户端类
    【功能描述】提供Binance API的基础HTTP请求功能，包括认证、限流和错误处理
    【使用场景】作为其他Binance客户端类的基类
    【注意事项】API密钥和密钥必须同时设置或同时不设置
    """
    def __init__(
            self, api_key: Optional[str] = None, api_secret: Optional[str] = None,
            session: Optional[aiohttp.ClientSession] = None, tb: Optional[token_bucket.TokenBucketLimiter] = None,
            config_overrides: dict = {}
    ):
        """
        【中文说明】初始化基础客户端
        【参数说明】
        - api_key: API密钥，可选
        - api_secret: API密钥，可选
        - session: aiohttp客户端会话，可选
        - tb: 令牌桶限流器，可选
        - config_overrides: 配置覆盖项，可选
        【注意事项】api_key和api_secret必须同时设置或同时不设置
        """
        assert not ((api_key is None) ^ (api_secret is None)), \
            "Both api_key and api_secret should be set, or none of them"

        self._api_key = api_key
        self._api_secret = api_secret
        self._session = session
        self._tb = tb
        self._config_overrides = config_overrides

    async def make_request(
            self, method: str, path: str, send_key: bool = False, send_sig: bool = False,
            qs_params: Dict[str, Any] = {}, data: Dict[str, Any] = {}
    ) -> Any:
        """
        【中文说明】执行HTTP请求
        【功能描述】向Binance API发送HTTP请求，支持认证、限流和错误处理
        【参数说明】
        - method: HTTP方法，如"GET", "POST", "DELETE", "PUT"
        - path: API路径，如"/api/v3/account"
        - send_key: 是否发送API密钥，可选
        - send_sig: 是否发送签名，可选
        - qs_params: 查询字符串参数，可选
        - data: 请求体数据，可选
        【返回说明】JSON响应数据
        【注意事项】如果send_sig为True，会自动添加时间戳和签名
        """
        if self._tb and (sleep_time := self._tb.consume()):
            await asyncio.sleep(sleep_time)

        async with core_helpers.use_or_create_session(session=self._session) as session:
            headers = {}
            session_method = {
                "DELETE": session.delete,
                "GET": session.get,
                "POST": session.post,
                "PUT": session.put,
            }.get(method)
            assert session_method is not None

            base_url = get_config_value(config.DEFAULTS, "api.http.base_url", overrides=self._config_overrides)
            timeout = get_config_value(config.DEFAULTS, "api.http.timeout", overrides=self._config_overrides)
            url = urljoin(base_url, path)

            if send_key or send_sig:
                assert self._api_key, "api_key not set"

                headers["X-MBX-APIKEY"] = self._api_key

            if send_sig:
                assert self._api_secret, "api_secret not set"

                qs_params = copy.copy(qs_params)
                # 【中文说明】签名和时间戳应该放在查询字符串中，时间戳应该包含在签名中
                qs_params["timestamp"] = int(round(time.time() * 1000))
                qs_params["signature"] = helpers.get_signature(self._api_secret, qs_params=qs_params, data=data)

            form_data = None if not data else aiohttp.FormData(data)
            async with session_method(url, headers=headers, params=qs_params, data=form_data, timeout=timeout) as resp:
                # print(await resp.text())
                json_response = None
                if (ct := resp.headers.get("Content-Type")) and ct.lower().find("application/json") == 0:
                    json_response = await resp.json()
                raise_for_error(resp, json_response)
                return json_response


def set_optional_params(params: Dict[str, Any], tuples: Sequence[Tuple[str, Any]]):
    """
    【中文说明】设置可选参数
    【功能描述】将可选参数添加到参数字典中，跳过None值，将Decimal转换为字符串
    【参数说明】
    - params: 参数字典
    - tuples: 参数元组序列，格式为[(参数名, 参数值), ...]
    """
    for k, v in tuples:
        if v is None:
            continue
        if isinstance(v, Decimal):
            v = str(v)
        params[k] = v
