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
回测借贷基类模块

此模块定义了回测环境中的借贷系统核心抽象：
- 借贷信息数据结构
- 借贷抽象基类
- 借贷策略接口
- 无借贷策略实现

主要类：
- LoanInfo: 借贷信息数据类
- Loan: 借贷抽象基类
- ExchangeContext: 交易所上下文
- LendingStrategy: 借贷策略基类
- NoLoans: 无借贷策略
"""

from decimal import Decimal
from typing import Dict
import abc
import dataclasses
import datetime

from basana.backtesting import account_balances, config, errors, prices
from basana.backtesting.value_map import ValueMap, ValueMapDict
from basana.core import dispatcher


@dataclasses.dataclass
class LoanInfo:
    """借贷信息数据类
    
    包含借贷的完整信息，用于查询和展示借贷状态。
    """
    
    #: 借贷ID
    id: str
    #: 借贷是否开放，True表示开放，False表示关闭
    is_open: bool
    #: 借入的资产符号
    borrowed_symbol: str
    #: 借入的资产数量
    borrowed_amount: Decimal
    #: 未偿还的利息，仅对开放借贷有效
    outstanding_interest: Dict[str, Decimal]
    #: 已支付的利息，仅对关闭借贷有效
    paid_interest: Dict[str, Decimal]


class Loan(metaclass=abc.ABCMeta):
    """借贷抽象基类
    
    定义借贷的核心行为和属性，具体借贷类型需要继承此类。
    """
    
    def __init__(
            self, id: str, borrowed_symbol: str,  borrowed_amount: Decimal, created_at: datetime.datetime
    ):
        """初始化借贷
        
        :param id: 借贷ID
        :param borrowed_symbol: 借入的资产符号
        :param borrowed_amount: 借入的资产数量
        :param created_at: 创建时间
        :raises AssertionError: 如果借入数量小于等于0
        """
        assert borrowed_amount > Decimal(0), f"Invalid amount {borrowed_amount}"

        self._id = id
        self._borrowed_symbol = borrowed_symbol
        self._borrowed_amount = borrowed_amount
        self._is_open = True
        self._created_at = created_at
        self._paid_interest = ValueMap()

    @property
    def id(self) -> str:
        """获取借贷ID
        
        :return: 借贷ID字符串
        """
        return self._id

    @property
    def is_open(self) -> bool:
        """检查借贷是否开放
        
        :return: 如果借贷开放则为True，否则为False
        """
        return self._is_open

    @property
    def borrowed_symbol(self) -> str:
        """获取借入的资产符号
        
        :return: 资产符号字符串
        """
        return self._borrowed_symbol

    @property
    def borrowed_amount(self) -> Decimal:
        """获取借入的资产数量
        
        :return: 借入的资产数量
        """
        return self._borrowed_amount

    @property
    def created_at(self) -> datetime.datetime:
        """获取借贷创建时间
        
        :return: 创建时间
        """
        return self._created_at

    @property
    def paid_interest(self) -> ValueMapDict:
        """获取已支付的利息
        
        :return: 已支付的利息映射字典
        """
        return self._paid_interest

    def close(self):
        """关闭借贷
        
        将借贷状态设置为关闭，不再计算利息。
        :raises AssertionError: 如果借贷已经关闭
        """
        assert self._is_open
        self._is_open = False

    def add_paid_interest(self, interest: ValueMapDict):
        """添加已支付的利息
        
        :param interest: 要添加的利息映射字典
        """
        self._paid_interest += interest

    @abc.abstractmethod
    def calculate_interest(self, at: datetime.datetime, prices: prices.Prices) -> ValueMapDict:
        """计算利息
        
        :param at: 计算利息的时间点
        :param prices: 价格源
        :return: 利息映射字典
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def calculate_collateral(self, prices: prices.Prices) -> ValueMapDict:
        """计算抵押品价值
        
        :param prices: 价格源
        :return: 抵押品价值映射字典
        """
        raise NotImplementedError()


@dataclasses.dataclass
class ExchangeContext:
    """交易所上下文数据类
    
    包含借贷策略所需的交易所服务组件。
    """
    
    #: 回测分发器
    dispatcher: dispatcher.BacktestingDispatcher
    #: 账户余额管理器
    account_balances: account_balances.AccountBalances
    #: 价格源
    prices: prices.Prices
    #: 配置管理器
    config: config.Config


class LendingStrategy(metaclass=abc.ABCMeta):
    """借贷策略基类
    
    定义借贷策略的通用接口，具体借贷策略需要继承此类。
    """

    def set_exchange_context(self, loan_mgr, exchange_context: ExchangeContext):
        """设置交易所上下文
        
        在交易所初始化期间调用此方法，为借贷策略提供后续使用这些服务的机会。
        
        :param loan_mgr: 借贷管理器
        :param exchange_context: 交易所上下文
        """
        pass

    @abc.abstractmethod
    def create_loan(self, symbol: str, amount: Decimal, created_at: datetime.datetime) -> Loan:
        """创建借贷
        
        :param symbol: 借入的资产符号
        :param amount: 借入的资产数量
        :param created_at: 创建时间
        :return: 借贷实例
        """
        raise NotImplementedError()


class NoLoans(LendingStrategy):
    """无借贷策略
    
    表示不支持借贷的策略实现。
    """

    def create_loan(self, symbol: str, amount: Decimal, created_at: datetime.datetime) -> Loan:
        """创建借贷（不支持）
        
        :param symbol: 借入的资产符号
        :param amount: 借入的资产数量
        :param created_at: 创建时间
        :raises Error: 总是抛出错误，表示不支持借贷
        """
        raise errors.Error("Lending is not supported")
