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
保证金借贷模块

此模块提供了回测环境中的保证金借贷功能，包括：
- 保证金借贷条件定义
- 保证金借贷实现
- 保证金借贷策略
- 保证金水平检查

主要类：
- MarginLoanConditions: 保证金借贷条件
- MarginLoan: 保证金借贷实现
- MarginLoans: 保证金借贷策略
- CheckMarginLevel: 保证金水平检查规则
"""


from decimal import Decimal
from typing import Dict, Optional
import dataclasses
import datetime
import uuid

from basana.backtesting import account_balances, errors, loan_mgr, prices
from basana.backtesting.lending import base
from basana.backtesting.value_map import ValueMap, ValueMapDict


@dataclasses.dataclass
class MarginLoanConditions:
    """保证金借贷条件数据类
    
    定义保证金借贷的具体条件参数。
    """
    
    #: 利息资产符号
    interest_symbol: str
    #: 利息百分比
    interest_percentage: Decimal
    #: 利息计算周期
    interest_period: datetime.timedelta
    #: 最低收取利息
    min_interest: Decimal


class MarginLoan(base.Loan):
    """保证金借贷实现类
    
    继承自Loan基类，实现保证金借贷的具体逻辑。
    """
    
    def __init__(
            self, id: str, borrowed_symbol: str,  borrowed_amount: Decimal, created_at: datetime.datetime,
            conditions: MarginLoanConditions
    ):
        """初始化保证金借贷
        
        :param id: 借贷ID
        :param borrowed_symbol: 借入的资产符号
        :param borrowed_amount: 借入的资产数量
        :param created_at: 创建时间
        :param conditions: 保证金借贷条件
        """
        super().__init__(id, borrowed_symbol, borrowed_amount, created_at)
        self._conditions = conditions

    def calculate_interest(self, at: datetime.datetime, prices: prices.Prices) -> Dict[str, Decimal]:
        """计算利息
        
        :param at: 计算利息的时间点
        :param prices: 价格源
        :return: 利息映射字典
        :raises AssertionError: 如果计算时间早于创建时间
        """
        assert at >= self._created_at

        interest = self._conditions.interest_percentage / Decimal(100) * self.borrowed_amount
        if self._conditions.interest_period:
            time_ellapsed = at - self._created_at
            interest *= Decimal(time_ellapsed.total_seconds() / self._conditions.interest_period.total_seconds())

        # 如果利息符号与借入符号不同，进行货币转换
        if self._conditions.interest_symbol != self.borrowed_symbol:
            interest = prices.convert(interest, self._borrowed_symbol, self._conditions.interest_symbol)

        interest = max(interest, self._conditions.min_interest)
        return {self._conditions.interest_symbol: interest}

    def calculate_collateral(self, prices: prices.Prices) -> Dict[str, Decimal]:
        """计算抵押品价值
        
        保证金借贷的抵押品在账户级别通过CheckMarginLevel进行管理。
        
        :param prices: 价格源
        :return: 空字典，抵押品在账户级别管理
        """
        # 抵押品在账户级别通过CheckMarginLevel进行管理
        return {}


class MarginLoans(base.LendingStrategy):
    """保证金借贷策略类
    
    此策略将使用账户资产作为借贷的抵押品。
    
    :param quote_symbol: 用于标准化余额的资产符号
    :param margin_requirement: 抵押品价值相对于总头寸的最小阈值
    :param default_conditions: 默认的保证金借贷条件
    """
    
    def __init__(
            self, quote_symbol: str, margin_requirement: Decimal,
            default_conditions: Optional[MarginLoanConditions] = None
    ):
        """初始化保证金借贷策略
        
        :param quote_symbol: 用于标准化余额的资产符号
        :param margin_requirement: 抵押品价值相对于总头寸的最小阈值
        :param default_conditions: 默认的保证金借贷条件
        :raises AssertionError: 如果保证金要求小于等于0
        """
        assert margin_requirement > 0, "Margin requirement must be greater than zero"

        self._quote_symbol = quote_symbol
        self._margin_requirement = margin_requirement
        self._conditions: Dict[str, MarginLoanConditions] = {}
        self._default_conditions = default_conditions
        self._loan_mgr: Optional[loan_mgr.LoanManager] = None
        self._exchange_ctx: Optional[base.ExchangeContext] = None

    def set_conditions(self, symbol: str, conditions: MarginLoanConditions):
        """设置特定资产的借贷条件
        
        :param symbol: 要设置条件的资产符号
        :param conditions: 借贷条件
        """
        self._conditions[symbol] = conditions

    def get_conditions(self, symbol: str) -> MarginLoanConditions:
        """获取特定资产的借贷条件
        
        :param symbol: 资产符号
        :return: 借贷条件
        :raises Error: 如果没有找到该资产的借贷条件
        """
        conditions = self._conditions.get(symbol, self._default_conditions)
        if not conditions:
            raise errors.Error(f"No lending conditions for {symbol}")
        return conditions

    def set_exchange_context(self, loan_mgr: loan_mgr.LoanManager, exchange_context: base.ExchangeContext):
        """设置交易所上下文
        
        :param loan_mgr: 借贷管理器
        :param exchange_context: 交易所上下文
        """
        self._loan_mgr = loan_mgr
        self._exchange_ctx = exchange_context
        self._exchange_ctx.account_balances.push_update_rule(CheckMarginLevel(self))

    def create_loan(self, symbol: str, amount: Decimal, created_at: datetime.datetime) -> base.Loan:
        """创建借贷
        
        :param symbol: 借入的资产符号
        :param amount: 借入的资产数量
        :param created_at: 创建时间
        :return: 保证金借贷实例
        """
        conditions = self.get_conditions(symbol)
        return MarginLoan(uuid.uuid4().hex, symbol, amount, created_at, conditions)

    @property
    def margin_level(self) -> Decimal:
        """获取当前保证金水平
        
        :return: 当前保证金水平
        :raises AssertionError: 如果尚未连接到交易所
        """
        assert self._exchange_ctx, "Not yet connected with the exchange"
        acc_balances = self._exchange_ctx.account_balances
        return self.calculate_margin_level(
            acc_balances.balances, acc_balances.holds, acc_balances.borrowed
        )

    def calculate_margin_level(
            self, updated_balances: ValueMapDict, updated_holds: ValueMapDict, updated_borrowed: ValueMapDict
    ) -> Decimal:
        """计算保证金水平
        
        :param updated_balances: 更新后的余额
        :param updated_holds: 更新后的冻结余额
        :param updated_borrowed: 更新后的借入余额
        :return: 保证金水平
        :raises AssertionError: 如果尚未连接到交易所
        """
        assert self._exchange_ctx and self._loan_mgr, "Not yet connected with the exchange"

        # 如果尚未借入任何资产，保证金水平为无限大
        if all(v == Decimal(0) for v in updated_borrowed.values()):
            # used_margin = 0,  margin_level = Infinity
            return Decimal("Infinity")

        # 计算未偿还利息
        outstanding_interest = ValueMap()
        for loan in self._loan_mgr.get_loans(is_open=True):
            outstanding_interest += loan.outstanding_interest
        outstanding_interest = self._exchange_ctx.prices.convert_value_map(outstanding_interest, self._quote_symbol)

        # 计算保证金水平
        borrowed = self._exchange_ctx.prices.convert_value_map(updated_borrowed, self._quote_symbol)
        total_position_size = self._exchange_ctx.prices.convert_value_map(updated_balances, self._quote_symbol)
        total_position_size -= outstanding_interest
        equity = total_position_size - borrowed
        used_margin = Decimal(sum(total_position_size.values())) * self._margin_requirement
        margin_level = Decimal(sum(equity.values())) / used_margin * Decimal(100)
        return margin_level


class CheckMarginLevel(account_balances.UpdateRule):
    """保证金水平检查规则类
    
    继承自UpdateRule，用于检查保证金水平是否满足要求。
    """
    
    def __init__(self, margin_loans: MarginLoans):
        """初始化保证金水平检查规则
        
        :param margin_loans: 保证金借贷策略实例
        """
        self._margin_loans = margin_loans
        self._threshold = Decimal(100)

    def check(
            self, updated_balances: ValueMap, updated_holds: ValueMap, updated_borrowed: ValueMap,
            delta_balances: ValueMap, delta_holds: ValueMap, delta_borrowed: ValueMap
    ):
        """检查保证金水平
        
        当借入金额增加时，检查保证金水平是否满足要求。
        
        :param updated_balances: 更新后的余额
        :param updated_holds: 更新后的冻结余额
        :param updated_borrowed: 更新后的借入余额
        :param delta_balances: 余额变化量
        :param delta_holds: 冻结余额变化量
        :param delta_borrowed: 借入余额变化量
        :raises NotEnoughBalance: 如果保证金水平低于阈值
        """
        # 如果我们在增加任何借入金额，需要检查保证金水平
        if any(v > 0 for v in delta_borrowed.values()):
            margin_level = self._margin_loans.calculate_margin_level(updated_balances, updated_holds, updated_borrowed)
            if margin_level < self._threshold:
                raise errors.NotEnoughBalance(f"Margin level too low {margin_level}")
