from datetime import date, datetime, time

TRADING_CALENDAR_CACHE: dict[date, bool] = {}


def is_trading_day(current_date: date) -> bool:
    """判断当日是否为 A 股交易日。优先查 AkShare 交易日历，失败时降级为周一至周五。"""
    if current_date in TRADING_CALENDAR_CACHE:
        return TRADING_CALENDAR_CACHE[current_date]

    if current_date.weekday() >= 5:
        TRADING_CALENDAR_CACHE[current_date] = False
        return False

    try:
        import akshare as ak

        df = ak.tool_trade_date_hist_sina()
        trading_dates = set(df["trade_date"].tolist())
        for d in trading_dates:
            if isinstance(d, (date, datetime)):
                TRADING_CALENDAR_CACHE[d.date() if isinstance(d, datetime) else d] = True
        is_trade = current_date in TRADING_CALENDAR_CACHE
        TRADING_CALENDAR_CACHE[current_date] = is_trade
        return is_trade
    except Exception:
        is_trade = current_date.weekday() < 5
        TRADING_CALENDAR_CACHE[current_date] = is_trade
        return is_trade


def is_trading_time(now: datetime | None = None) -> bool:
    """判断当前时间是否在 A 股交易时段内（9:30-11:30, 13:00-15:00）。"""
    t = (now or datetime.now()).time()
    morning_start = time(9, 30)
    morning_end = time(11, 30)
    afternoon_start = time(13, 0)
    afternoon_end = time(15, 0)
    return (morning_start <= t <= morning_end) or (afternoon_start <= t <= afternoon_end)
