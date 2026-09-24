"""
基金（场内 ETF/LOF）数据获取模块

数据源：**stockdb 本地行情为主，akshare 为兜底**（2026-09-21 切换）。

切换原因：原实现用 akshare 场外开放式基金净值接口（fund_open_fund_info_em），
其"单位净值"口径在分红型 ETF 上会跳变，导致收益率计算错误；本页全部标的都是
场内 ETF/LOF（`SELECTED_FUND_LIST` 67 只 / `_ALL_FUND_LIST_` 184 只，stockdb 实测
184/184 命中、510300 自 2012 年起 3480 行），故改用 stockdb 场内**前复权价格**
（qfq ≈ 累计净值口径，与 akshare 累计净值 12M 收益平均差异 ~3pp，为 ETF 折溢价所致）。

**语义列名（方案 B，统一 schema）**：`日期 / 收盘价 / 涨跌幅% / 来源`
akshare 兜底返回的净值数据会转换到同一 schema（收盘价=单位净值，已在日期列统一）。
"""

import calendar
import sys
import time as time_module  # 重命名time模块避免冲突
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import akshare as ak
import pandas as pd

from config import setup_logger

logger = setup_logger(__name__)
from ..core.cache_with_database import get_fund_cached_data, set_fund_cache_data
from .stockdb_data_fetcher import get_daily, get_raw  # stockdb 日K（本机，无额度限制）

# stockdb 取数的 schema：A股口径写入时统一加"净值日期/单位净值"兼容列已废弃，
# 改为语义列；来源标记便于排查（stockdb=本地 / akshare=在线）
_CL_DATE, _CL_CLOSE, _CL_PCT, _CL_SRC = "日期", "收盘价", "涨跌幅%", "来源"

