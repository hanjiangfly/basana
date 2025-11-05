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
回测配置模块

提供回测系统的配置管理功能，包括：
- 货币符号精度配置
- 交易对精度配置
- 默认配置设置

支持通过单个货币符号配置自动构建交易对配置。
"""

from typing import Dict, Optional
import dataclasses

from basana.backtesting import errors
from basana.core.pair import Pair, PairInfo


@dataclasses.dataclass(frozen=True)
class SymbolInfo:
    """货币符号信息。

    包含货币符号的精度配置。

    :param precision: 小数精度位数
    """
    precision: int


class Config:
    """回测配置管理器。

    管理回测系统中的货币符号和交易对配置信息。

    :param default_symbol_info: 默认货币符号信息
    :param default_pair_info: 默认交易对信息
    """
    def __init__(self, default_symbol_info: Optional[SymbolInfo] = None, default_pair_info: Optional[PairInfo] = None):
        self._symbol_info: Dict[str, SymbolInfo] = {}
        self._default_symbol_info = default_symbol_info
        self._pair_info: Dict[Pair, PairInfo] = {}
        self._default_pair_info = default_pair_info

    def set_pair_info(self, pair: Pair, pair_info: PairInfo):
        """设置交易对信息。

        :param pair: 交易对
        :param pair_info: 交易对信息
        """
        self._pair_info[pair] = pair_info

    def get_pair_info(self, pair: Pair) -> PairInfo:
        """获取交易对信息。

        如果未设置特定交易对的配置，将尝试使用单个货币符号的配置构建交易对信息。

        :param pair: 交易对
        :return: 交易对信息
        :raises errors.Error: 如果找不到交易对配置
        """
        ret = self._pair_info.get(pair)

        # 如果没有此特定交易对的配置，我们将尝试使用单个货币符号的配置来构建它。
        if ret is None:
            base_symbol_config = self._symbol_info.get(pair.base_symbol)
            quote_symbol_config = self._symbol_info.get(pair.quote_symbol)
            if base_symbol_config and quote_symbol_config:
                ret = PairInfo(
                    base_precision=base_symbol_config.precision, quote_precision=quote_symbol_config.precision
                )
        # 如果设置了默认交易对信息，则作为最后选项使用。
        if ret is None:
            ret = self._default_pair_info

        if ret is None:
            raise errors.Error(f"找不到 {pair} 的配置")
        return ret

    def set_symbol_info(self, symbol: str, symbol_info: SymbolInfo):
        """设置货币符号信息。

        :param symbol: 货币符号
        :param symbol_info: 货币符号信息
        """
        self._symbol_info[symbol] = symbol_info

    def get_symbol_info(self, symbol: str) -> SymbolInfo:
        """获取货币符号信息。

        :param symbol: 货币符号
        :return: 货币符号信息
        :raises errors.Error: 如果找不到货币符号配置
        """
        ret = self._symbol_info.get(symbol, self._default_symbol_info)
        if ret is None:
            raise errors.Error(f"找不到 {symbol} 的配置")
        return ret
