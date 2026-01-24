"""
指数数据获取模块
支持A股主要指数的获取和处理
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional
import json

# 导入缓存系统
from cache_with_database import get_index_cached_data, set_index_cache_data

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#############################sina interface###################

SINA_ALL_INDEX = [
    {"symbol": "sz980018", "name": "卫星通信", "interface": "sina"},
    {"symbol": "sz399434", "name": "数字传媒", "interface": "sina"},
    {"symbol": "sz399971", "name": "中证传媒", "interface": "sina"},
    {"symbol": "sz399654", "name": "深证文化", "interface": "sina"},
    {"symbol": "sz399264", "name": "创业软件", "interface": "sina"},
    {"symbol": "sz980076", "name": "通用航空", "interface": "sina"},
    {"symbol": "sz399959", "name": "军工指数", "interface": "sina"},
    {"symbol": "sz399973", "name": "中证国防", "interface": "sina"},
    {"symbol": "sh000823", "name": "800有色", "interface": "sina"},
    {"symbol": "sz399967", "name": "中证军工", "interface": "sina"},
    {"symbol": "sh000819", "name": "有色金属", "interface": "sina"},
    {"symbol": "sz399368", "name": "国证军工", "interface": "sina"},
    {"symbol": "sz399397", "name": "国证文化", "interface": "sina"},
    {"symbol": "sz399652", "name": "中创高新", "interface": "sina"},
    {"symbol": "sz399366", "name": "能源金属", "interface": "sina"},
    {"symbol": "sh000689", "name": "科创材料", "interface": "sina"},
    {"symbol": "sz399704", "name": "深证上游", "interface": "sina"},
    {"symbol": "sz399395", "name": "国证有色", "interface": "sina"},
    {"symbol": "sh000131", "name": "上证高新", "interface": "sina"},
    {"symbol": "sh000071", "name": "材料等权", "interface": "sina"},
    {"symbol": "sh000698", "name": "科创100", "interface": "sina"},
    {"symbol": "sh000033", "name": "上证材料", "interface": "sina"},
    {"symbol": "sh000987", "name": "全指材料", "interface": "sina"},
    {"symbol": "sh000693", "name": "科创机械", "interface": "sina"},
    {"symbol": "sz399232", "name": "采矿指数", "interface": "sina"},
    {"symbol": "sz399614", "name": "深证材料", "interface": "sina"},
    {"symbol": "sh000856", "name": "500工业", "interface": "sina"},
    {"symbol": "sz399970", "name": "移动互联", "interface": "sina"},
    {"symbol": "sz399248", "name": "文化指数", "interface": "sina"},
    {"symbol": "sz399284", "name": "AI 50", "interface": "sina"},
    {"symbol": "sh000858", "name": "500信息", "interface": "sina"},
    {"symbol": "sh000692", "name": "科创新能", "interface": "sina"},
    {"symbol": "sz399804", "name": "中证体育", "interface": "sina"},
    {"symbol": "sz399639", "name": "深证大宗", "interface": "sina"},
    {"symbol": "sh000680", "name": "科创综指", "interface": "sina"},
    {"symbol": "sh000681", "name": "科创价格", "interface": "sina"},
    {"symbol": "sh000682", "name": "科创信息", "interface": "sina"},
    {"symbol": "sz399020", "name": "创业小盘", "interface": "sina"},
    {"symbol": "sh000905", "name": "中证500", "interface": "sina"},
    {"symbol": "sz399376", "name": "小盘成长", "interface": "sina"},
    {"symbol": "sh000066", "name": "上证商品", "interface": "sina"},
    {"symbol": "sz399994", "name": "信息安全", "interface": "sina"},
    {"symbol": "sz399018", "name": "创业创新", "interface": "sina"},
    {"symbol": "sh000146", "name": "优势制造", "interface": "sina"},
    {"symbol": "sz399551", "name": "央视创新", "interface": "sina"},
    {"symbol": "sz399263", "name": "创业数字", "interface": "sina"},
    {"symbol": "sz399303", "name": "国证2000", "interface": "sina"},
    {"symbol": "sz399401", "name": "中小盘", "interface": "sina"},
    {"symbol": "sz399852", "name": "中证1000", "interface": "sina"},
    {"symbol": "sz399620", "name": "深证信息", "interface": "sina"},
    {"symbol": "sz399388", "name": "1000信息", "interface": "sina"},
    {"symbol": "sz399989", "name": "中证医疗", "interface": "sina"},
    {"symbol": "sz399982", "name": "500等权", "interface": "sina"},
    {"symbol": "sz399642", "name": "中小新兴", "interface": "sina"},
    {"symbol": "sz399267", "name": "专精特新", "interface": "sina"},
    {"symbol": "sz399687", "name": "深成信息", "interface": "sina"},
    {"symbol": "sz399696", "name": "深证创投", "interface": "sina"},
    {"symbol": "sh000688", "name": "科创50", "interface": "sina"},
    {"symbol": "sz399432", "name": "智能汽车", "interface": "sina"},
    {"symbol": "sz399699", "name": "金融科技", "interface": "sina"},
    {"symbol": "sz399016", "name": "深证创新", "interface": "sina"},
    {"symbol": "sz399805", "name": "互联金融", "interface": "sina"},
    {"symbol": "sz399277", "name": "公共健康", "interface": "sina"},
    {"symbol": "sh000097", "name": "高端装备", "interface": "sina"},
    {"symbol": "sh000690", "name": "科创成长", "interface": "sina"},
    {"symbol": "sh000039", "name": "上证信息", "interface": "sina"},
    {"symbol": "sh000993", "name": "全指信息", "interface": "sina"},
    {"symbol": "sz399976", "name": "CS新能车", "interface": "sina"},
    {"symbol": "sz399996", "name": "智能家居", "interface": "sina"},
    {"symbol": "sh000935", "name": "中证信息", "interface": "sina"},
    {"symbol": "sz980035", "name": "化肥农药", "interface": "sina"},
    {"symbol": "sh000683", "name": "科创生物", "interface": "sina"},
    {"symbol": "sz399275", "name": "创医药", "interface": "sina"},
    {"symbol": "sz399008", "name": "中小300", "interface": "sina"},
    {"symbol": "sz399265", "name": "创新药械", "interface": "sina"},
    {"symbol": "sz399375", "name": "中盘价值", "interface": "sina"},
    {"symbol": "sh000077", "name": "信息等权", "interface": "sina"},
    {"symbol": "sz399102", "name": "创业板综", "interface": "sina"},
    {"symbol": "sz399649", "name": "中小红利", "interface": "sina"},
    {"symbol": "sz399692", "name": "创业低波", "interface": "sina"},
    {"symbol": "sz399935", "name": "中证信息", "interface": "sina"},
    {"symbol": "sz399283", "name": "机器人50", "interface": "sina"},
    {"symbol": "sz399674", "name": "深A医药", "interface": "sina"},
    {"symbol": "sz399107", "name": "深证Ａ指", "interface": "sina"},
    {"symbol": "sz399106", "name": "深证综指", "interface": "sina"},
    {"symbol": "sz399276", "name": "创科技", "interface": "sina"},
    {"symbol": "sh000004", "name": "工业指数", "interface": "sina"},
    {"symbol": "sz399262", "name": "数字经济", "interface": "sina"},
    {"symbol": "sz399695", "name": "深证节能", "interface": "sina"},
    {"symbol": "sz399317", "name": "国证Ａ指", "interface": "sina"},
    {"symbol": "sh000057", "name": "全指成长", "interface": "sina"},
    {"symbol": "sz399441", "name": "生物医药", "interface": "sina"},
    {"symbol": "sz399389", "name": "国证通信", "interface": "sina"},
    {"symbol": "sz399295", "name": "创价值", "interface": "sina"},
    {"symbol": "sh000158", "name": "上证环保", "interface": "sina"},
    {"symbol": "sz399419", "name": "国证高铁", "interface": "sina"},
    {"symbol": "sh000865", "name": "上海国企", "interface": "sina"},
    {"symbol": "sz399233", "name": "制造指数", "interface": "sina"},
    {"symbol": "sz980032", "name": "新能电池", "interface": "sina"},
    {"symbol": "sz980030", "name": "消费电子", "interface": "sina"},
    {"symbol": "sz399001", "name": "深证成指", "interface": "sina"},
    {"symbol": "sz399602", "name": "中小成长", "interface": "sina"},
    {"symbol": "sz399809", "name": "保险主题", "interface": "sina"},
    {"symbol": "sz399667", "name": "创业成长", "interface": "sina"},
    {"symbol": "sz399604", "name": "中小价值", "interface": "sina"},
    {"symbol": "sz399417", "name": "新能源车", "interface": "sina"},
    {"symbol": "sh000128", "name": "380基本", "interface": "sina"},
    {"symbol": "sz399280", "name": "生物50", "interface": "sina"},
    {"symbol": "sz399440", "name": "国证钢铁", "interface": "sina"},
    {"symbol": "sz399377", "name": "小盘价值", "interface": "sina"},
    {"symbol": "sz399608", "name": "科技100", "interface": "sina"},
    {"symbol": "sz980015", "name": "疫苗生科", "interface": "sina"},
    {"symbol": "sz399615", "name": "深证工业", "interface": "sina"},
    {"symbol": "sz399913", "name": "300医药", "interface": "sina"},
    {"symbol": "sz399808", "name": "中证新能", "interface": "sina"},
    {"symbol": "sh000037", "name": "上证医药", "interface": "sina"},
    {"symbol": "sz399439", "name": "国证油气", "interface": "sina"},
    {"symbol": "sh000906", "name": "中证800", "interface": "sina"},
    {"symbol": "sz399235", "name": "建筑指数", "interface": "sina"},
    {"symbol": "sh000991", "name": "全指医药", "interface": "sina"},
    {"symbol": "sz399643", "name": "创业新兴", "interface": "sina"},
    {"symbol": "sz399007", "name": "深证300", "interface": "sina"},
    {"symbol": "sz399618", "name": "深证医药", "interface": "sina"},
    {"symbol": "sz399995", "name": "基建工程", "interface": "sina"},
    {"symbol": "sz399339", "name": "深证科技", "interface": "sina"},
    {"symbol": "sh000047", "name": "上证全指", "interface": "sina"},
    {"symbol": "sh000065", "name": "上证龙头", "interface": "sina"},
    {"symbol": "sh000001", "name": "上证指数", "interface": "sina"},
    {"symbol": "sz399006", "name": "创业板指", "interface": "sina"},
    {"symbol": "sz399266", "name": "创新能源", "interface": "sina"},
    {"symbol": "sz980016", "name": "医疗健康", "interface": "sina"},
    {"symbol": "sh000121", "name": "医药主题", "interface": "sina"},
    {"symbol": "sz399688", "name": "深成电信", "interface": "sina"},
    {"symbol": "sh000510", "name": "中证A500", "interface": "sina"},
    {"symbol": "sz399613", "name": "深证能源", "interface": "sina"},
    {"symbol": "sz399655", "name": "深证绩效", "interface": "sina"},
    {"symbol": "sz399698", "name": "优势成长", "interface": "sina"},
    {"symbol": "sz399379", "name": "国证基金", "interface": "sina"},
    {"symbol": "sh000139", "name": "上证转债", "interface": "sina"},
    {"symbol": "sz399705", "name": "深证中游", "interface": "sina"},
    {"symbol": "sz399348", "name": "深证价值", "interface": "sina"},
    {"symbol": "sz399312", "name": "国证300", "interface": "sina"},
    {"symbol": "sz399630", "name": "1000成长", "interface": "sina"},
    {"symbol": "sz399412", "name": "国证新能", "interface": "sina"},
    {"symbol": "sz399240", "name": "金融指数", "interface": "sina"},
    {"symbol": "sz399626", "name": "中创成长", "interface": "sina"},
    {"symbol": "sh000075", "name": "医药等权", "interface": "sina"},
    {"symbol": "sh000070", "name": "能源等权", "interface": "sina"},
    {"symbol": "sz399363", "name": "国证算力", "interface": "sina"},
    {"symbol": "sh000109", "name": "380医药", "interface": "sina"},
    {"symbol": "sh000118", "name": "380价值", "interface": "sina"},
    {"symbol": "sz399933", "name": "中证医药", "interface": "sina"},
    {"symbol": "sz399814", "name": "大农业", "interface": "sina"},
    {"symbol": "sz399234", "name": "水电指数", "interface": "sina"},
    {"symbol": "sz399636", "name": "深证装备", "interface": "sina"},
    {"symbol": "sh000072", "name": "工业等权", "interface": "sina"},
    {"symbol": "sh000155", "name": "市值百强", "interface": "sina"},
    {"symbol": "sh000034", "name": "上证工业", "interface": "sina"},
    {"symbol": "sz399631", "name": "1000价值", "interface": "sina"},
    {"symbol": "sz399261", "name": "创业制造", "interface": "sina"},
    {"symbol": "sh000056", "name": "上证国企", "interface": "sina"},
    {"symbol": "sz399680", "name": "深成能源", "interface": "sina"},
    {"symbol": "sh000063", "name": "上证周期", "interface": "sina"},
    {"symbol": "sz399402", "name": "周期100", "interface": "sina"},
    {"symbol": "sh000050", "name": "50等权", "interface": "sina"},
    {"symbol": "sz399806", "name": "环境治理", "interface": "sina"},
    {"symbol": "sz399258", "name": "绿色低碳", "interface": "sina"},
    {"symbol": "sh000016", "name": "上证50", "interface": "sina"},
    {"symbol": "sz399351", "name": "创新示范", "interface": "sina"},
    {"symbol": "sh000867", "name": "港中小企", "interface": "sina"},
    {"symbol": "sz399812", "name": "养老产业", "interface": "sina"},
    {"symbol": "sh000986", "name": "全指能源", "interface": "sina"},
    {"symbol": "sz399686", "name": "深成金融", "interface": "sina"},
    {"symbol": "sz399300", "name": "沪深300", "interface": "sina"},
    {"symbol": "sz399259", "name": "创业低碳", "interface": "sina"},
    {"symbol": "sz399293", "name": "创业大盘", "interface": "sina"},
    {"symbol": "sh000032", "name": "上证能源", "interface": "sina"},
    {"symbol": "sz399346", "name": "深证成长", "interface": "sina"},
    {"symbol": "sh000989", "name": "全指可选", "interface": "sina"},
    {"symbol": "sz399372", "name": "大盘成长", "interface": "sina"},
    {"symbol": "sz399619", "name": "深证金融", "interface": "sina"},
    {"symbol": "sh000928", "name": "中证能源", "interface": "sina"},
    {"symbol": "sz399371", "name": "国证价值", "interface": "sina"},
    {"symbol": "sz399381", "name": "1000能源", "interface": "sina"},
    {"symbol": "sz399365", "name": "国证粮食", "interface": "sina"},
    {"symbol": "sh000827", "name": "中证环保", "interface": "sina"},
    {"symbol": "sz399436", "name": "绿色煤炭", "interface": "sina"},
    {"symbol": "sz399324", "name": "深证红利", "interface": "sina"},
    {"symbol": "sz399437", "name": "证券龙头", "interface": "sina"},
    {"symbol": "sz399990", "name": "煤炭等权", "interface": "sina"},
    {"symbol": "sz399928", "name": "中证能源", "interface": "sina"},
    {"symbol": "sz399638", "name": "深证环保", "interface": "sina"},
    {"symbol": "sz399669", "name": "深证农业", "interface": "sina"},
    {"symbol": "sz399975", "name": "证券公司", "interface": "sina"},
    {"symbol": "sz399637", "name": "深证地产", "interface": "sina"},
    {"symbol": "sh000122", "name": "农业主题", "interface": "sina"},
    {"symbol": "sh000058", "name": "全指价值", "interface": "sina"},
    {"symbol": "sh000076", "name": "金融等权", "interface": "sina"},
    {"symbol": "sz399353", "name": "国证物流", "interface": "sina"},
    {"symbol": "sz980028", "name": "龙头家电", "interface": "sina"},
    {"symbol": "sz399622", "name": "深证公用", "interface": "sina"},
    {"symbol": "sz399260", "name": "先进制造", "interface": "sina"},
    {"symbol": "sz399433", "name": "国证交运", "interface": "sina"},
    {"symbol": "sh000035", "name": "上证可选", "interface": "sina"},
    {"symbol": "sz399241", "name": "地产指数", "interface": "sina"},
    {"symbol": "sz399998", "name": "中证煤炭", "interface": "sina"},
    {"symbol": "sh000992", "name": "全指金融", "interface": "sina"},
    {"symbol": "sh000015", "name": "红利指数", "interface": "sina"},
    {"symbol": "sz399934", "name": "中证金融", "interface": "sina"},
    {"symbol": "sh000074", "name": "消费等权", "interface": "sina"},
    {"symbol": "sz399552", "name": "央视成长", "interface": "sina"},
    {"symbol": "sh000038", "name": "上证金融", "interface": "sina"},
    {"symbol": "sz399653", "name": "深证龙头", "interface": "sina"},
    {"symbol": "sz399358", "name": "国证环保", "interface": "sina"},
    {"symbol": "sz399983", "name": "地产等权", "interface": "sina"},
    {"symbol": "sz399438", "name": "绿色电力", "interface": "sina"},
    {"symbol": "sz399321", "name": "国证红利", "interface": "sina"},
    {"symbol": "sz399373", "name": "大盘价值", "interface": "sina"},
    {"symbol": "sz399328", "name": "深证治理", "interface": "sina"},
    {"symbol": "sh000152", "name": "上央红利", "interface": "sina"},
    {"symbol": "sh000036", "name": "上证消费", "interface": "sina"},
    {"symbol": "sz399237", "name": "运输指数", "interface": "sina"},
    {"symbol": "sz399431", "name": "国证银行", "interface": "sina"},
    {"symbol": "sz399390", "name": "1000公用", "interface": "sina"},
    {"symbol": "sh000134", "name": "上证银行", "interface": "sina"},
    {"symbol": "sz399359", "name": "国证基建", "interface": "sina"},
    {"symbol": "sh000012", "name": "国债指数", "interface": "sina"},
    {"symbol": "sz399986", "name": "中证银行", "interface": "sina"},
    {"symbol": "sz399396", "name": "国证食品", "interface": "sina"},
    {"symbol": "sz399385", "name": "1000消费", "interface": "sina"},
    {"symbol": "sz399435", "name": "国证农牧", "interface": "sina"},
    {"symbol": "sh000932", "name": "中证消费", "interface": "sina"},
    {"symbol": "sz399617", "name": "深证消费", "interface": "sina"},
    {"symbol": "sz399231", "name": "农林指数", "interface": "sina"},
    {"symbol": "sz399997", "name": "中证白酒", "interface": "sina"}]


SELECTED_MAIN_INDEX = [
    {"symbol": "sh000510", "name": "中证A500", "interface": "sinae"},
    {"symbol": "zs000813", "name": "细分化工", "interface": "eastmoney"},
    {"symbol": "sz399971", "name": "中证传媒", "interface": "sina"}, 
    {"symbol": "sz399804", "name": "中证体育", "interface": "sina"}, 
    {"symbol": "sz399935", "name": "中证信息", "interface": "sina"}, 
    {"symbol": "sz399967", "name": "中证军工", "interface": "sina"}, 
    {"symbol": "sz399989", "name": "中证医疗", "interface": "sina"}, 
    {"symbol": "sz399933", "name": "中证医药", "interface": "sina"}, 
    {"symbol": "sz399808", "name": "中证新能", "interface": "sina"}, 
    {"symbol": "sz399932", "name": "中证消费", "interface": "sina"}, 
    {"symbol": "sz399998", "name": "中证煤炭", "interface": "sina"}, 
    {"symbol": "sh000827", "name": "中证环保", "interface": "sina"}, 
    {"symbol": "sz399997", "name": "中证白酒", "interface": "sina"}, 
    {"symbol": "sz399928", "name": "中证能源", "interface": "sina"}, 
    {"symbol": "sh000934", "name": "中证金融", "interface": "sina"}, 
    {"symbol": "sz399986", "name": "中证银行", "interface": "sina"}, 
    {"symbol": "sz399283", "name": "机器人50", "interface": "sina"},
    {"symbol": "sz399363", "name": "国证算力", "interface": "sina"}, 
    {"symbol": "sz399365", "name": "国证粮食", "interface": "sina"}, 
    {"symbol": "sz399389", "name": "国证通信", "interface": "sina"}, 
    {"symbol": "sz399395", "name": "国证有色", "interface": "sina"}, 
    {"symbol": "sz399440", "name": "国证钢铁", "interface": "sina"}, 
    {"symbol": "sz399353", "name": "国证物流", "interface": "sina"}, 
    {"symbol": "sz399397", "name": "国证文化", "interface": "sina"}, 
    {"symbol": "sz399435", "name": "国证农牧", "interface": "sina"}, 
    {"symbol": "sz980035", "name": "化肥农药", "interface": "sina"}
]


# 注释掉的指数列表（备用）
# SELECTED_SINA_INDEX_BACKUP = [
#    {"symbol": "sz399813", "name": "中证国安", "interface": "sina"}, 

#    {"symbol": "sh000819", "name": "有色金属", "interface": "sina"}, 
#     {"symbol": "sh000682", "name": "科创信息", "interface": "sina"},
#     {"symbol": "sh000689", "name": "科创材料", "interface": "sina"},
#     {"symbol": "sh000693", "name": "科创机械", "interface": "sina"},
#     {"symbol": "sh000683", "name": "科创生物", "interface": "sina"},
#     {"symbol": "sh000933", "name": "中证医药", "interface": "sina"},
#     {"symbol": "sz399441", "name": "生物医药", "interface": "sina"},
#     {"symbol": "sz399394", "name": "国证医药", "interface": "sina"},
#     {"symbol": "sh000935", "name": "中证信息", "interface": "sina"},
#     {"symbol": "sz399973", "name": "中证国防", "interface": "sina"},
#     {"symbol": "sz399417", "name": "新能源车", "interface": "sina"},
#     {"symbol": "sz399433", "name": "国证交运", "interface": "sina"},
#     {"symbol": "sz399368", "name": "国证军工", "interface": "sina"}
# ]


def get_sina_index_spot_data():
    """
    获取新浪指数实时数据并加入缓存
    """
    cache_key = "sina_index_spot_data"
    
    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, pd.DataFrame) and not cached_data.empty:
        logger.info("从缓存获取新浪指数实时数据")
        return cached_data
    elif cached_data is not None and isinstance(cached_data, list):
        # 如果缓存的是字典列表，转换回DataFrame
        df_from_cache = pd.DataFrame(cached_data) if cached_data else pd.DataFrame()
        logger.info("从缓存获取新浪指数实时数据")
        return df_from_cache
    try:
        df = ak.stock_zh_index_spot_sina()
        # 将DataFrame转换为字典列表进行缓存，避免JSON序列化问题
        df_dict = df.to_dict('records') if not df.empty else []
        set_index_cache_data(cache_key, df_dict)
        logger.info(f"使用新浪接口获取到 {len(df)} 条指数实时数据并存入缓存")
        return df
    except Exception as e:
        logger.error(f"获取新浪指数实时数据失败: {e}")
        return pd.DataFrame()

def get_index_daily_data(symbol):
    cache_key = f"sina_index_{symbol}_daily"
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, pd.DataFrame) and not cached_data.empty:
        logger.info(f"从缓存获取新浪{symbol}daily数据")
        return cached_data
    elif cached_data is not None and isinstance(cached_data, list):
        # 如果缓存的是字典列表，转换回DataFrame
        df_from_cache = pd.DataFrame(cached_data) if cached_data else pd.DataFrame()
        logger.info(f"从缓存获取新浪{symbol}daily数据")
        return df_from_cache
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        # 确保日期列是datetime类型并转换为字符串格式，避免JSON序列化问题
        if not df.empty and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
        # 将DataFrame转换为字典列表进行缓存，避免JSON序列化问题
        df_dict = df.to_dict('records') if not df.empty else []
        set_index_cache_data(cache_key, df_dict)
        logger.info(f"使用新浪接口获取到 {len(df)} 条新数历史数据并存入缓存")
        return df
    except Exception as e:
        logger.error(f"获取新浪指数实时数据失败: {e}")
        return pd.DataFrame()



def get_main_index_list():
    """
    获取主要指数列表
    """
    cache_key = "index_main_list"
    
    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
        logger.info("从缓存获取主要指数列表")
        return cached_data
    
    try:
        # 从实时行情获取数据
        df = get_sina_index_spot_data()
        
        # 过滤出主要指数
        index_list = []
        for idx in SELECTED_MAIN_INDEX:
            filtered_df = df[df['代码'] == idx['symbol']]
            if not filtered_df.empty:
                row = filtered_df.iloc[0]
                index_info = {
                    'symbol': idx['symbol'],
                    'name': idx['name'],
                    'current_price': float(row['最新价']) if pd.notna(row['最新价']) else 0.0,
                    'change_percent': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else 0.0,
                    'change_amount': float(row['涨跌额']) if pd.notna(row['涨跌额']) else 0.0,
                    'volume': int(row['成交量']) if pd.notna(row['成交量']) else 0,
                    'amount': float(row['成交额']) if pd.notna(row['成交额']) else 0.0
                }
                index_list.append(index_info)
            else:
                logger.warning(f"未找到指数 {idx['symbol']} 的实时数据")

        set_index_cache_data(cache_key, index_list)
        
        return index_list
    except Exception as e:
        logger.error(f"获取主要指数列表失败: {e}")
        return [
            {'symbol': idx['symbol'], 'name': idx['name'], 'current_price': 0.0, 
             'change_percent': 0.0, 'change_amount': 0.0, 'volume': 0, 'amount': 0.0} 
            for idx in SELECTED_MAIN_INDEX
        ]


def get_index_history(symbol: str, period: str = "12M"):
    """
    获取单个指数历史数据
    :param symbol: 指数代码
    :param period: 时间周期，默认12个月
    """
    cache_key = f"index_history_{symbol}_{period}"

    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
        logger.info(f"从缓存获取指数历史数据: {symbol}")
        return cached_data
    
    try:
        df = get_index_daily_data(symbol)

        # 如果是中文列名，转换为英文
        if '日期' in df.columns:
            df.rename(columns={
                '日期': 'date',
                '开盘': 'open',
                '收盘': 'close',
                '最高': 'high',
                '最低': 'low',
                '成交量': 'volume',
                '成交额': 'amount'
            }, inplace=True)
        # 确保所需的列存在
        required_columns = ['date', 'open', 'close', 'high', 'low', 'volume', 'amount']
        for col in required_columns:
            if col not in df.columns:
                df[col] = 0 if col != 'date' else pd.NaT

        # 转换日期格式
        df['date'] = pd.to_datetime(df['date'])
        
        # 计算时间范围
        end_date = datetime.now()
        if period.endswith('D'):
            # 处理天数周期
            days = int(period[:-1])
            start_date = end_date - timedelta(days=days)
        elif period.endswith('M'):
            months = int(period[:-1])
            start_date = end_date - timedelta(days=months*30)
        elif period.endswith('Y'):
            years = int(period[:-1])
            start_date = end_date - timedelta(days=years*365)
        else:
            start_date = end_date - timedelta(days=365)  # 默认一年
        
        # 筛选指定时间范围内的数据
        df = df[df['date'] >= start_date]
        df = df.sort_values('date')
        
        # 转换为字典列表格式
        result = []
        for _, row in df.iterrows():
            item = {
                'date': row['date'].strftime('%Y-%m-%d'),
                'open': float(row['open']) if pd.notna(row['open']) else 0.0,
                'close': float(row['close']) if pd.notna(row['close']) else 0.0,
                'high': float(row['high']) if pd.notna(row['high']) else 0.0,
                'low': float(row['low']) if pd.notna(row['low']) else 0.0,
                'volume': int(row['volume']) if pd.notna(row['volume']) else 0,
                'amount': float(row['amount']) if pd.notna(row['amount']) else 0.0
            }
            result.append(item)
        
        # 在缓存前确保所有数据都是JSON可序列化的
        set_index_cache_data(cache_key, result)
        
        return result
    except Exception as e:
        logger.error(f"获取指数历史数据失败 {symbol}: {e}")
        return []


def get_index_ranking_optimized(period_days=30, use_sina_ranking=False):
    """
    优化版本的获取指数涨跌幅排名函数
    该版本不调用get_index_history获取完整历史数据，而是直接从get_index_daily_data获取指定日期的收盘价
    :param period_days: 时间周期（天数），默认30天
    :param use_sina_ranking: 是否使用新浪指数数据
        - True: 返回所有新浪指数的排名（基于历史数据计算周期涨跌幅）
        - False: 返回SELECTED_MAIN_INDEX中定义的指数排名（基于历史数据计算周期涨跌幅）
    """
    logger.info(f"开始获取指数排名（优化版），周期: {period_days}天, use_sina_ranking: {use_sina_ranking}")
    
    # 根据参数设置不同的缓存键，避免缓存冲突
    if use_sina_ranking:
        cache_key = f"index_ranking_all_sina_optimized_{period_days}"
    else:
        cache_key = f"index_ranking_main_optimized_{period_days}"
    
    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
        logger.info(f"从缓存获取指数排名（优化版，{period_days}天周期，use_sina_ranking={use_sina_ranking}）")
        return cached_data
    
    try:
        def _get_close_price_on_date(symbol, target_date, max_days_diff=3):
            """
            从指数日线数据中获取指定日期或相近日期的收盘价
            :param symbol: 指数代码
            :param target_date: 目标日期
            :param max_days_diff: 最大日期差异（天数），默认3天
            :return: 收盘价，如果找不到则返回None
            """
            # 获取指数日线数据
            daily_data = get_index_daily_data(symbol)
            
            if daily_data is None or daily_data.empty:
                logger.warning(f"无法获取指数 {symbol} 的日线数据")
                return None
            
            # 转换为字典列表以便处理
            if isinstance(daily_data, pd.DataFrame):
                daily_list = daily_data.to_dict('records')
            else:
                daily_list = daily_data
            
            if not daily_list:
                logger.warning(f"指数 {symbol} 没有日线数据")
                return None
            
            # 按日期排序（从近到远）
            daily_list_sorted = sorted(daily_list, key=lambda x: x['date'], reverse=True)
            
            # 查找精确匹配的日期
            target_date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            
            # 首先尝试精确匹配
            for item in daily_list_sorted:
                try:
                    item_date = datetime.strptime(item['date'], '%Y-%m-%d')
                    if item_date.date() == target_date_obj.date():
                        return item['close']
                except (ValueError, KeyError) as e:
                    logger.debug(f"处理日期时出错 {symbol}: {e}")
                    continue
            
            # 如果没有精确匹配，查找最接近的日期（在允许误差范围内）
            for item in daily_list_sorted:
                try:
                    item_date = datetime.strptime(item['date'], '%Y-%m-%d')
                    date_diff = abs((item_date - target_date_obj).days)
                    
                    # 如果日期差在允许范围内
                    if date_diff <= max_days_diff:
                        return item['close']
                except (ValueError, KeyError) as e:
                    logger.debug(f"处理日期时出错 {symbol}: {e}")
                    continue
            
            # 如果没有找到合适的日期，返回最近的数据
            if daily_list_sorted:
                return daily_list_sorted[0]['close']
            
            return None
        
        def _get_latest_and_start_prices(symbol, period_days):
            """
            获取指数的最新价格和指定周期前的价格
            :param symbol: 指数代码
            :param period_days: 周期天数
            :return: (latest_close, start_close) 或 (None, None) 如果失败
            """
            # 获取指数日线数据
            daily_data = get_index_daily_data(symbol)
            
            if daily_data is None or daily_data.empty:
                logger.warning(f"无法获取指数 {symbol} 的日线数据")
                return None, None
            
            # 转换为字典列表以便处理
            if isinstance(daily_data, pd.DataFrame):
                daily_list = daily_data.to_dict('records')
            else:
                daily_list = daily_data
            
            # 按日期排序（从近到远）
            daily_list_sorted = sorted(daily_list, key=lambda x: x['date'], reverse=True)
            
            # 获取最新价格（最后一个数据）
            latest_item = daily_list_sorted[0]
            latest_close = latest_item['close'] if 'close' in latest_item and latest_item['close'] else 0.0
            
            # 获取目标日期
            target_date = (datetime.now() - timedelta(days=period_days)).strftime('%Y-%m-%d')
            
            # 获取目标日期的价格
            start_close = _get_close_price_on_date(symbol, target_date, max_days_diff=3)
            
            return latest_close, start_close
        
        def _calculate_change_percent_optimized(symbol, name, period_days):
            """使用优化方法计算指数涨跌幅的内部函数"""
            if not symbol or not name:
                return None
                
            # 获取最新价格和起始价格
            latest_close, start_close = _get_latest_and_start_prices(symbol, period_days)
            
            if latest_close is None or start_close is None or start_close == 0:
                logger.warning(f"无法获取指数 {symbol} 的价格数据")
                return None
            
            logger.debug(f"指数 {name} ({symbol}) 最新价格: {latest_close}, 起始价格: {start_close}")
            
            if start_close != 0:
                change_percent = ((latest_close - start_close) / start_close) * 100
                return {
                    'symbol': symbol,
                    'name': name,
                    'current_price': latest_close,
                    'change_percent': round(change_percent, 2),
                    'change_amount': round(latest_close - start_close, 2),
                    'volume': 0,  # 由于只获取日线数据，无法获取成交量
                    'amount': 0.0  # 由于只获取日线数据，无法获取成交额
                }
            return None
        
        if use_sina_ranking:
            # 使用所有新浪指数数据获取排名（基于历史数据计算周期涨跌幅）
            logger.info("使用所有新浪指数数据获取排名（优化版，基于历史数据）")
            # 直接使用预定义的SINA_ALL_INDEX列表
            df = SINA_ALL_INDEX
            logger.info(f"使用预定义的SINA_ALL_INDEX列表，包含 {len(df)} 个指数")
            ranking_list = []
            
            # 逐个计算每个指数的涨跌幅
            for item in df:
                symbol = item['symbol']
                name = item['name']
                if pd.notna(name) and name != '':
                    rank_item = _calculate_change_percent_optimized(symbol, name, period_days)
                    
                    if rank_item:
                        ranking_list.append(rank_item)
                        logger.debug(f"添加指数 {symbol} 到排名列表，涨跌幅: {rank_item['change_percent']}%")
                    else:
                        logger.warning(f"无法计算指数 {symbol} 的涨跌幅")
                        # 如果无法计算涨跌幅，使用默认值
                        rank_item = {
                            'symbol': symbol,
                            'name': name,
                            'current_price': 0.0,
                            'change_percent': 0.0,  # 无法计算周期涨跌幅
                            'change_amount': 0.0,
                            'volume': 0,
                            'amount': 0.0
                        }
                        ranking_list.append(rank_item)
                        logger.debug(f"使用默认值添加指数 {symbol}，涨跌幅: 0.0%")
        else:
            # 使用SELECTED_MAIN_INDEX中的指数数据
            logger.info(f"使用优化方法计算 {period_days} 天周期的指数排名（SELECTED_MAIN_INDEX）")
            ranking_list = []
            
            # 逐个计算每个指数的涨跌幅
            for idx in SELECTED_MAIN_INDEX:
                symbol = idx['symbol']
                name = idx['name']
                rank_item = _calculate_change_percent_optimized(symbol, name, period_days)
                
                if rank_item:
                    ranking_list.append(rank_item)
                    logger.debug(f"添加指数 {symbol} 到排名列表，涨跌幅: {rank_item['change_percent']}%")
                else:
                    logger.warning(f"无法计算指数 {symbol} 的涨跌幅")
                    # 如果无法计算涨跌幅，使用当前实时数据作为备选
                    df = get_sina_index_spot_data()
                    filtered_df = df[df['代码'] == symbol]
                    if not filtered_df.empty:
                        row = filtered_df.iloc[0]
                        rank_item = {
                            'symbol': symbol,
                            'name': idx['name'],
                            'current_price': float(row['最新价']) if pd.notna(row['最新价']) else 0.0,
                            'change_percent': 0.0,  # 无法计算周期涨跌幅
                            'change_amount': 0.0,
                            'volume': int(row['成交量']) if pd.notna(row['成交量']) else 0,
                            'amount': float(row['成交额']) if pd.notna(row['成交额']) else 0.0
                        }
                        ranking_list.append(rank_item)
                        logger.debug(f"使用实时数据添加指数 {symbol}，涨跌幅: 0.0%")

        logger.info(f"排序前排名列表长度: {len(ranking_list)}")
        # 按涨跌幅排序
        ranking_list.sort(key=lambda x: x['change_percent'], reverse=True)
        logger.info(f"排序后排名列表长度: {len(ranking_list)}，已按涨跌幅排序")
        
        # 添加排名
        for i, item in enumerate(ranking_list):
            item['rank'] = i + 1
            logger.debug(f"排名 {i+1}: {item['name']} ({item['symbol']}) 涨跌幅: {item['change_percent']}%")
        
        set_index_cache_data(cache_key, ranking_list)
        logger.info(f"成功获取并缓存 {len(ranking_list)} 个指数的排名数据（优化版，{period_days}天周期，use_sina_ranking={use_sina_ranking}）")
        
        return ranking_list
    except Exception as e:
        logger.error(f"获取指数排名失败（优化版）: {e}", exc_info=True)
        # 返回缓存的数据
        cached_data = get_index_cached_data(cache_key)
        if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
            logger.info(f"返回缓存的指数排名（优化版，{period_days}天周期，use_sina_ranking={use_sina_ranking}）")
            return cached_data
        return []


def get_index_ranking(period_days=30, use_sina_ranking=False):
    """
    获取指数涨跌幅排名
    :param period_days: 时间周期（天数），默认30天
    :param use_sina_ranking: 是否使用新浪指数数据
        - True: 返回所有新浪指数的排名（基于历史数据计算周期涨跌幅）
        - False: 返回SELECTED_MAIN_INDEX中定义的指数排名（基于历史数据计算周期涨跌幅）
    """
    logger.info(f"开始获取指数排名，周期: {period_days}天, use_sina_ranking: {use_sina_ranking}")
    
    # 根据参数设置不同的缓存键，避免缓存冲突
    if use_sina_ranking:
        cache_key = f"index_ranking_all_sina_{period_days}"
    else:
        cache_key = f"index_ranking_main_{period_days}"
    
    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
        logger.info(f"从缓存获取指数排名（{period_days}天周期，use_sina_ranking={use_sina_ranking}）")
        return cached_data
    
    try:
        def _calculate_change_percent(symbol, name, history_data, period_days):
            """计算指数涨跌幅的内部函数"""
            if not history_data or len(history_data) == 0:
                return None
                
            # 获取最新的价格
            latest_data = history_data[-1]
            latest_close = latest_data['close']
            logger.debug(f"指数 {name} ({symbol}) 最新价格: {latest_close}")
            
            # 获取period_days天前的价格
            target_date = datetime.now() - timedelta(days=period_days)
            start_price = None
            
            # 直接查找最接近目标日期的价格，而不是复杂的时间匹配
            # 从最近的数据向前查找，找到最接近目标日期的数据
            for hist_item in reversed(history_data):  # 从后往前遍历
                hist_date = datetime.strptime(hist_item['date'], '%Y-%m-%d')
                if hist_date.date() <= target_date.date():
                    start_price = hist_item['close']
                    break
            
            # 如果没找到合适的价格，使用最早的可用数据
            if start_price is None and len(history_data) > 0:
                start_price = history_data[0]['close']
            
            logger.debug(f"指数 {name} ({symbol}) 起始价格: {start_price}, 最终价格: {latest_close}")
            
            if start_price and start_price != 0:
                change_percent = ((latest_close - start_price) / start_price) * 100
                return {
                    'symbol': symbol,
                    'name': name,
                    'current_price': latest_close,
                    'change_percent': round(change_percent, 2),
                    'change_amount': round(latest_close - start_price, 2),
                    'volume': 0,  # 历史周期数据无法获得累计成交量
                    'amount': 0.0  # 历史周期数据无法获得累计成交额
                }
            return None
        
        if use_sina_ranking:
            # 使用所有新浪指数数据获取排名（基于历史数据计算周期涨跌幅）
            logger.info("使用所有新浪指数数据获取排名（基于历史数据）")
            df = get_sina_index_spot_data()
            logger.info(f"从akshare获取到 {len(df)} 条新浪指数数据")
            ranking_list = []
            
            # 批量获取所有指数的历史数据以提高效率
            symbol_history_map = {}
            for _, row in df.iterrows():
                symbol = row['代码']
                history_data = get_index_history(symbol, period=f"{period_days}D")
                symbol_history_map[symbol] = history_data
            
            # 计算每个指数的周期涨跌幅
            for _, row in df.iterrows():
                symbol = row['代码']
                name = row['名称']
                if pd.notna(name) and name != '':
                    history_data = symbol_history_map.get(symbol, [])
                    rank_item = _calculate_change_percent(symbol, name, history_data, period_days)
                    
                    if rank_item:
                        ranking_list.append(rank_item)
                        logger.debug(f"添加指数 {symbol} 到排名列表，涨跌幅: {rank_item['change_percent']}%")
                    else:
                        logger.warning(f"无法计算指数 {symbol} 的涨跌幅")
                        # 如果无法计算涨跌幅，使用当前实时数据作为备选
                        rank_item = {
                            'symbol': symbol,
                            'name': name,
                            'current_price': float(row['最新价']) if pd.notna(row['最新价']) else 0.0,
                            'change_percent': 0.0,  # 无法计算周期涨跌幅
                            'change_amount': 0.0,
                            'volume': int(row['成交量']) if pd.notna(row['成交量']) else 0,
                            'amount': float(row['成交额']) if pd.notna(row['成交额']) else 0.0
                        }
                        ranking_list.append(rank_item)
                        logger.debug(f"使用实时数据添加指数 {symbol}，涨跌幅: 0.0%")
        else:
            # 使用SELECTED_MAIN_INDEX中的指数数据
            logger.info(f"使用历史数据计算 {period_days} 天周期的指数排名（SELECTED_MAIN_INDEX）")
            # 对于其他周期，需要计算历史涨跌幅
            ranking_list = []
            
            # 批量获取所有指数的历史数据以提高效率
            symbol_history_map = {}
            for idx in SELECTED_MAIN_INDEX:
                logger.debug(f"获取指数: {idx['name']} ({idx['symbol']}) 历史数据")
                history_data = get_index_history(idx['symbol'], period=f"{period_days}D")
                symbol_history_map[idx['symbol']] = history_data
                
            # 计算每个指数的涨跌幅
            for idx in SELECTED_MAIN_INDEX:
                symbol = idx['symbol']
                history_data = symbol_history_map.get(symbol, [])
                name = idx['name']
                rank_item = _calculate_change_percent(symbol, name, history_data, period_days)
                
                if rank_item:
                    ranking_list.append(rank_item)
                    logger.debug(f"添加指数 {symbol} 到排名列表，涨跌幅: {rank_item['change_percent']}%")
                else:
                    logger.warning(f"无法计算指数 {symbol} 的涨跌幅")
                    # 如果无法计算涨跌幅，使用当前实时数据作为备选
                    df = get_sina_index_spot_data()
                    filtered_df = df[df['代码'] == symbol]
                    if not filtered_df.empty:
                        row = filtered_df.iloc[0]
                        rank_item = {
                            'symbol': symbol,
                            'name': idx['name'],
                            'current_price': float(row['最新价']) if pd.notna(row['最新价']) else 0.0,
                            'change_percent': 0.0,  # 无法计算周期涨跌幅
                            'change_amount': 0.0,
                            'volume': int(row['成交量']) if pd.notna(row['成交量']) else 0,
                            'amount': float(row['成交额']) if pd.notna(row['成交额']) else 0.0
                        }
                        ranking_list.append(rank_item)
                        logger.debug(f"使用实时数据添加指数 {symbol}，涨跌幅: 0.0%")
                # 如果历史数据获取失败，使用当前实时数据
                if not history_data or len(history_data) == 0:
                    logger.warning(f"历史数据获取失败或为空，使用实时数据处理指数 {symbol}")
                    df = get_sina_index_spot_data()
                    filtered_df = df[df['代码'] == symbol]
                    if not filtered_df.empty:
                        row = filtered_df.iloc[0]
                        rank_item = {
                            'symbol': symbol,
                            'name': idx['name'],
                            'current_price': float(row['最新价']) if pd.notna(row['最新价']) else 0.0,
                            'change_percent': 0.0,  # 无法计算周期涨跌幅
                            'change_amount': 0.0,
                            'volume': int(row['成交量']) if pd.notna(row['成交量']) else 0,
                            'amount': float(row['成交额']) if pd.notna(row['成交额']) else 0.0
                        }
                        ranking_list.append(rank_item)
                        logger.debug(f"使用实时数据添加指数 {symbol}，涨跌幅: 0.0%")

        logger.info(f"排序前排名列表长度: {len(ranking_list)}")
        # 按涨跌幅排序
        ranking_list.sort(key=lambda x: x['change_percent'], reverse=True)
        logger.info(f"排序后排名列表长度: {len(ranking_list)}，已按涨跌幅排序")
        
        # 添加排名
        for i, item in enumerate(ranking_list):
            item['rank'] = i + 1
            logger.debug(f"排名 {i+1}: {item['name']} ({item['symbol']}) 涨跌幅: {item['change_percent']}%")
        
        set_index_cache_data(cache_key, ranking_list)
        logger.info(f"成功获取并缓存 {len(ranking_list)} 个指数的排名数据（{period_days}天周期，use_sina_ranking={use_sina_ranking}）")
        
        return ranking_list
    except Exception as e:
        logger.error(f"获取指数排名失败: {e}", exc_info=True)
        # 返回缓存的数据
        cached_data = get_index_cached_data(cache_key)
        if cached_data is not None and isinstance(cached_data, list) and len(cached_data) > 0:
            logger.info(f"返回缓存的指数排名（{period_days}天周期，use_sina_ranking={use_sina_ranking}）")
            return cached_data
        return []


def get_multiple_index_history(symbols: List[str], period: str = "12M"):
    """
    获取多个指数历史数据用于对比
    :param symbols: 指数代码列表
    :param period: 时间周期
    """
    cache_key = f"multiple_index_history_{','.join(sorted(symbols))}_{period}"
    
    # 尝试从缓存获取数据
    cached_data = get_index_cached_data(cache_key)
    if cached_data is not None and isinstance(cached_data, dict) and len(cached_data) > 0:
        logger.info(f"从缓存获取多指数历史数据: {symbols}")
        return cached_data
    
    try:
        result = {}
        for symbol in symbols:
            history_data = get_index_history(symbol, period)
            result[symbol] = history_data
        
        set_index_cache_data(cache_key, result)
        
        return result
    except Exception as e:
        logger.error(f"获取多个指数历史数据失败: {e}")
        return {}


def calculate_growth_rate(history_data: List[Dict], base_date: Optional[str] = None):
    """
    计算相对于基准日期的增长率
    :param history_data: 历史数据
    :param base_date: 基准日期，默认使用第一个数据点
    """
    if not history_data:
        logger.warning("历史数据为空，无法计算增长率")
        return []
    
    # 排序确保按日期顺序
    sorted_data = sorted(history_data, key=lambda x: x['date'])
    
    # 确定基准值
    if base_date:
        base_value = None
        for item in sorted_data:
            if item['date'] == base_date:
                base_value = item['close']
                break
        if base_value is None or base_value == 0:
            base_value = sorted_data[0]['close'] if sorted_data[0]['close'] != 0 else 1
            logger.warning(f"基准日期 {base_date} 的数据未找到或价格为0，使用第一个数据点作为基准值: {base_value}")
    else:
        base_value = sorted_data[0]['close'] if sorted_data[0]['close'] != 0 else 1
        logger.info(f"使用第一个数据点作为基准值: {base_value} (日期: {sorted_data[0]['date']})")
    
    # 计算增长率
    growth_data = []
    for item in sorted_data:
        growth_rate = ((item['close'] - base_value) / base_value) * 100 if base_value != 0 else 0
        growth_item = {
            'date': item['date'],
            'growth_rate': round(growth_rate, 2),
            'close': item['close']
        }
        growth_data.append(growth_item)
    
    logger.info(f"成功计算增长率，共 {len(growth_data)} 个数据点")
    return growth_data


if __name__ == "__main__":
    # 测试函数
    print("测试主要指数列表获取:")
    index_list = get_main_index_list()
    for idx in index_list[:]:  # 只打印前3个
        print(idx)
    
    # print("\n测试指数历史数据获取:")
    # history = get_index_history("sz399813")
    # for h in history[-3:]:  # 打印最后3天
    #     print(h)
    
    # print("\n测试指数排名获取:")
    # ranking = get_index_ranking()
    # for r in ranking[:3]:  # 打印前3名
    #     print(r)
    
    # print("\n测试多指数历史数据获取:")
    # multi_history = get_multiple_index_history(["sz399928", "sh000934"])
    # print("\n测试增长率计算:")
    # growth = calculate_growth_rate(history[-10:])  # 使用最后10天数据
    # for g in growth[-3:]:  # 打印最后3天的增长率
    #     print(g)