_ALL_FUND_LIST_ = [
    {"基金代码": 510310, "基金简称": "沪深300ETF"},
    {"基金代码": 512400, "基金简称": "有色金属ETF"},
    {"基金代码": 512690, "基金简称": "酒ETF"},
    {"基金代码": 588200, "基金简称": "科创芯片ETF"},
    {"基金代码": 517520, "基金简称": "黄金股ETF"},
    {"基金代码": 512880, "基金简称": "证券ETF"},
    {"基金代码": 159870, "基金简称": "化工ETF"},
    {"基金代码": 512480, "基金简称": "半导体ETF"},
    {"基金代码": 159206, "基金简称": "卫星ETF"},
    {"基金代码": 512000, "基金简称": "券商ETF"},
    {"基金代码": 159928, "基金简称": "消费ETF"},
    {"基金代码": 512980, "基金简称": "传媒ETF"},
    {"基金代码": 562500, "基金简称": "机器人ETF"},
    {"基金代码": 159326, "基金简称": "电网设备ETF"},
    {"基金代码": 159852, "基金简称": "软件ETF"},
    {"基金代码": 159995, "基金简称": "芯片ETF"},
    {"基金代码": 512070, "基金简称": "证券保险ETF易方达"},
    {"基金代码": 588170, "基金简称": "科创半导体ETF"},
    {"基金代码": 515220, "基金简称": "煤炭ETF"},
    {"基金代码": 512200, "基金简称": "房地产ETF"},
    {"基金代码": 512800, "基金简称": "银行ETF"},
    {"基金代码": 512170, "基金简称": "医疗ETF"},
    {"基金代码": 515880, "基金简称": "通信ETF"},
    {"基金代码": 159869, "基金简称": "游戏ETF"},
    {"基金代码": 515980, "基金简称": "人工智能ETF"},
    {"基金代码": 159755, "基金简称": "电池ETF"},
    {"基金代码": 159851, "基金简称": "金融科技ETF"},
    {"基金代码": 515790, "基金简称": "光伏ETF"},
    {"基金代码": 159992, "基金简称": "创新药ETF"},
    {"基金代码": 512660, "基金简称": "军工ETF"},
    {"基金代码": 159566, "基金简称": "储能电池ETF易方达"},
    {"基金代码": 561330, "基金简称": "矿业ETF"},
    {"基金代码": 159731, "基金简称": "石化ETF"},
    {"基金代码": 561360, "基金简称": "石油ETF"},
    {"基金代码": 159766, "基金简称": "旅游ETF"},
    {"基金代码": 159745, "基金简称": "建材ETF"},
    {"基金代码": 516780, "基金简称": "稀土ETF"},
    {"基金代码": 515070, "基金简称": "人工智能AIETF"},
    {"基金代码": 515080, "基金简称": "中证红利ETF"},
    {"基金代码": 159883, "基金简称": "医疗器械ETF"},
    {"基金代码": 515210, "基金简称": "钢铁ETF"},
    {"基金代码": 512930, "基金简称": "AI人工智能ETF"},
    {"基金代码": 515650, "基金简称": "消费50ETF"},
    {"基金代码": 159559, "基金简称": "机器人50ETF"},
    {"基金代码": 159930, "基金简称": "能源ETF"},
    {"基金代码": 159998, "基金简称": "计算机ETF"},
    {"基金代码": 159993, "基金简称": "证券ETF鹏华"},
    {"基金代码": 159611, "基金简称": "电力ETF"},
    {"基金代码": 512670, "基金简称": "国防ETF"},
    {"基金代码": 159825, "基金简称": "农业ETF"},
    {"基金代码": 515030, "基金简称": "新能源车ETF"},
    {"基金代码": 159707, "基金简称": "地产ETF"},
    {"基金代码": 159583, "基金简称": "通信设备ETF"},
    {"基金代码": 159267, "基金简称": "航天ETF"},
    {"基金代码": 159865, "基金简称": "养殖ETF"},
    {"基金代码": 561380, "基金简称": "电网ETF"},
    {"基金代码": 159859, "基金简称": "生物医药ETF"},
    {"基金代码": 159758, "基金简称": "红利质量ETF"},
    {"基金代码": 159698, "基金简称": "粮食ETF"},
    {"基金代码": 510410, "基金简称": "资源ETF"},
    {"基金代码": 159994, "基金简称": "5GETF"},
    {"基金代码": 516160, "基金简称": "新能源ETF"},
    {"基金代码": 159732, "基金简称": "消费电子ETF"},
    {"基金代码": 159929, "基金简称": "医药ETF"},
    {"基金代码": 510170, "基金简称": "大宗商品ETF"},
    {"基金代码": 560280, "基金简称": "工程机械ETF"},
    {"基金代码": 159890, "基金简称": "云计算ETF"},
    {"基金代码": 560080, "基金简称": "中药ETF"},
    {"基金代码": 159899, "基金简称": "软件龙头ETF"},
    {"基金代码": 516520, "基金简称": "智能驾驶ETF"},
    {"基金代码": 561160, "基金简称": "锂电池ETF"},
    {"基金代码": 516820, "基金简称": "医疗创新ETF"},
    {"基金代码": 159843, "基金简称": "食品饮料ETF"},
    {"基金代码": 515700, "基金简称": "新能车ETF"},
    {"基金代码": 159862, "基金简称": "食品ETF"},
    {"基金代码": 512040, "基金简称": "价值100ETF"},
    {"基金代码": 560680, "基金简称": "消费ETF广发"},
    {"基金代码": 159996, "基金简称": "家电ETF"},
    {"基金代码": 515250, "基金简称": "智能汽车ETF"},
    {"基金代码": 510230, "基金简称": "金融ETF"},
    {"基金代码": 512600, "基金简称": "消费ETF嘉实"},
    {"基金代码": 159855, "基金简称": "影视ETF"},
    {"基金代码": 159790, "基金简称": "碳中和ETF"},
    {"基金代码": 517800, "基金简称": "人工智能50ETF"},
    {"基金代码": 588010, "基金简称": "科创新材料ETF"},
    {"基金代码": 159997, "基金简称": "电子ETF"},
    {"基金代码": 159602, "基金简称": "中国A50ETF南方"},
    {"基金代码": 562570, "基金简称": "信创ETF"},
    {"基金代码": 560770, "基金简称": "机器人指数ETF"},
    {"基金代码": 562550, "基金简称": "绿电ETF"},
    {"基金代码": 588960, "基金简称": "科创板新能源ETF"},
    {"基金代码": 159939, "基金简称": "信息技术ETF"},
    {"基金代码": 159546, "基金简称": "集成电路ETF"},
    {"基金代码": 517900, "基金简称": "银行AH优选ETF"},
    {"基金代码": 159551, "基金简称": "机器人产业ETF"},
    {"基金代码": 516670, "基金简称": "畜牧养殖ETF"},
    {"基金代码": 159867, "基金简称": "畜牧ETF"},
    {"基金代码": 159643, "基金简称": "疫苗ETF"},
    {"基金代码": 159775, "基金简称": "电池ETF基金"},
    {"基金代码": 562310, "基金简称": "沪深300成长ETF"},
    {"基金代码": 159525, "基金简称": "红利低波ETF"},
    {"基金代码": 515260, "基金简称": "电子ETF"},
    {"基金代码": 516950, "基金简称": "基建ETF"},
    {"基金代码": 563210, "基金简称": "专精特新ETF"},
    {"基金代码": 515750, "基金简称": "科技50ETF"},
    {"基金代码": 159873, "基金简称": "医疗设备ETF"},
    {"基金代码": 159207, "基金简称": "高股息ETF"},
    {"基金代码": 159944, "基金简称": "材料ETF"},
    {"基金代码": 563320, "基金简称": "通用航空ETF"},
    {"基金代码": 159835, "基金简称": "创新药50ETF"},
    {"基金代码": 515950, "基金简称": "医药龙头ETF"},
    {"基金代码": 159672, "基金简称": "主要消费ETF"},
    {"基金代码": 159108, "基金简称": "工业软件ETF"},
    {"基金代码": 515580, "基金简称": "科技100ETF"},
    {"基金代码": 159767, "基金简称": "电池龙头ETF"},
    {"基金代码": 159666, "基金简称": "交通运输ETF"},
    {"基金代码": 159616, "基金简称": "农牧ETF"},
    {"基金代码": 512580, "基金简称": "环保ETF"},
    {"基金代码": 516130, "基金简称": "消费龙头ETF"},
    {"基金代码": 516800, "基金简称": "智能制造ETF"},
    {"基金代码": 159392, "基金简称": "航空ETF"},
    {"基金代码": 560800, "基金简称": "数字经济ETF"},
    {"基金代码": 515320, "基金简称": "电子50ETF"},
    {"基金代码": 588110, "基金简称": "科创成长ETF"},
    {"基金代码": 159512, "基金简称": "汽车ETF"},
    {"基金代码": 159275, "基金简称": "农牧渔ETF"},
    {"基金代码": 516270, "基金简称": "新能源50ETF"},
    {"基金代码": 561920, "基金简称": "疫苗龙头ETF"},
    {"基金代码": 159779, "基金简称": "消费电子50ETF"},
    {"基金代码": 562050, "基金简称": "药ETF"},
    {"基金代码": 561170, "基金简称": "绿色电力ETF"},
    {"基金代码": 510200, "基金简称": "上证券商ETF"},
    {"基金代码": 588260, "基金简称": "科创信息ETF"},
    {"基金代码": 159936, "基金简称": "可选消费ETF"},
    {"基金代码": 516500, "基金简称": "生物科技ETF"},
    {"基金代码": 562320, "基金简称": "沪深300价值ETF"},
    {"基金代码": 159966, "基金简称": "创业板价值ETF"},
    {"基金代码": 159827, "基金简称": "农业50ETF"},
    {"基金代码": 516910, "基金简称": "物流ETF"},
    {"基金代码": 562350, "基金简称": "电力指数ETF"},
    {"基金代码": 562920, "基金简称": "信息安全ETF易方达"},
    {"基金代码": 159889, "基金简称": "智能汽车ETF"},
    {"基金代码": 560690, "基金简称": "电信ETF鹏华"},
    {"基金代码": 159940, "基金简称": "金融地产ETF"},
    {"基金代码": 517550, "基金简称": "消费ETF沪港深"},
    {"基金代码": 159886, "基金简称": "机械ETF"},
    {"基金代码": 512150, "基金简称": "A50ETF"},
    {"基金代码": 562340, "基金简称": "中证500成长ETF"},
    {"基金代码": 516330, "基金简称": "物联网ETF"},
    {"基金代码": 159861, "基金简称": "碳中和50ETF"},
    {"基金代码": 516560, "基金简称": "养老ETF"},
    {"基金代码": 516360, "基金简称": "新材料ETF"},
    {"基金代码": 562390, "基金简称": "中药50ETF"},
    {"基金代码": 512380, "基金简称": "MSCI中国ETF"},
    {"基金代码": 159838, "基金简称": "医药50ETF"},
    {"基金代码": 159909, "基金简称": "TMT50ETF"},
    {"基金代码": 159777, "基金简称": "创科技ETF"},
    {"基金代码": 516830, "基金简称": "300ESGETF"},
    {"基金代码": 516580, "基金简称": "新能源主题ETF"},
    {"基金代码": 562330, "基金简称": "中证500价值ETF"},
    {"基金代码": 561310, "基金简称": "消电ETF"},
    {"基金代码": 561320, "基金简称": "交运ETF"},
    {"基金代码": 516380, "基金简称": "智能电动车ETF"},
    {"基金代码": 562010, "基金简称": "绿色能源ETF"},
    {"基金代码": 515920, "基金简称": "智能消费ETF"},
    {"基金代码": 517990, "基金简称": "医药ETF沪港深"},
    {"基金代码": 159849, "基金简称": "生物科技指数ETF"},
    {"基金代码": 159959, "基金简称": "央企ETF"},
    {"基金代码": 159306, "基金简称": "汽车零件ETF"},
    {"基金代码": 515200, "基金简称": "创新100ETF"},
    {"基金代码": 516530, "基金简称": "物流快递ETF"},
    {"基金代码": 517880, "基金简称": "品牌消费ETF"},
    {"基金代码": 512520, "基金简称": "MSCIETF"},
    {"基金代码": 159913, "基金简称": "深价值ETF"},
    {"基金代码": 515590, "基金简称": "500等权ETF"},
    {"基金代码": 517360, "基金简称": "科技ETF沪港深"},
    {"基金代码": 159203, "基金简称": "大盘成长ETF"},
    {"基金代码": 512970, "基金简称": "大湾区ETF"},
    {"基金代码": 515090, "基金简称": "可持续发展ETF"},
    {"基金代码": 159973, "基金简称": "民企ETF"},
    {"基金代码": 159717, "基金简称": "ESGETF"},
    {"基金代码": 512360, "基金简称": "MSCI中国A股ETF基金"},
    {"基金代码": 512870, "基金简称": "杭州湾区ETF"},
]

