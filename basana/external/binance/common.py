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
【中文说明】Binance通用数据模型模块
【功能描述】定义Binance交易所API返回数据的通用数据模型和包装类
【使用场景】用于解析和处理Binance API返回的JSON数据，提供类型安全的访问接口
【注意事项】所有类都基于JSON数据构建，提供属性访问器来获取特定字段
"""

from decimal import Decimal
from typing import Dict, Optional, Sequence
import collections
import datetime

from . import helpers
from basana.core.enums import OrderOperation


class Balance:
    """
    【中文说明】账户余额数据类
    【功能描述】封装Binance账户余额信息，包括可用余额、锁定余额和总余额
    【使用场景】用于解析账户查询API返回的余额数据
    【注意事项】基于JSON数据构建，提供Decimal类型的数值访问
    """
    def __init__(self, json: dict):
        """
        【中文说明】初始化余额对象
        【功能描述】从Binance API返回的JSON数据创建余额对象
        【参数说明】
        - json: Binance账户余额JSON数据
        """
        self.json = json

    @property
    def available(self) -> Decimal:
        """
        【中文说明】可用余额
        【功能描述】获取账户中可用的余额数量
        【返回说明】Decimal类型的可用余额
        """
        return Decimal(self.json["free"])

    @property
    def total(self) -> Decimal:
        """
        【中文说明】总余额
        【功能描述】获取账户总余额（可用余额 + 锁定余额）
        【返回说明】Decimal类型的总余额
        """
        return self.available + self.locked

    @property
    def locked(self) -> Decimal:
        """
        【中文说明】锁定余额
        【功能描述】获取账户中被锁定的余额数量（如挂单中的资金）
        【返回说明】Decimal类型的锁定余额
        """
        return Decimal(self.json["locked"])


class Trade:
    """
    【中文说明】交易数据类
    【功能描述】封装Binance交易记录信息，包括交易ID、价格、数量、手续费等
    【使用场景】用于解析交易历史、订单成交记录等API返回的交易数据
    【注意事项】基于JSON数据构建，提供类型安全的属性访问
    """
    def __init__(self, json: dict):
        """
        【中文说明】初始化交易对象
        【功能描述】从Binance API返回的JSON数据创建交易对象
        【参数说明】
        - json: Binance交易记录JSON数据
        """
        self.json = json

    @property
    def id(self) -> str:
        """
        【中文说明】交易ID
        【功能描述】获取交易的唯一标识符
        【返回说明】字符串类型的交易ID
        """
        return str(self.json["id"])

    @property
    def order_id(self) -> str:
        """
        【中文说明】订单ID
        【功能描述】获取该交易所属的订单ID
        【返回说明】字符串类型的订单ID
        """
        return str(self.json["orderId"])

    @property
    def datetime(self) -> datetime.datetime:
        """
        【中文说明】交易时间
        【功能描述】获取交易发生的时间戳
        【返回说明】datetime类型的交易时间（UTC时区）
        """
        return helpers.timestamp_to_datetime(self.json["time"])

    @property
    def is_best_match(self) -> bool:
        """
        【中文说明】是否最佳匹配
        【功能描述】判断该交易是否是最佳价格匹配
        【返回说明】布尔值，True表示最佳匹配
        """
        return self.json["isBestMatch"]

    @property
    def is_buyer(self) -> bool:
        """
        【中文说明】是否为买方
        【功能描述】判断该交易是否为买入交易
        【返回说明】布尔值，True表示买入，False表示卖出
        """
        return self.json["isBuyer"]

    @property
    def is_maker(self) -> bool:
        """
        【中文说明】是否为挂单方
        【功能描述】判断该交易是否为挂单方（maker）
        【返回说明】布尔值，True表示挂单方，False表示吃单方
        """
        return self.json["isMaker"]

    @property
    def price(self) -> Decimal:
        """
        【中文说明】交易价格
        【功能描述】获取交易的成交价格
        【返回说明】Decimal类型的交易价格
        """
        return Decimal(self.json["price"])

    @property
    def amount(self) -> Decimal:
        """
        【中文说明】交易数量
        【功能描述】获取交易的成交数量（基础货币数量）
        【返回说明】Decimal类型的交易数量
        """
        return Decimal(self.json["qty"])

    @property
    def quote_amount(self) -> Decimal:
        """
        【中文说明】计价货币数量
        【功能描述】获取交易的计价货币总金额
        【返回说明】Decimal类型的计价货币数量
        """
        return Decimal(self.json["quoteQty"])

    @property
    def commission(self) -> Decimal:
        """
        【中文说明】手续费
        【功能描述】获取该交易产生的手续费
        【返回说明】Decimal类型的手续费金额
        """
        return Decimal(self.json["commission"])

    @property
    def commission_asset(self) -> str:
        """
        【中文说明】手续费币种
        【功能描述】获取手续费支付的币种
        【返回说明】字符串类型的手续费币种
        """
        return self.json["commissionAsset"]


class OrderWrapper:
    def __init__(self, json: dict):
        self.json = json

    @property
    def id(self) -> str:
        """The order id."""
        return str(self.json["orderId"])

    @property
    def client_order_id(self) -> str:
        """The client order id."""
        return self.json["clientOrderId"]

    @property
    def order_list_id(self) -> Optional[str]:
        """The order list id."""
        ret = self.json.get("orderListId")
        ret = None if ret in [None, -1] else str(ret)
        return ret

    @property
    def status(self) -> str:
        """The status.

        Check **Order status** in
        https://developers.binance.com/docs/binance-spot-api-docs/enums#order-status-status.
        """
        return self.json["status"]

    @property
    def is_open(self) -> bool:
        """True if the order is open, False otherwise."""
        return helpers.order_status_is_open(self.status)

    @property
    def amount(self) -> Decimal:
        """The amount."""
        return Decimal(self.json["origQty"])

    @property
    def amount_filled(self) -> Decimal:
        """The amount filled."""
        return Decimal(self.json["executedQty"])

    @property
    def quote_amount_filled(self) -> Decimal:
        """The amount filled in quote units."""
        return Decimal(self.json["cummulativeQuoteQty"])

    @property
    def limit_price(self) -> Optional[Decimal]:
        """The limit price."""
        return helpers.get_optional_decimal(self.json, "price", True)

    @property
    def stop_price(self) -> Optional[Decimal]:
        """The stop price."""
        return helpers.get_optional_decimal(self.json, "stopPrice", True)

    @property
    def time_in_force(self) -> Optional[str]:
        """The time in force.

        Check **Time in force** in
        https://developers.binance.com/docs/binance-spot-api-docs/enums#time-in-force-timeinforce.
        """
        return self.json.get("timeInForce")


class OrderInfo(OrderWrapper):
    def __init__(self, json: dict, trades: Sequence[Trade]):
        super().__init__(json)
        self.trades = trades
        self._fees: Dict[str, Decimal] = collections.defaultdict(Decimal)
        for trade in trades:
            if trade.commission:
                self._fees[trade.commission_asset] += trade.commission

    @property
    def operation(self) -> OrderOperation:
        """The operation."""
        return helpers.side_to_order_operation(self.json["side"])

    @property
    def amount_remaining(self) -> Decimal:
        """The amount remaining to be filled."""
        return self.amount - self.amount_filled

    @property
    def fill_price(self) -> Optional[Decimal]:
        """The fill price."""
        ret = None
        if self.amount_filled:
            ret = self.quote_amount_filled / self.amount_filled
        return ret

    @property
    def fees(self) -> Dict[str, Decimal]:
        """The fees."""
        return self._fees


class Fill:
    def __init__(self, json: dict):
        self.json = json

    @property
    def price(self) -> Decimal:
        """The price."""
        return Decimal(self.json["price"])

    @property
    def amount(self) -> Decimal:
        """The amount."""
        return Decimal(self.json["qty"])

    @property
    def commission(self) -> Decimal:
        """The commission."""
        return Decimal(self.json["commission"])

    @property
    def commission_asset(self) -> str:
        """The commission asset."""
        return self.json["commissionAsset"]


class CreatedOrder:
    def __init__(self, json: dict):
        self.json = json

    @property
    def id(self) -> str:
        """The order id."""
        return str(self.json["orderId"])

    @property
    def datetime(self) -> datetime.datetime:
        """The creation datetime."""
        return helpers.timestamp_to_datetime(self.json["transactTime"])

    @property
    def client_order_id(self) -> str:
        """The client order id."""
        return self.json["clientOrderId"]

    @property
    def limit_price(self) -> Optional[Decimal]:
        """The limit price.

        Only available for RESULT / FULL responses.
        """
        return helpers.get_optional_decimal(self.json, "price", True)

    @property
    def amount(self) -> Optional[Decimal]:
        """The amount.

        Only available for RESULT / FULL responses.
        """
        return helpers.get_optional_decimal(self.json, "origQty", False)

    @property
    def amount_filled(self) -> Optional[Decimal]:
        """The amount filled.

        Only available for RESULT / FULL responses.
        """
        return helpers.get_optional_decimal(self.json, "executedQty", False)

    @property
    def quote_amount_filled(self) -> Optional[Decimal]:
        """The amount filled in quote units.

        Only available for RESULT / FULL responses.
        """
        return helpers.get_optional_decimal(self.json, "cummulativeQuoteQty", False)

    @property
    def status(self) -> Optional[str]:
        """The status.

        Only available for RESULT / FULL responses.
        Check **Order status** in https://developers.binance.com/docs/binance-spot-api-docs/enums#order-status-status.
        """
        return self.json.get("status")

    @property
    def time_in_force(self) -> Optional[str]:
        """The time in force.

        Only available for RESULT / FULL responses.
        Check **Time in force** in
        https://developers.binance.com/docs/binance-spot-api-docs/enums#time-in-force-timeinforce.
        """
        return self.json.get("timeInForce")

    @property
    def is_open(self) -> bool:
        """True if the order is open, False otherwise.

        Only available for RESULT / FULL responses.
        """
        assert self.status is not None, "status not set"
        return helpers.order_status_is_open(self.status)


class CanceledOrder(OrderWrapper):
    @property
    def operation(self) -> OrderOperation:
        """The operation."""
        return helpers.side_to_order_operation(self.json["side"])

    @property
    def type(self) -> str:
        """The type of order.

        Check **Order types** in
        https://developers.binance.com/docs/binance-spot-api-docs/enums#order-types-ordertypes-type.
        """
        return self.json["type"]


class OpenOrder(OrderWrapper):
    @property
    def datetime(self) -> datetime.datetime:
        """The creation datetime."""
        return helpers.timestamp_to_datetime(self.json["time"])

    @property
    def operation(self) -> OrderOperation:
        """The operation."""
        return helpers.side_to_order_operation(self.json["side"])

    @property
    def type(self) -> str:
        """The type of order.

        Check **Order types** in
        https://developers.binance.com/docs/binance-spot-api-docs/enums#order-types-ordertypes-type.
        """
        return self.json["type"]


class OCOOrderWrapper:
    def __init__(self, json: dict):
        self.json = json

    @property
    def order_list_id(self) -> str:
        """The order list id."""
        return str(self.json["orderListId"])

    @property
    def client_order_list_id(self) -> str:
        """A client id for the order list."""
        return str(self.json["listClientOrderId"])

    @property
    def datetime(self) -> datetime.datetime:
        """The creation datetime."""
        return helpers.timestamp_to_datetime(self.json["transactionTime"])

    @property
    def is_open(self) -> bool:
        """True if the order is open, False otherwise."""
        return helpers.oco_order_status_is_open(self.json["listOrderStatus"])

    @property
    def limit_order_id(self) -> str:
        """The id for the limit order."""
        order_ids = [
            str(order["orderId"])
            for order in self.json.get("orderReports", [])
            if order["type"] in ("LIMIT", "LIMIT_MAKER")
        ]
        return order_ids[0]

    @property
    def stop_loss_order_id(self) -> str:
        """The id for the stop loss order."""
        order_ids = [
            str(order["orderId"])
            for order in self.json.get("orderReports", [])
            if order["type"] in ("STOP_LOSS", "STOP_LOSS_LIMIT")
        ]
        return order_ids[0]


class CreatedOCOOrder(OCOOrderWrapper):
    pass


class OCOOrderInfo(OCOOrderWrapper):
    pass


class CanceledOCOOrder(OCOOrderWrapper):
    pass
