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
回测费用模块

提供回测系统中的费用计算策略，包括：
- 无费用策略
- 百分比费用策略

支持自定义费用计算逻辑。
"""

from decimal import Decimal
from typing import Dict
import abc

from . import orders


class FeeStrategy(metaclass=abc.ABCMeta):
    """费用策略基类。

    建模费用方案的策略基类。

    .. note::

        * 这是一个基类，不应直接使用。
    """

    @abc.abstractmethod
    def calculate_fees(
            self, order: orders.Order, balance_updates: Dict[str, Decimal]
    ) -> Dict[str, Decimal]:
        """计算订单的费用。

        :param order: 订单对象。
        :param balance_updates: 余额更新字典。
        :return: 费用字典，键为货币符号，值为费用金额（负数表示扣除）。
        """
        raise NotImplementedError()


class NoFee(FeeStrategy):
    """无费用策略。

    此策略不对交易应用任何费用。
    """

    def calculate_fees(self, order: orders.Order, balance_updates: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """计算费用（返回空字典，表示无费用）。

        :param order: 订单对象。
        :param balance_updates: 余额更新字典。
        :return: 空字典。
        """
        return {}


class Percentage(FeeStrategy):
    """百分比费用策略。

    此策略对每笔交易应用固定百分比费用，以计价货币计算。

    :param percentage: 应用的百分比。
    :param min_fee: 最低费用金额，以计价货币计算。
    """

    def __init__(self, percentage: Decimal, min_fee: Decimal = Decimal(0)):
        assert percentage >= 0 and percentage < 100, f"无效的百分比 {percentage}"
        assert min_fee >= 0, f"最低费用不能为负数 {min_fee}"
        self._percentage = percentage
        self._min_fee = min_fee

    def calculate_fees(self, order: orders.Order, balance_updates: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """计算百分比费用。

        :param order: 订单对象。
        :param balance_updates: 余额更新字典。
        :return: 费用字典。
        """
        ret = {}

        # 费用始终以计价货币计算。
        symbol = order.pair.quote_symbol

        # 由于之前的成交可能已经进行了舍入，费用可能被多收。因此我们计算应收取的总费用，
        # 然后减去已经收取的费用。
        charged_fee_amount = order.fees.get(symbol, Decimal(0))
        assert charged_fee_amount <= Decimal(0), "费用应始终为负数"
        total_quote_amount = order.balance_updates.get(symbol, Decimal(0)) + balance_updates.get(symbol, Decimal(0))
        total_fee_amount = -max(abs(total_quote_amount) * self._percentage / Decimal(100), self._min_fee)
        pending_fee = total_fee_amount - charged_fee_amount
        if pending_fee < Decimal(0):
            ret[symbol] = pending_fee

        return ret