# 大盘指数 ETF —— 与指数页「大盘指数」组一一对应（沪深300/上证50/中证500/中证1000/上证180/创业板50）。
# 这些 ETF 在基金排名中**恒置顶**（保证不被 top_n 截断），便于与指数页对照。
# 注：口径不同——指数页是指数点位，这里是 ETF 二级市场**前复权价格**（叠加折溢价/跟踪误差/管理费），
# 故两者收益接近但**不相等**，属正常现象。
INDEX_FUND_ETFS = {
    "510300": "沪深300ETF",
    "510050": "上证50ETF",
    "510500": "中证500ETF",
    "512100": "中证1000ETF",
    "510180": "上证180ETF",
    "159949": "创业板50ETF",
}

# 基金分组标签（与指数页的 `index_group` 同构；指数页分组依据是"有无乐咕估值源"，
# 基金页无估值字段，故按**标的是否大盘指数 ETF** 分组）
GROUP_INDEX_FUND = "大盘指数ETF"
GROUP_THEME_FUND = "行业主题ETF"


def fund_group(symbol) -> str:
    """基金分组标签：`大盘指数ETF` / `行业主题ETF`。"""
    return (GROUP_INDEX_FUND if str(symbol).zfill(6) in INDEX_FUND_ETFS
            else GROUP_THEME_FUND)

