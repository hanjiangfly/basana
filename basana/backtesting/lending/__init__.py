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
回测借贷子模块

此模块提供了回测环境中的借贷功能，包括：
- 借贷策略抽象
- 借贷信息管理
- 保证金借贷条件
- 无借贷策略

主要类：
- LendingStrategy: 借贷策略基类
- LoanInfo: 借贷信息类
- NoLoans: 无借贷策略
- MarginLoanConditions: 保证金借贷条件
- MarginLoans: 保证金借贷管理
"""

# ruff: noqa

from .base import (
    LendingStrategy,
    LoanInfo,
    NoLoans,
)


from .margin import (
    MarginLoanConditions,
    MarginLoans,
)
