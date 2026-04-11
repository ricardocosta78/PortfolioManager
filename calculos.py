import yfinance as yf

def calculate_springate_score(working_capital, total_assets, ebit, profit_before_tax, current_liabilities, revenue):
    try:
        A = working_capital / total_assets
        B = ebit / total_assets
        C = profit_before_tax / current_liabilities
        D = revenue / total_assets
        return 1.03 * A + 3.07 * B + 0.66 * C + 0.4 * D
    except Exception as e:
        print(f"Error calculating Springate score: {e}")
        return None

def format_number(value):
    if isinstance(value, (int, float)):
        if value >= 1_000_000_000:
            return f"{value/1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value/1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value/1_000:.2f}K"
        else:
            return f"{value:.2f}"
    return value

def format_percentage(value):
    if isinstance(value, (int, float)):
        return f"{value*100:.2f}%"
    return value

def calculate_stock_metrics(symbol):
    stock = yf.Ticker(symbol)
    info = stock.info
    fs = stock.financials.T
    fb = stock.balance_sheet.T
    fc = stock.cashflow.T

    # Basic financial metrics
    ebit = fs['EBIT'].iloc[0]
    operating_income = fs['Operating Income'].iloc[0]
    net_income = fs['Net Income'].iloc[0]
    totalAssets = fb['Total Assets'].iloc[0]
    currentLiab = fb['Current Liabilities'].iloc[0]
    totalLiabInt = fb['Total Liabilities Net Minority Interest'].iloc[0]
    currentAssets = fb['Current Assets'].iloc[0]
    invested_capital = totalAssets - currentLiab
    fcfoa = fc['Cash Flow From Continuing Operating Activities'].iloc[0]
    fcfia = fc['Cash Flow From Continuing Investing Activities'].iloc[0]
    working_capital=currentAssets-currentLiab
    # Get profit before tax
    profit_before_tax = fs['Pretax Income'].iloc[0]
    
    # Calculate Springate Score
    springate = calculate_springate_score(
        working_capital,
        totalAssets,
        ebit,
        profit_before_tax,
        currentLiab,
        fs['Total Revenue'].iloc[0]
    )



    roce = ebit / (totalAssets - currentLiab)
    roic = (operating_income * (1 - (ebit - net_income) / ebit)) / invested_capital
    Zmijewski = -4.336 - 4.513 * (net_income/totalAssets) + 5.679 * (totalLiabInt/totalAssets) + 0.004 * (currentAssets/currentLiab)
    sloan = (net_income-fcfoa-fcfia)/totalAssets
    tobinQ = info.get('marketCap')/totalAssets
    # M-Score components
    sales_t = fs['Total Revenue'].iloc[0]
    sales_t_1 = fs['Total Revenue'].iloc[1]
    cogs_t = fs['Cost Of Revenue'].iloc[0]
    cogs_t_1 = fs['Cost Of Revenue'].iloc[1]
    receivables_t = fb['Accounts Receivable'].iloc[0] if 'Accounts Receivable' in fb else 0
    receivables_t_1 = fb['Accounts Receivable'].iloc[1] if 'Accounts Receivable' in fb else 0
    current_assets_t = fb['Current Assets'].iloc[0]
    current_assets_t_1 = fb['Current Assets'].iloc[1]
    ppe_t = fb['Gross PPE'].iloc[0]
    ppe_t_1 = fb['Gross PPE'].iloc[1]
    securities_t = fs['Gain Loss On Investment Securities'].iloc[0] if 'Gain Loss On Investment Securities' in fs else 0
    securities_t_1 = fs['Gain Loss On Investment Securities'].iloc[1] if 'Gain Loss On Investment Securities' in fs else 0
    total_assets_t = fb['Total Assets'].iloc[0]
    total_assets_t_1 = fb['Total Assets'].iloc[1]
    depreciation_t = fc['Depreciation And Amortization'].iloc[0]
    depreciation_t_1 = fc['Depreciation And Amortization'].iloc[1]
    sg_and_a_t = fs['Selling General And Administration'].iloc[0]
    sg_and_a_t_1 = fs['Selling General And Administration'].iloc[1]
    current_liabilities_t = fb['Current Liabilities'].iloc[0]
    current_liabilities_t_1 = fb['Current Liabilities'].iloc[1]
    total_debt_t = fb['Long Term Debt'].iloc[0]
    total_debt_t_1 = fb['Long Term Debt'].iloc[1]
    income_from_operations_t = fs['Operating Income'].iloc[0]
    cash_flow_operations_t = fc['Cash Flow From Continuing Operating Activities'].iloc[0]

    # Calculate M-Score components
    DSRI = (receivables_t / sales_t) / (receivables_t_1 / sales_t_1)
    GMI = ((sales_t_1 - cogs_t_1) / sales_t_1) / ((sales_t - cogs_t) / sales_t)
    AQI = (1 - (current_assets_t + ppe_t + securities_t) / total_assets_t) / (1 - (current_assets_t_1 + ppe_t_1 + securities_t_1) / total_assets_t_1)
    SGI = sales_t / sales_t_1
    DEPI = (depreciation_t_1 / (ppe_t_1 + depreciation_t_1)) / (depreciation_t / (ppe_t + depreciation_t))
    SGAI = (sg_and_a_t / sales_t) / (sg_and_a_t_1 / sales_t_1)
    LVGI = ((current_liabilities_t + total_debt_t) / total_assets_t) / ((current_liabilities_t_1 + total_debt_t_1) / total_assets_t_1)
    TATA = (income_from_operations_t - cash_flow_operations_t) / total_assets_t
    mscore = -4.840 + 0.920 * DSRI + 0.528 * GMI + 0.404 * AQI + 0.892 * SGI + 0.115 * DEPI - 0.172 * SGAI - 0.327 * LVGI + 4.697 * TATA

    # Calculate book value per share
    total_stockholder_equity = fb['Stockholders Equity'].iloc[0] if 'Stockholders Equity' in fb else fb['Total Stockholder Equity'].iloc[0]
    shares = info.get('sharesOutstanding')
    bookvalueShare = total_stockholder_equity / shares if shares else 0

    data = stock.history(period="1y")
    
    # Calculate RSI manually
    def calculate_rsi(prices, period=14):
        deltas = prices.diff()
        gain = deltas.clip(lower=0)
        loss = -deltas.clip(upper=0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    # Calculate SMAs
    data['SMA_50'] = data['Close'].rolling(window=50).mean()
    data['SMA_200'] = data['Close'].rolling(window=200).mean()
    
    # Calculate EMAs and MACD manually
    def calculate_ema(prices, period):
        multiplier = 2 / (period + 1)
        return prices.ewm(span=period, adjust=False).mean()
    
    data['EMA_12'] = calculate_ema(data['Close'], 12)
    data['EMA_26'] = calculate_ema(data['Close'], 26)
    data['MACD_Line'] = data['EMA_12'] - data['EMA_26']
    data['Signal_Line'] = calculate_ema(data['MACD_Line'], 9)
    
    # Calculate RSI
    data['RSI'] = calculate_rsi(data['Close'])
    
    # Calculate Kairi Relative Index
    data['SMA_25'] = data['Close'].rolling(window=25).mean()
    data['Kairi'] = ((data['Close'] - data['SMA_25']) / data['SMA_25']) * 100

   
    rsi= data['RSI'].iloc[-1]
    sma50= data['SMA_50'].iloc[-1]
    sma200= data['SMA_200'].iloc[-1]
    macd= data['MACD_Line'].iloc[-1]
    signal= data['Signal_Line'].iloc[-1]
    kairi= data['Kairi'].iloc[-1]
    current_price= data['Close'].iloc[-1]
    dividendRate = info.get('dividendYield') or 0
    print(f'o Dividendo é {dividendRate}')
    return {
        'sector': info.get('sector', 'N/A'),
        'industry': info.get('industry', 'N/A'),
        'shortName': info.get('shortName', 'N/A'),
        'country': info.get('country', 'N/A'),
        'price': format_number(info.get('currentPrice', 'N/A')),
        'marketCap': format_number(info.get('marketCap')),
        'enterpriseValue': format_number(info.get('enterpriseValue', 'N/A')),
        'targetMedianPrice': format_number(info.get('targetMedianPrice', 'N/A')),
        'currentPrice': info.get('currentPrice', 'N/A'),
        'recommendationKey': info.get('recommendationKey', 'N/A'),
        'recommendationMean': info.get('recommendationMean', 'N/A'),
        'totalRevenue': format_number(info.get('totalRevenue', 'N/A')),
        'netIncomeToCommon': format_number(info.get('netIncomeToCommon', 'N/A')),
        'revenueGrowth': format_percentage(info.get('revenueGrowth', 'N/A')),
        'trailingEps': info.get('trailingEps', 'N/A'),
        'fcfGrowth': format_percentage(info.get('freeCashflowGrowth', 'N/A')),
        'forwardEps': info.get('forwardEps', 'N/A'),
        'trailingPE': info.get('trailingPE', 'N/A'),
        'forwardPE': info.get('forwardPE', 'N/A'),
        'enterpriseToEbitda': info.get('enterpriseToEbitda', 'N/A'),
        'pegRatio': info.get('trailingPegRatio') or info.get('pegRatio', 'N/A'),
        'dividendRate': format_percentage(dividendRate),
        'beta': info.get('beta', 'N/A'),
        'totalCash': format_number(info.get('totalCash', 'N/A')),
        'totalDebt': format_number(info.get('totalDebt', 'N/A')),
        'sharesOutstanding': format_number(info.get('sharesOutstanding', 'N/A')),
        'freeCashflow': format_number(info.get('freeCashflow', 'N/A')),
        'earningsGrowth': format_percentage(info.get('earningsGrowth', 'N/A')),
        'roe': format_percentage(info.get('returnOnEquity', 'N/A')),
        'roa': format_percentage(info.get('returnOnAssets', 'N/A')),
        'roic': format_percentage(roic),
        'roce': format_percentage(roce),
        'grossMargin': format_percentage(info.get('grossMargins', 'N/A')),
        'operatingMargins': format_percentage(info.get('operatingMargins', 'N/A')),
        'profitMargins': format_percentage(info.get('profitMargins', 'N/A')),
        'effectiveTaxRate': info.get('effectiveTaxRate', 'N/A'),
        'currentRatio': info.get('currentRatio', 'N/A'),
        'debtToEquity': info.get('debtToEquity', 'N/A'),
        'interestCoverage': info.get('interestCoverage', 'N/A'),
        'quickRatio': info.get('quickRatio', 'N/A'),
        'ebitdaMargins': format_percentage(info.get('ebitdaMargins', 'N/A')),
        'bookValue': bookvalueShare,
        'zmij': Zmijewski,
        'sloan': sloan,
        'tobinQ': tobinQ,
        'mscore': mscore,
        'springate': springate, 
        'rsi':rsi,
        'macd':macd,
        'sma50':sma50,
        'sma200':sma200,
        'kairi':kairi,
        'signal':signal

    }