# 新的精选基金列表，初始为空，将在update_selected_fund_list函数中被填充
SELECTED_FUND_LIST = [
    # —— 大盘指数 ETF（置顶组，见 INDEX_FUND_ETFS）——
    {"基金代码": 510300, "基金简称": "沪深300ETF"},
    {"基金代码": 510050, "基金简称": "上证50ETF"},
    {"基金代码": 510500, "基金简称": "中证500ETF"},
    {"基金代码": 512100, "基金简称": "中证1000ETF"},
    {"基金代码": 510180, "基金简称": "上证180ETF"},
    {"基金代码": 159949, "基金简称": "创业板50ETF"},
    # —— 行业/主题 ETF ——
    {"基金代码": 512400, "基金简称": "有色金属ETF"},
    {"基金代码": 588200, "基金简称": "科创芯片ETF"},
    {"基金代码": 517520, "基金简称": "黄金股ETF"},
    {"基金代码": 159870, "基金简称": "化工ETF"},
    {"基金代码": 512480, "基金简称": "半导体ETF"},
    {"基金代码": 159206, "基金简称": "卫星ETF"},
    {"基金代码": 512980, "基金简称": "传媒ETF"},
    {"基金代码": 159326, "基金简称": "电网设备ETF"},
    {"基金代码": 159852, "基金简称": "软件ETF"},
    {"基金代码": 159995, "基金简称": "芯片ETF"},
    {"基金代码": 515220, "基金简称": "煤炭ETF"},
    {"基金代码": 512200, "基金简称": "房地产ETF"},
    {"基金代码": 159869, "基金简称": "游戏ETF"},
    {"基金代码": 515980, "基金简称": "人工智能ETF"},
    {"基金代码": 515790, "基金简称": "光伏ETF"},
    {"基金代码": 512660, "基金简称": "军工ETF"},
    {"基金代码": 561330, "基金简称": "矿业ETF"},
    {"基金代码": 159731, "基金简称": "石化ETF"},
    {"基金代码": 561360, "基金简称": "石油ETF"},
    {"基金代码": 159745, "基金简称": "建材ETF"},
    {"基金代码": 516780, "基金简称": "稀土ETF"},
    {"基金代码": 515080, "基金简称": "中证红利ETF"},
    {"基金代码": 515210, "基金简称": "钢铁ETF"},
    {"基金代码": 159930, "基金简称": "能源ETF"},
    {"基金代码": 159998, "基金简称": "计算机ETF"},
    {"基金代码": 512670, "基金简称": "国防ETF"},
    {"基金代码": 159707, "基金简称": "地产ETF"},
    {"基金代码": 159267, "基金简称": "航天ETF"},
    {"基金代码": 561380, "基金简称": "电网ETF"},
    {"基金代码": 159698, "基金简称": "粮食ETF"},
    {"基金代码": 510410, "基金简称": "资源ETF"},
    {"基金代码": 516160, "基金简称": "新能源ETF"},
    {"基金代码": 510170, "基金简称": "大宗商品ETF"},
    {"基金代码": 560280, "基金简称": "工程机械ETF"},
    {"基金代码": 159890, "基金简称": "云计算ETF"},
    {"基金代码": 159899, "基金简称": "软件龙头ETF"},
    {"基金代码": 512040, "基金简称": "价值100ETF"},
    {"基金代码": 159855, "基金简称": "影视ETF"},
    {"基金代码": 588010, "基金简称": "科创新材料ETF"},
    {"基金代码": 159997, "基金简称": "电子ETF"},
    {"基金代码": 562570, "基金简称": "信创ETF"},
    {"基金代码": 159939, "基金简称": "信息技术ETF"},
    {"基金代码": 159546, "基金简称": "集成电路ETF"},
    {"基金代码": 159551, "基金简称": "机器人产业ETF"},
    {"基金代码": 516950, "基金简称": "基建ETF"},
    {"基金代码": 563210, "基金简称": "专精特新ETF"},
    {"基金代码": 159207, "基金简称": "高股息ETF"},
    {"基金代码": 159944, "基金简称": "材料ETF"},
    {"基金代码": 563320, "基金简称": "通用航空ETF"},
    {"基金代码": 159108, "基金简称": "工业软件ETF"},
    {"基金代码": 515580, "基金简称": "科技100ETF"},
    {"基金代码": 159616, "基金简称": "农牧ETF"},
    {"基金代码": 516800, "基金简称": "智能制造ETF"},
    {"基金代码": 159392, "基金简称": "航空ETF"},
    {"基金代码": 560800, "基金简称": "数字经济ETF"},
    {"基金代码": 588110, "基金简称": "科创成长ETF"},
    {"基金代码": 588260, "基金简称": "科创信息ETF"},
    {"基金代码": 516330, "基金简称": "物联网ETF"},
    {"基金代码": 159861, "基金简称": "碳中和50ETF"},
    {"基金代码": 516360, "基金简称": "新材料ETF"},
    {"基金代码": 159777, "基金简称": "创科技ETF"},
    {"基金代码": 516580, "基金简称": "新能源主题ETF"},
    {"基金代码": 159959, "基金简称": "央企ETF"},
    {"基金代码": 515200, "基金简称": "创新100ETF"},
    {"基金代码": 159913, "基金简称": "深价值ETF"},
    {"基金代码": 512870, "基金简称": "杭州湾区ETF"},
]


def _ensure_consistent_format(data: Union[pd.DataFrame, List[Dict]]) -> List[Dict]:
    """
    确保数据格式一致，将DataFrame转换为字典列表
    """
    if isinstance(data, pd.DataFrame):
        return data.to_dict("records") if not data.empty else []
    elif isinstance(data, list):
        return data
    else:
        return []


def _convert_cached_data_to_dataframe(
    cached_data: Union[pd.DataFrame, List[Dict]],
) -> pd.DataFrame:
    """
    将缓存的数据转换为DataFrame格式
    """
    if isinstance(cached_data, pd.DataFrame):
        return cached_data
    elif isinstance(cached_data, list):
        return pd.DataFrame(cached_data) if cached_data else pd.DataFrame()
    else:
        return pd.DataFrame()




# ---------------------------------------------------------------- 数据层
def _records_from_stockdb(code: str) -> Optional[List[Dict]]:
    """stockdb 场内行情 → 统一 schema（日期/收盘价/涨跌幅%）。失败返回 None 以便兜底。"""
    try:
        df = get_daily(code, fq="qfq", fields="date,close,pct_chg")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"stockdb 取数失败 {code}: {type(e).__name__}: {e}")
        return None
    if df is None or df.empty or "close" not in df.columns:
        return None
    df = df.sort_values("date")
    return [
        {  # 日期 int YYYYMMDD → 'YYYY-MM-DD'；qfq 前复权 ≈ 累计净值口径
            _CL_DATE: str(int(d["date"]))[:10] if str(d["date"]).isdigit()
                      else str(d["date"])[:10],
            _CL_CLOSE: round(float(d["close"]), 4),
            _CL_PCT: (None if pd.isna(d["pct_chg"]) else round(float(d["pct_chg"]), 3)),
            _CL_SRC: "stockdb",
        }
        for _, d in df.iterrows()
    ]


