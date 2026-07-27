import streamlit as st
import sheets_helper as sh
import yfinance as yf
import pandas as pd
import os
import datetime
import div_yf as dyf

@st.cache_data(ttl=300)
def get_stocks_cached():
    return sh.get_stocks()

@st.cache_data(ttl=60)
def get_portfolio_cached():
    return sh.get_portfolio()

@st.cache_data(ttl=60)
def get_watchlist_cached():
    return sh.get_watchlist()

@st.cache_data(ttl=60)
def get_watchlist_details_cached():
    return sh.get_watchlist_details()

@st.cache_data(ttl=60)
def get_alerts_cached():
    return sh.get_alerts()

@st.cache_data(ttl=60)
def get_trading_history_cached():
    return sh.get_trading_history()

@st.cache_data(ttl=60)
def get_order_history_cached():
    ws_ord = sh.get_sh().worksheet("order_history")
    return sh.get_as_dataframe(ws_ord).dropna(subset=["symbol"])

@st.cache_data(ttl=60)
def get_comment_cached(ticker):
    return sh.get_comment(ticker)

@st.cache_data(ttl=60)
def get_comments_list_cached(ticker):
    return sh.get_comments_list(ticker)

@st.cache_data(ttl=30)
def get_alert_prices_cached(tickers_to_check):
    if not tickers_to_check:
        return pd.DataFrame()
    return yf.download(tickers_to_check, period="1d", interval="1m", progress=False)

def clear_all_caches():
    get_stocks_cached.clear()
    get_portfolio_cached.clear()
    get_watchlist_cached.clear()
    get_watchlist_details_cached.clear()
    get_alerts_cached.clear()
    get_trading_history_cached.clear()
    get_order_history_cached.clear()

@st.cache_data
def get_stock_data(ticker):
    os.makedirs("cache", exist_ok=True)
    price_cache_path = f"cache/{ticker}_price.csv"
    div_cache_path = f"cache/{ticker}_div.csv"

    session = dyf.get_yf_session()

    # 1. 주가 데이터 (df_price) 처리
    df_price = None
    if os.path.exists(price_cache_path):
        try:
            df_price = pd.read_csv(price_cache_path, index_col=0, parse_dates=True)
            if isinstance(df_price.columns, pd.MultiIndex):
                df_price.columns = df_price.columns.droplevel(1)
            df_price.index = df_price.index.tz_localize(None)
            
            last_cached_date = df_price.index.max()
            today = datetime.date.today()
            
            if (today - last_cached_date.date()).days >= 1:
                df_recent = yf.download(ticker, period="5d", auto_adjust=False, session=session)
                if not df_recent.empty:
                    if isinstance(df_recent.columns, pd.MultiIndex):
                        df_recent.columns = df_recent.columns.droplevel(1)
                    df_recent.index = df_recent.index.tz_localize(None)
                    
                    df_price = pd.concat([df_price, df_recent])
                    df_price = df_price[~df_price.index.duplicated(keep='last')].sort_index()
                    df_price.to_csv(price_cache_path)
        except Exception:
            df_price = None

    if df_price is None or df_price.empty:
        df_price = yf.download(ticker, period="max", auto_adjust=False, session=session)
        if isinstance(df_price.columns, pd.MultiIndex):
            df_price.columns = df_price.columns.droplevel(1)
        df_price.index = df_price.index.tz_localize(None)
        df_price.to_csv(price_cache_path)

    df_close = df_price['Close'].copy()

    # 2. 배당 데이터 (df_div) 처리
    df_div = None
    if os.path.exists(div_cache_path):
        try:
            file_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(div_cache_path))
            if datetime.datetime.now() - file_mtime < datetime.timedelta(days=3):
                df_div = pd.read_csv(div_cache_path, parse_dates=['Date'])
        except Exception:
            df_div = None

    if df_div is None or df_div.empty:
        df_div = dyf.get_yf_dividend_history(ticker, session=session)
        df_div.to_csv(div_cache_path, index=False)

    df_div_period = dyf.add_period_columns_by_div(df_div)
    df_com = dyf.group_by_period_by_div(df_div_period)
    _, df_stat = dyf.merge_dividend_data(df_close, df_com)
    
    df_stat['Date'] = pd.to_datetime(df_stat['Date']).dt.tz_localize(None)
    
    return df_price, df_stat, df_div_period, df_com
