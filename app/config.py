"""Central configuration: constants, index mappings, time windows."""

from typing import Optional

# Risk-free rate: China 10Y government bond yield (~2.5% annualized)
RISK_FREE_RATE_ANNUAL: float = 0.025

# Analysis windows: (label, days_back)
TIME_WINDOWS: list[tuple[str, int]] = [
    ("3年", 1095),
    ("1年", 365),
    ("6个月", 182),
    ("3个月", 91),
    ("1个月", 30),
    ("1周", 7),
]

# Chinese index name -> akshare stock code (for index_zh_a_hist)
# None means skip (bond/deposit types)
INDEX_NAME_TO_CODE: dict[str, Optional[str]] = {
    "沪深300": "000300",
    "中证500": "000905",
    "中证1000": "000852",
    "中证800": "000906",
    "中证700": "000907",
    "中证全指": "000985",
    "中证红利": "000922",
    "中证转债": "000832",
    "上证50": "000016",
    "上证180": "000010",
    "上证380": "000009",
    "上证综指": "000001",
    "深证成指": "399001",
    "深证100": "399330",
    "创业板指": "399006",
    "创业板指数": "399006",
    "科创50": "000688",
    "中证消费": "000932",
    "中证医药": "000933",
    "中证信息": "000935",
    "中证金融": "000934",
    "中证可选": "000931",
    # Common thematic indices (non-overlapping with above)
    "中证内地消费主题指数": "000942",
    "中证内地消费主题": "000942",
    "中证内地消费": "000942",
    "中证科技龙头": "931087",
    "中证新能源": "000941",
    "中证医疗": "000913",
    "中证军工": "399967",
    "中证银行": "399986",
    "中证证券": "399975",
    "中证白酒": "399997",
    "上证消费": "000036",
    "上证医药": "000037",
    "深证红利": "399324",
    "中证环保": "000827",
    "中证体育": "399804",
    "中证TMT": "000998",
    "中证人工智能": "399812",
    "恒生指数": "HSI",
    "标普500": "SPX",
    "纳斯达克100": "NDX",
    # Bond / deposit indices (skipped)
    "中证综合债": None,
    "中证综合债券": None,
    "中证国债": None,
    "中证信用债": None,
    "中证短融": None,
    "银行活期存款利率": None,
    "银行定期存款利率": None,
    "一年期定期存款": None,
    "同业存款利率": None,
}

# Keywords that indicate a bond or deposit component (to skip)
BOND_KEYWORDS: list[str] = [
    "债券", "国债", "存款", "信用", "短融", "央票", "货币", "债",
]

# Column name aliases to handle akshare version differences
NAV_DATE_ALIASES: list[str] = ["净值日期", "x", "date"]
NAV_VALUE_ALIASES: list[str] = ["单位净值", "累计净值", "y"]
NAV_RETURN_ALIASES: list[str] = ["日增长率", "equityReturn", "daily_return"]

INDEX_DATE_ALIASES: list[str] = ["日期", "date"]
INDEX_CLOSE_ALIASES: list[str] = ["收盘", "close", "收盘价"]

# Cache TTLs in seconds
CACHE_TTL: dict[str, int] = {
    "fund_list": 86400,       # 24h
    "fund_overview": 604800,  # 7d
    "nav_history": 3600,      # 1h
    "index_history": 3600,    # 1h
}

# UI constants
SEARCH_DEBOUNCE_MS: int = 300
CHART_DPI: int = 100
TABLE_DECIMALS: int = 4

# Minimum observations required for regression
MIN_OBSERVATIONS: int = 20