def _records_from_akshare(code: str) -> Optional[List[Dict]]:
    """akshare 兜底（在线，"单位净值走势"；分红型标的口径与 qfq 有差异）。"""
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty or "单位净值" not in df.columns:
            return None
        df = df.copy()
        df["净值日期"] = pd.to_datetime(df["净值日期"]).dt.strftime("%Y-%m-%d")
        df = df.sort_values("净值日期")
        pct = df["日增长率"] if "日增长率" in df.columns else None
        return [
            {
                _CL_DATE: str(r["净值日期"])[:10],
                _CL_CLOSE: round(float(r["单位净值"]), 4),
                _CL_PCT: (None if pct is None or pd.isna(r["日增长率"])
                          else round(float(r["日增长率"]), 3)),
                _CL_SRC: "akshare",
            }
            for _, r in df.iterrows()
        ]
    except Exception as e:  # noqa: BLE001
        logger.warning(f"akshare 取数失败 {code}: {type(e).__name__}: {e}")
        return None


def get_fund_daily_data(fund_code: str, indicator: str = None, apply_delay: bool = False):
    """获取单只基金完整历史（stockdb 优先，akshare 兜底），返回 DataFrame。

    兼容旧签名（indicator/apply_delay 参数保留但不影响取数，stockdb 无需延时）。
    输出列为统一 schema（日期/收盘价/涨跌幅%/来源），升序。
    """
    code = str(fund_code).zfill(6)
    cache_key = f"fund_px_hist_{code}"           # 新前缀：语义切换不读旧净值缓存
    cached = get_fund_cached_data(cache_key)
    if cached:
        return pd.DataFrame(cached)

    records = _records_from_stockdb(code)
    if not records:
        records = _records_from_akshare(code)
    if not records:
        logger.warning(f"基金 {code} 无历史数据（stockdb/akshare 均未命中）")
        return pd.DataFrame()

    df = pd.DataFrame(records).sort_values(_CL_DATE)
    set_fund_cache_data(cache_key, df.to_dict("records"), cache_duration=86400)
    return df


def get_fund_history(fund_code: str, period: str = "12M", indicator: str = None,
                     apply_delay: bool = False):
    """获取单只基金在 period 窗口内的历史（缓存整段，按期切片）。"""
    cache_key = f"fund_px_hist_{str(fund_code).zfill(6)}_{period}"
    cached = get_fund_cached_data(cache_key)
    if cached:
        return pd.DataFrame(cached)

    full = get_fund_daily_data(fund_code)
    if full.empty:
        return pd.DataFrame()

    hist = filter_history_by_period(full, period).reset_index(drop=True)
    set_fund_cache_data(cache_key, hist.to_dict("records"), cache_duration=86400)
    return hist


def get_fund_histories_smart_batch(fund_codes: List[str], period: str = "12M",
                                   indicator: str = None, delay: float = 0.0):
    """批量获取多只基金的历史（stockdb **一次请求拉多只**，仅对未命中缓存的个股兜底）。

    兼容旧签名（indicator/delay 保留；stockdb 本地取数无网络翻页，不再需要延时）。
    流程：逐码查缓存 → 缺失码一次 get_raw 拉全 → 逐码写缓存（整段+切片）→
    stockdb 未命中的码走 akshare 兜底（get_fund_history 内部）。
    """
    results: Dict[str, pd.DataFrame] = {}
    codes = [str(c).zfill(6) for c in fund_codes]
    missing: List[str] = []
    for code in codes:
        cache_key = f"fund_px_hist_{code}_{period}"
        cached = get_fund_cached_data(cache_key)
        if cached is not None:
            results[code] = _convert_cached_data_to_dataframe(cached)
        else:
            missing.append(code)

    if missing:
        try:
            df = get_raw(missing, fq="qfq", fields="date,code,close,pct_chg")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"stockdb 批量取数失败: {type(e).__name__}: {e}")
            df = None
        if isinstance(df, pd.DataFrame) and not df.empty:
            for code, g in df.groupby("code"):
                g = g.sort_values("date")
                full = pd.DataFrame([
                    {"日期": str(int(r["date"]))[:10],
                     "收盘价": round(float(r["close"]), 4),
                     "涨跌幅%": (None if pd.isna(r["pct_chg"])
                                 else round(float(r["pct_chg"]), 3)),
                     "来源": "stockdb"}
                    for _, r in g.iterrows()
                ])
                set_fund_cache_data(f"fund_px_hist_{code}",
                                    full.to_dict("records"), cache_duration=86400)
                hist = filter_history_by_period(full, period).reset_index(drop=True)
                set_fund_cache_data(f"fund_px_hist_{code}_{period}",
                                    hist.to_dict("records"), cache_duration=86400)
                results[code] = hist

    # stockdb 未命中的（代码缺失/新上市）走 akshare 逐只兜底
    still_missing = [c for c in codes if c not in results
                     or results[c] is None or (hasattr(results[c], "empty")
                                               and getattr(results[c], "empty", True))]
    for code in missing:
        if code in results and not (getattr(results[code], "empty", True)):
            continue
        results[code] = get_fund_history(code, period=period)
    got = sum(1 for v in results.values() if not getattr(v, "empty", True))
    logger.info(f"批量获取基金数据完成（stockdb）：{len(codes)} 只，"
                f"批量请求 {len(missing)} 次兜底 {len(missing)}, 有效 {got} 只")
    return results


def _period_return(history) -> Optional[Dict]:
    """由统一 schema（日期/收盘价）的历史记录计算期间收益率。

    返回 {rate(%), current(最新价), amount(绝对涨跌), days(条数)}；数据不足返回 None。
    收益率 = 尾价/首价 − 1（qfq 前复权 ≈ 累计净值口径，分红已含）。
    """
    recs = _ensure_consistent_format(history)
    if len(recs) < 2:
        return None
    vals = [r.get(_CL_CLOSE) for r in recs
            if isinstance(r, dict) and r.get(_CL_CLOSE) is not None]
    try:
        vals = [float(v) for v in vals if v not in (None, "",)]
    except (TypeError, ValueError):
        return None
    if len(vals) < 2 or vals[0] == 0:
        return None
    return {
        "rate": round((vals[-1] / vals[0] - 1.0) * 100, 2),
        "current": round(vals[-1], 4),
        "amount": round(vals[-1] - vals[0], 4),
        "days": len(recs),
    }


