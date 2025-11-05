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
【中文说明】Binance辅助工具模块
【功能描述】提供Binance交易所API相关的通用工具函数和转换函数
【使用场景】用于API签名、数据转换、状态判断等通用操作
【功能分类】
- API认证：HMAC签名生成
- 数据转换：交易对转换、时间戳转换、数值转换
- 状态判断：订单状态、OCO订单状态
- 枚举映射：订单操作类型转换
【注意事项】这些函数是Binance API集成的核心工具组件
"""

from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode
import datetime
import hashlib
import hmac

from basana.core import dt, pair
from basana.core.enums import OrderOperation


def get_signature(api_secret: str, qs_params: dict = {}, data: dict = {}) -> str:
    total_params = ""
    if qs_params:
        total_params += urlencode(qs_params)
    if data:
        total_params += urlencode(data)
    return hmac.new(api_secret.encode(), msg=total_params.encode("utf-8"), digestmod=hashlib.sha256).hexdigest()


def pair_to_symbol(pair: pair.Pair) -> str:
    return "{}{}".format(pair.base_symbol.upper(), pair.quote_symbol.upper())


def order_operation_to_side(operation: OrderOperation) -> str:
    return {
        OrderOperation.BUY: "BUY",
        OrderOperation.SELL: "SELL",
    }[operation]


def side_to_order_operation(side: str) -> OrderOperation:
    return {
        "BUY": OrderOperation.BUY,
        "SELL": OrderOperation.SELL,
    }[side]


def order_status_is_open(order_status: str) -> bool:
    # Not doing `order_status in ["NEW", "PARTIALLY_FILLED", "PENDING_CANCEL"]` to detect unkown states.
    is_open = {
        "NEW": True,
        "PARTIALLY_FILLED": True,
        "FILLED": False,
        "CANCELED": False,
        "PENDING_CANCEL": True,
        "REJECTED": False,
        "EXPIRED": False,
    }.get(order_status)
    assert is_open is not None, "No mapping for {} order status".format(order_status)
    return is_open


def oco_order_status_is_open(list_order_status: str) -> bool:
    # Not doing `list_order_status in ["EXECUTING"]` to detect unkown states.
    is_open = {
        "EXECUTING": True,
        "ALL_DONE": False,
        "REJECT": False,
    }.get(list_order_status)
    assert is_open is not None, "No mapping for {} list order status".format(list_order_status)
    return is_open


def get_optional_decimal(mapping: dict, key: str, skip_zero: bool) -> Optional[Decimal]:
    ret = None
    price = mapping.get(key)
    if price is not None:
        price = Decimal(price)
        ret = None if price == Decimal(0) and skip_zero else price
    return ret


def timestamp_to_datetime(timestamp: int) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(timestamp / 1e3, tz=datetime.timezone.utc)


def datetime_to_timestamp(datetime: datetime.datetime) -> int:
    return int(dt.to_utc_timestamp(datetime) * 1e3)
