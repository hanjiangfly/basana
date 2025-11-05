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

import dataclasses


@dataclasses.dataclass(frozen=True)
class Pair:
    """
    【中文说明】交易对类
    
    【功能描述】
    表示一个交易对，包含基础货币和计价货币的符号。
    交易对是金融市场中的基本概念，用于标识两种资产之间的交易关系。
    
    【参数说明】
    - base_symbol: str - 基础货币符号，可以是股票、加密货币、法定货币等
    - quote_symbol: str - 计价货币符号，用于表示基础货币的价格
    
    【使用场景】
    - 交易所API调用时指定交易对
    - 价格数据查询和交易执行
    - 资产组合管理和风险控制
    
    【注意事项】
    - 这是一个不可变的数据类（frozen=True），创建后不能修改
    - 基础货币在前，计价货币在后，符合行业标准
    - 字符串表示格式为"基础货币/计价货币"

    A trading pair.

    :param base_symbol: The base symbol. It could be a stock, a crypto currency, a currency, etc.
    :param quote_symbol: The quote symbol. It could be a stock, a crypto currency, a currency, etc.
    """

    #: 基础货币符号
    base_symbol: str

    #: 计价货币符号
    quote_symbol: str

    def __str__(self):
        """
        【中文说明】返回交易对的字符串表示
        
        【功能描述】
        将交易对对象转换为标准格式的字符串表示。
        
        【返回值】
        - str: 格式为"基础货币/计价货币"的字符串
        
        【使用场景】
        - 日志记录和调试输出
        - 用户界面显示
        - API请求参数格式化
        
        【注意事项】
        - 使用斜杠分隔基础货币和计价货币
        - 符合行业标准的交易对表示格式
        """
        return "{}/{}".format(self.base_symbol, self.quote_symbol)


@dataclasses.dataclass(frozen=True)
class PairInfo:
    """
    【中文说明】交易对信息类
    
    【功能描述】
    包含交易对的精度信息，用于控制价格和数量的显示和计算精度。
    
    【参数说明】
    - base_precision: int - 基础货币的精度（小数位数）
    - quote_precision: int - 计价货币的精度（小数位数）
    
    【使用场景】
    - 价格和数量的格式化显示
    - 订单数量和价格的验证
    - 交易对信息的配置管理
    
    【注意事项】
    - 精度值表示小数点后的位数
    - 这是一个不可变的数据类（frozen=True）
    - 精度信息通常从交易所API获取

    Information about a trading pair.

    :param base_precision: The precision for the base symbol.
    :param quote_precision: The precision for the quote symbol.
    """

    #: 基础货币精度（小数位数）
    base_precision: int

    #: 计价货币精度（小数位数）
    quote_precision: int