def calculate_date_range(period: str):
    """
    根据时间段计算开始和结束日期
    :param period: 时间周期，如 "1M", "3M", "6M", "12M", "YTD", "1Y" 等
    :return: (start_date, end_date) 元组
    """
    end_date = datetime.now()

    if period == "YTD":
        # Year to Date: 当年年初至今
        start_date = datetime(end_date.year, 1, 1)
    elif period.endswith("D"):
        # 处理天数周期
        days = int(period[:-1])
        start_date = end_date - timedelta(days=days)
    elif period.endswith("M"):
        # 更精确地处理月份周期
        months = int(period[:-1])
        # 计算目标月份和年份
        target_month = end_date.month - months
        target_year = end_date.year
        while target_month <= 0:
            target_month += 12
            target_year -= 1
        # 获取目标月份的天数，确保日期有效
        target_day = min(
            end_date.day, calendar.monthrange(target_year, target_month)[1]
        )
        start_date = datetime(target_year, target_month, target_day)
    elif period.endswith("Y"):
        # 更精确地处理年份周期
        years = int(period[:-1])
        target_year = end_date.year - years
        # 确保日期有效（考虑闰年等情况）
        target_day = min(
            end_date.day, calendar.monthrange(target_year, end_date.month)[1]
        )
        start_date = datetime(target_year, end_date.month, target_day)
    else:
        # 默认一年
        start_date = end_date - timedelta(days=365)

    return start_date, end_date


def filter_history_by_period(history_df: pd.DataFrame, period: str = "12M"):
    """按时间段筛选历史数据（统一 schema：日期/收盘价）。"""
    if history_df is None or history_df.empty or "日期" not in history_df.columns:
        return history_df

    df = history_df.copy()
    df["日期"] = pd.to_datetime(df["日期"])
    start_date, end_date = calculate_date_range(period)
    df = df[(df["日期"] >= start_date) & (df["日期"] <= end_date)].sort_values("日期")
    df["日期"] = df["日期"].dt.strftime("%Y-%m-%d")
    return df


def filter_fund_history_by_period(history_df: pd.DataFrame, period: str = "12M"):
    """兼容旧名的切片函数（预热器 start_app 等使用）。"""
    return filter_history_by_period(history_df, period)


def _selected_list2_dataframe():
    """
    将精选基金列表转为 DataFrame：代码/名称 + stockdb 实时快照（收盘价/涨跌幅%）。

    前端 `/api/fund/list` 只消费 基金代码/基金简称（chart 选择器），
    其余字段为真实市值信息（原 akshare 版本这些字段全是硬编码假值）。
    """
    codes = [str(f["基金代码"]).zfill(6) for f in SELECTED_FUND_LIST]
    quotes: Dict[str, dict] = {}
    try:
        df = get_raw(codes, fq="qfq", fields="date,code,close,pct_chg")
        if isinstance(df, pd.DataFrame) and not df.empty:
            for code, g in df.groupby("code"):
                g = g.sort_values("date")
                last = g.iloc[-1]
                quotes[code] = {
                    "收盘价": round(float(last["close"]), 4),
                    "涨跌幅%": (None if pd.isna(last["pct_chg"])
                                else round(float(last["pct_chg"]), 3)),
                }
    except Exception as e:  # noqa: BLE001
        logger.warning(f"精选列表快照获取失败（stockdb）: {e}")

    fund_list = []
    for fund in SELECTED_FUND_LIST:
        code = str(fund["基金代码"]).zfill(6)
        q = quotes.get(code, {})
        fund_list.append({
            "基金代码": code,
            "基金简称": fund["基金简称"],
            "收盘价": q.get("收盘价"),
            "涨跌幅%": q.get("涨跌幅%"),
            "fund_group": fund_group(code),
        })
    return pd.DataFrame(fund_list)


def get_selected_fund_list():
    """
    获取预定义的基金列表（返回精选的前100只）
    返回包含基金代码、基金简称等信息的字典列表
    """
    try:
        # 使用辅助函数获取与原基金列表格式兼容的数据
        fund_list_df = _selected_list2_dataframe()
        # 将DataFrame转换为字典列表格式
        fund_list = fund_list_df.to_dict("records")
        logger.info(f"返回精选基金列表，共 {len(fund_list)} 只基金")
        return fund_list
    except Exception as e:
        logger.error(f"get_selected_fund_list: {e}")
        return []


def _pin_index_funds(ranked: List[Dict]) -> List[Dict]:
    """给每项打 `fund_group` 标签，并把大盘指数 ETF 置顶（其余保持原顺序）。

    置顶 = 保证不被 `top_n` 截断；前端按 `fund_group` **分组显示**（与指数页同构）。
    """
    for item in ranked:
        item["fund_group"] = fund_group(item.get("symbol", ""))
    idx = [x for x in ranked if x["fund_group"] == GROUP_INDEX_FUND]
    rest = [x for x in ranked if x["fund_group"] != GROUP_INDEX_FUND]
    return idx + rest


