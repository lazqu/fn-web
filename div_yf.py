import pandas as pd
import yfinance as yf
import requests

def get_yf_session():
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    return session

def get_yf_dividend_history(ticker, session=None):
    if session is None:
        session = get_yf_session()
    Ticker = yf.Ticker(ticker, session=session)
    df_div_period = Ticker.dividends.reset_index()
    df_div_period['Date'] = pd.to_datetime(df_div_period['Date'].dt.date)
    return df_div_period

def add_period_columns_by_div(df):
    # df_temp = df.sort_index().reset_index()
    df['period'] = (df['Dividends'] != df['Dividends'].shift()).cumsum() - 1
    return df

def group_by_period_by_div(df, sum_frequency=4):
    df_com = df.groupby('period').agg(
            start_date=("Date", "min"),
            end_date=("Date", "max"),
            dividend_mean=("Dividends", "mean"),
            dividend_sum=("Dividends", "sum"),
            count=("Date", "count"))
    # $$$ 1년 기준으로 통일시켜줘야함
    # df_com['adj_div'] = df_com['dividend_mean'] * df_com['count'].mode()[0]
    df_com['adj_div'] = df_com['dividend_mean'] * sum_frequency
    df_com['div_change'] = df_com['adj_div'].pct_change()
    return df_com.reset_index()

def merge_dividend_data(df_price, df_com):
    # df_price가 Series일 경우 안전하게 DataFrame으로 변환 (캐시 파일 로드 시 발생 대응)
    if isinstance(df_price, pd.Series):
        name = df_price.name if df_price.name else 'Close'
        df_price = df_price.to_frame(name=name)

    ticker = df_price.columns[0]

    # 각 배당 주기에 대하여, 시작 날짜의 다음날부터 다음 주기의 시작 날짜까지, adj_div 를 기입
    df_merge = pd.merge(df_price.reset_index(), df_com, left_on='Date', right_on='start_date', how='outer')
    cols = ['period', 'start_date', 'end_date', 'dividend_mean', 'dividend_sum', 'count', 'adj_div', 'div_change']
    df_merge.loc[:, cols] = df_merge.loc[:, cols].shift(1).ffill()
    df_merge.dropna(subset=[ticker, "period"], inplace=True)
    df_merge['dfs'] = df_merge['adj_div'] / df_merge[ticker]


    # dfs_agg: 기간별 통계 집계
    dfs_agg = df_merge.groupby('period').agg(
        date_s=('Date', 'min'),
        date_e=('Date', 'max'),
        div=('adj_div', 'mean'),
        pr_min=(ticker, 'min'),
        pr_max=(ticker, 'max'),
        dfs_min=('dfs', 'min'),
        dfs_max=('dfs', 'max'),)

    # 다시 정보 취합
    df_left = df_merge[['Date', ticker, 'period', 'start_date', 'end_date', 'adj_div', 'dfs', 'div_change']].reset_index(drop=True)
    df_right = dfs_agg.shift(1).loc[df_merge['period']].reset_index(drop=True)
    df_stat = pd.concat([df_left, df_right], axis=1)

    return dfs_agg, df_stat


def get_div_data(ticker: str, df_close: pd.DataFrame):
    """
    배당 데이터를 가져와 분석 및 통계 가공을 거쳐 결합 데이터를 생성하는 파이프라인 함수입니다.
    """
    # 배당금 지급 내역 가져오기
    df_div_period = get_yf_dividend_history(ticker)
    # 배당급 집계
    add_period_columns_by_div(df_div_period)
    df_com = group_by_period_by_div(df_div_period)

    dfs_agg, df_stat = merge_dividend_data(df_close, df_com)
    return dfs_agg, df_stat


if __name__ == "__main__":
    ticker_test = "AAPL"
    print(f"🚀 {ticker_test} 배당 파이프라인 가공 테스트 시작...")
    try:
        # 테스트용 가격 데이터 가져오기
        df_price = yf.download(ticker_test, period="2y", interval="1d")["Close"]
        if not df_price.empty:
            dfs_agg, df_stat = get_div_data(ticker_test, df_price)
            print("\n=== [1] dfs_agg (기간별 배당 통계 요약) ===")
            print(dfs_agg.head(5))
            print("\n=== [2] df_stat (상세 결합 테이블) ===")
            print(df_stat.head(5))
            print("\n✅ 배당 파이프라인 연산 테스트 완료!")
        else:
            print("❌ 가격 데이터를 불러오지 못했습니다.")
    except Exception as e:
        print(f"❌ 연산 중 에러 발생: {e}")