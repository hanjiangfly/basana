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
【中文说明】账户余额管理模块

【功能描述】
提供交易账户余额管理功能，包括可用余额、冻结余额和借贷余额的管理。
支持余额更新规则验证，确保账户状态始终有效。

【核心组件】
- UpdateRule抽象基类：余额更新规则接口
- NonZero规则：确保余额非负验证
- ValidHold规则：确保冻结余额不超过可用余额
- AccountBalances类：账户余额管理器

【账户状态】
- 可用余额（balances）：可自由使用的资金
- 冻结余额（holds）：已冻结但未使用的资金（如挂单）
- 借贷余额（borrowed）：从交易所借入的资金

【使用场景】
- 回测系统中的账户状态管理
- 订单执行前的资金验证
- 借贷和保证金交易管理
- 风险控制和资金安全验证

【注意事项】
- 使用Decimal进行精确数值计算
- 支持自定义更新规则扩展
- 遵循严格的余额验证机制
"""

from decimal import Decimal
from typing import List
import abc
import itertools

from basana.backtesting import errors
from basana.backtesting.value_map import ValueMap, ValueMapDict


class UpdateRule(metaclass=abc.ABCMeta):
    """
    【中文说明】余额更新规则抽象基类
    
    【功能描述】
    定义余额更新规则的接口，用于验证账户余额更新的有效性。
    这是一个抽象基类，需要子类实现具体的验证逻辑。
    
    【设计原则】
    - 开闭原则：支持通过继承扩展新的验证规则
    - 单一职责：每个规则只负责一种验证逻辑
    - 接口隔离：提供清晰的验证接口
    
    【使用场景】
    - 自定义余额验证规则
    - 风险控制规则实现
    - 交易所特定规则适配
    """

    @abc.abstractmethod
    def check(
            self, updated_balances: ValueMap, updated_holds: ValueMap, updated_borrowed: ValueMap,
            delta_balances: ValueMap, delta_holds: ValueMap, delta_borrowed: ValueMap
    ):
        """
        【中文说明】验证余额更新
        
        【功能描述】
        抽象方法，验证账户余额更新是否有效。
        
        【参数说明】
        - updated_balances: ValueMap - 更新后的可用余额
        - updated_holds: ValueMap - 更新后的冻结余额
        - updated_borrowed: ValueMap - 更新后的借贷余额
        - delta_balances: ValueMap - 可用余额变化量
        - delta_holds: ValueMap - 冻结余额变化量
        - delta_borrowed: ValueMap - 借贷余额变化量
        
        【异常情况】
        - 如果验证失败，抛出相应的异常
        
        【注意事项】
        - 子类必须实现此方法
        - 验证失败时应抛出描述性异常
        """
        raise NotImplementedError()


class NonZero(UpdateRule):
    def check(
            self, updated_balances: ValueMap, updated_holds: ValueMap, updated_borrowed: ValueMap,
            delta_balances: ValueMap, delta_holds: ValueMap, delta_borrowed: ValueMap
    ):
        # balance >= 0
        for symbol, value in updated_balances.items():
            if value < Decimal(0):
                raise errors.NotEnoughBalance(f"Not enough {symbol} available")
        # hold >= 0
        for symbol, value in updated_holds.items():
            if value < Decimal(0):
                raise errors.Error(f"hold update amount for {symbol} is invalid")
        # borrowed >= 0
        for symbol, value in updated_borrowed.items():
            if value < Decimal(0):
                raise errors.Error(f"borrowed update amount for {symbol} is invalid")


class ValidHold(UpdateRule):
    # * hold <= balance
    def check(
            self, updated_balances: ValueMap, updated_holds: ValueMap, updated_borrowed: ValueMap,
            delta_balances: ValueMap, delta_holds: ValueMap, delta_borrowed: ValueMap
    ):
        symbols = set(itertools.chain(updated_holds.keys(), updated_balances.keys()))
        for symbol in symbols:
            updated_hold = updated_holds.get(symbol, Decimal(0))
            updated_balance = updated_balances.get(symbol, Decimal(0))
            if updated_hold > updated_balance:
                raise errors.NotEnoughBalance(f"Not enough {symbol} available to hold")


class AccountBalances:
    def __init__(self, initial_balances: ValueMapDict):
        self.balances = ValueMap({
            symbol: balance for symbol, balance in initial_balances.items() if balance >= 0
        })
        self.holds = ValueMap()
        self.borrowed = ValueMap({
            symbol: -balance for symbol, balance in initial_balances.items() if balance < 0
        })
        self._update_rules: List[UpdateRule] = [
            NonZero(),
            ValidHold()
        ]

    def push_update_rule(self, update_rule: UpdateRule):
        self._update_rules.append(update_rule)

    def update(
            self, balance_updates: ValueMapDict = {}, hold_updates: ValueMapDict = {},
            borrowed_updates: ValueMapDict = {}
    ):
        updated_balances = self.balances + balance_updates
        updated_holds = self.holds + hold_updates
        updated_borrowed = self.borrowed + borrowed_updates

        for rule in self._update_rules:
            rule.check(
                updated_balances, updated_holds, updated_borrowed,
                ValueMap(balance_updates), ValueMap(hold_updates), ValueMap(borrowed_updates)
            )

        # Update if no error ocurred.
        self.balances = updated_balances
        self.holds = updated_holds
        self.borrowed = updated_borrowed

    def get_symbols(self) -> List[str]:
        symbols = set(self.balances.keys())
        symbols.update(self.holds.keys())
        symbols.update(self.borrowed.keys())
        return list(symbols)

    def get_available_balance(self, symbol: str) -> Decimal:
        return self.balances.get(symbol, Decimal(0)) - self.holds.get(symbol, Decimal(0))

    def get_balance_on_hold(self, symbol: str) -> Decimal:
        return self.holds.get(symbol, Decimal(0))

    def get_borrowed_balance(self, symbol: str) -> Decimal:
        return self.borrowed.get(symbol, Decimal(0))