def get_fund_dynamic_list(top_n=28, period="30D", cache_duration=24 * 3600):
    """
    获取动态选择的基金列表（基于收益率排名）
    :param top_n: 返回前N只基金
    :param period: 时间周期，默认30天
    :param cache_duration: 缓存持续时间，默认30分钟
    """
    cache_key = f"dynamic_selected_funds_px_{top_n}_{period}"

    # 尝试从缓存获取数据
    cached_data = get_fund_cached_data(cache_key)
    if cached_data is not None:
        logger.info(f"从缓存获取动态选择的基金列表（前{top_n}只）")
        return cached_data

    try:
        # 使用预定义的基金列表
        all_funds_df = _selected_list2_dataframe()
        funds_to_process = all_funds_df  # 使用所有预定义基金

        # 智能批量获取基金历史数据
        fund_codes = [
            str(fund.get("基金代码", "")) for _, fund in funds_to_process.iterrows()
        ]
        batch_histories = get_fund_histories_smart_batch(
            fund_codes, period=period, delay=0.4
        )  # 使用较小的延时

        ranked_funds = []
        for index, fund in funds_to_process.iterrows():
            fund_code = str(fund.get("基金代码", ""))
            fund_name = fund.get("基金简称", "")
            try:
                ret = _period_return(batch_histories.get(fund_code, pd.DataFrame()))
                if ret:
                    ranked_funds.append({
                        "symbol": fund_code, "name": fund_name,
                        "current_price": ret["current"],
                        "change_percent": ret["rate"],
                        "change_amount": ret["amount"], "days": ret["days"],
                    })
            except Exception as e:
                logger.debug(f"计算基金 {fund_code} 收益率时出错: {e}")
                continue

        # 按收益率排序
        ranked_funds.sort(key=lambda x: x["change_percent"], reverse=True)

        # 大盘指数 ETF 恒置顶（保证不被 top_n 截断）
        ranked_funds = _pin_index_funds(ranked_funds)

        # 返回前N只
        top_funds = ranked_funds[:top_n]

        set_fund_cache_data(
            cache_key, top_funds, cache_duration=cache_duration
        )  # 使用传入的缓存时间

        logger.info(f"成功获取动态选择的基金列表（前{len(top_funds)}只）")
        return top_funds
    except Exception as e:
        logger.error(f"获取动态选择的基金列表失败: {e}")
        # 返回空列表
        return []


def get_fund_ranking(period: str = "30D"):
    """
    获取按收益率排名的SELECTED的基金列表
    :param period: 时间周期，默认1个月
    """
    cache_key = f"top_funds_by_return_px_{period}"

    # 尝试从缓存获取数据
    cached_data = get_fund_cached_data(cache_key)
    if cached_data is not None:
        logger.info(f"从缓存获取 {period} 按收益率排名的基金列表）")
        return cached_data

    try:
        # 使用预定义的基金列表，而不是获取全部基金
        all_funds_df = _selected_list2_dataframe()
        funds_to_process = all_funds_df  # 使用所有预定义基金，而不是限制为前100只

        # 智能批量获取基金历史数据
        fund_codes = [
            str(fund.get("基金代码", "")) for _, fund in funds_to_process.iterrows()
        ]
        batch_histories = get_fund_histories_smart_batch(
            fund_codes, period=period, delay=0.4
        )  # 使用较小的延时

        ranked_funds = []
        for _, fund in funds_to_process.iterrows():
            fund_code = str(fund.get("基金代码", ""))
            fund_name = fund.get("基金简称", "")
            try:
                ret = _period_return(batch_histories.get(fund_code, pd.DataFrame()))
                if ret:
                    ranked_funds.append({
                        "symbol": fund_code, "name": fund_name,
                        "current_price": ret["current"],
                        "change_percent": ret["rate"],
                        "change_amount": ret["amount"], "days": ret["days"],
                    })
            except Exception as e:
                logger.debug(f"计算基金 {fund_code} 收益率时出错: {e}")
                continue

        # 按收益率排序
        ranked_funds.sort(key=lambda x: x["change_percent"], reverse=True)
        for i, item in enumerate(ranked_funds):
            item["rank"] = i + 1
        # 大盘指数 ETF 恒置顶（保证不被 top_n 截断；前端仍按涨跌幅展示并用 ★ 区分）
        ranked_funds = _pin_index_funds(ranked_funds)
        set_fund_cache_data(cache_key, ranked_funds)
        logger.info(f"成功获取按收益率排名的基金列表（共{len(ranked_funds)}只）")
        return ranked_funds
    except Exception as e:
        logger.error(f"获取按收益率排名的基金列表失败: {e}")
        return []


def get_fund_chart_data(
    symbols: List[str], period: str = "12M", use_growth_rate: bool = True
):
    """
    准备基金图表数据，返回适合ECharts展示的格式
    :param symbols: 基金代码列表
    :param period: 时间周期
    :param use_growth_rate: 是否使用增长率对比
    :return: 适合ECharts展示的数据格式
    """
    cache_key = f"prepared_fund_chart_data_px_{','.join(sorted(symbols))}_{period}_{use_growth_rate}"

    # 尝试从缓存获取数据
    cached_data = get_fund_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, dict):
        logger.info(f"从缓存获取准备好的基金图表数据: {symbols}")
        return cached_data

    try:
        # 智能批量获取多个基金历史数据
        batch_histories = get_fund_histories_smart_batch(
            symbols, period=period, delay=0.4
        )  # 使用较小的延时

        # 将批量获取的数据转换为原有格式
        multi_history_data = {}
        for symbol in symbols:
            history = batch_histories.get(symbol, pd.DataFrame())
            # 统一处理history数据，确保是一致的格式
            history_records = _ensure_consistent_format(history)
            multi_history_data[symbol] = history_records

        if not multi_history_data:
            logger.error("获取基金历史数据失败")
            return None

        # 构建图表数据格式
        chart_data = {"dates": [], "series": []}

        # 收集所有日期并去重排序
        all_dates = set()
        for symbol, history in multi_history_data.items():
            for item in history:
                if isinstance(item, dict) and _CL_DATE in item:
                    all_dates.add(item[_CL_DATE])
        chart_data["dates"] = sorted(list(all_dates))

        # 为每个基金生成系列数据
        for symbol in symbols:
            if symbol in multi_history_data:
                history = multi_history_data[symbol]

                # 为了匹配日期轴，创建完整的数据序列（缺失日期填充为None）
                series_data = []

                # 创建日期到净值的映射
                date_to_value = {}
                for item in history:
                    if isinstance(item, dict):
                        date_key = item.get(_CL_DATE)
                        nav_value = item.get(_CL_CLOSE)
                        if date_key and nav_value is not None:
                            date_to_value[date_key] = (
                                float(nav_value) if nav_value != "" else None
                            )

                if (
                    use_growth_rate
                    and len([v for v in date_to_value.values() if v is not None]) > 0
                ):
                    # 使用增长率计算
                    # 首先获取按日期排序的净值数据
                    sorted_items = []
                    for date in chart_data["dates"]:
                        if date in date_to_value and date_to_value[date] is not None:
                            sorted_items.append(
                                {"date": date, "close": date_to_value[date]}
                            )

                    if len(sorted_items) > 0:
                        # 计算增长率
                        base_value = (
                            sorted_items[0]["close"]
                            if sorted_items[0]["close"] != 0
                            else 1
                        )
                        date_to_growth = {}
                        for item in sorted_items:
                            growth_rate = (
                                ((item["close"] - base_value) / base_value) * 100
                                if base_value != 0
                                else 0
                            )
                            date_to_growth[item["date"]] = round(growth_rate, 2)

                        # 为每个日期生成数据点 - 转换为ECharts需要的格式 [timestamp, value]
                        # Python中需要使用datetime处理时间戳
                        from datetime import datetime

                        for date in chart_data["dates"]:
                            if date in date_to_growth:
                                # 转换日期为时间戳
                                try:
                                    dt = datetime.strptime(date, "%Y-%m-%d")
                                    timestamp = int(
                                        dt.timestamp() * 1000
                                    )  # 转换为毫秒时间戳
                                    series_data.append(
                                        [timestamp, date_to_growth[date]]
                                    )
                                except ValueError:
                                    series_data.append(
                                        [0, date_to_growth[date]]
                                    )  # 如果日期格式不对，使用0
                            else:
                                try:
                                    dt = datetime.strptime(date, "%Y-%m-%d")
                                    timestamp = int(
                                        dt.timestamp() * 1000
                                    )  # 转换为毫秒时间戳
                                    series_data.append([timestamp, None])
                                except ValueError:
                                    series_data.append(
                                        [0, None]
                                    )  # 如果日期格式不对，使用0
                    else:
                        # 如果没有有效数据，填充None
                        from datetime import datetime

                        for date in chart_data["dates"]:
                            try:
                                dt = datetime.strptime(date, "%Y-%m-%d")
                                timestamp = int(
                                    dt.timestamp() * 1000
                                )  # 转换为毫秒时间戳
                                series_data.append([timestamp, None])
                            except ValueError:
                                series_data.append([0, None])  # 如果日期格式不对，使用0
                else:
                    # 使用原始净值数据
                    from datetime import datetime

                    for date in chart_data["dates"]:
                        if date in date_to_value and date_to_value[date] is not None:
                            try:
                                dt = datetime.strptime(date, "%Y-%m-%d")
                                timestamp = int(
                                    dt.timestamp() * 1000
                                )  # 转换为毫秒时间戳
                                series_data.append(
                                    [timestamp, round(float(date_to_value[date]), 4)]
                                )
                            except ValueError:
                                series_data.append(
                                    [0, round(float(date_to_value[date]), 4)]
                                )  # 如果日期格式不对，使用0
                        else:
                            try:
                                dt = datetime.strptime(date, "%Y-%m-%d")
                                timestamp = int(
                                    dt.timestamp() * 1000
                                )  # 转换为毫秒时间戳
                                series_data.append([timestamp, None])
                            except ValueError:
                                series_data.append([0, None])  # 如果日期格式不对，使用0

                # 获取基金名称
                fund_name = symbol
                # 从预定义基金列表中查找名称
                for fund in SELECTED_FUND_LIST:
                    if str(fund["基金代码"]) == symbol:
                        fund_name = fund["基金简称"]
                        break

                # 返回ECharts需要的格式
                chart_data["series"].append(
                    {
                        "name": fund_name,
                        "type": "line",
                        "data": series_data,
                        "smooth": True,
                        "connectNulls": False,
                        "showSymbol": False,
                        "lineStyle": {"width": 2},
                        "emphasis": {"focus": "series"},
                    }
                )

        # 缓存数据
        set_fund_cache_data(cache_key, chart_data)
        logger.info(f"准备好的基金图表数据已缓存: {symbols}")

        return chart_data
    except Exception as e:
        logger.error(f"准备基金图表数据失败: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    # 测试函数
    print("测试基金数据获取功能...")

    # 测试获取手动选择的基金列表
    print("\n1.1 测试获取手动选择的基金列表:")
    try:
        selected_funds = get_selected_fund_list()
        print(f"获取到 {len(selected_funds)} 只手动选择的基金")
        for i, fund in enumerate(selected_funds[:5]):  # 显示前5只
            print(f"  {i+1}. {fund}")
    except Exception as e:
        print(f"获取手动选择的基金列表失败: {e}")

    # 测试获取某只基金的历史数据
    print("\n2. 测试获取基金历史数据 (示例基金 512400):")
    try:
        test_fund = selected_funds[0]  # 使用手动选择的第一只基金作为测试
        fund_history = get_fund_history(test_fund["基金代码"], period="3M")
        print(f"获取到基金 {test_fund['基金代码']} 历史数据 {len(fund_history)} 条")
        if not fund_history.empty:
            print(f"最近3天数据: \n{fund_history.tail(3)}")
    except Exception as e:
        print(f"获取基金历史数据失败: {e}")

    # 测试获取动态选择的基金
    print("\n3. 测试获取动态选择的基金:")
    try:
        dynamic_funds = get_fund_dynamic_list(top_n=5)
        print(f"获取到动态选择的基金 {len(dynamic_funds)} 只")
        for fund in dynamic_funds:
            print(f"  {fund['name']}({fund['symbol']}): {fund['change_percent']}%")
    except Exception as e:
        print(f"获取动态选择的基金失败: {e}")
