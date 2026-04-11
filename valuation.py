import yfinance as yf
import numpy as np
from datetime import datetime, timedelta
import pandas as pd
from contextlib import contextmanager
from typing import Optional
import time



def get_yahoo_growth(ticker):
    """
    Obtém a taxa de crescimento projetada a 5 anos da tabela de analistas do Yahoo Finance.

    Args:
        ticker (str): Símbolo da ação.

    Returns:
        Optional[float]: Taxa de crescimento como decimal (e.g., 0.15 para 15%) ou None se não encontrado.
    """
    try:
        tk = yf.Ticker(ticker)

        # Tenta obter estimativa de crescimento a 5 anos dos analistas
        growth_df = tk.growth_estimates
        if growth_df is not None and not growth_df.empty and '+5y' in growth_df.index:
            val = growth_df.loc['+5y']
            # O DataFrame pode ter o ticker como coluna ou uma única coluna
            if hasattr(val, 'iloc'):
                rate = val.iloc[0]
            else:
                rate = float(val)
            if pd.notna(rate):
                print(f"Taxa de crescimento a 5 anos (analistas) para {ticker}: {rate:.2%}")
                return float(rate)

        # Fallback: usa revenueGrowth ou earningsGrowth do info
        info = tk.info
        for key in ('revenueGrowth', 'earningsGrowth', 'earningsQuarterlyGrowth'):
            rate = info.get(key)
            if rate is not None and pd.notna(rate):
                print(f"Taxa de crescimento ({key}) para {ticker}: {rate:.2%}")
                return float(rate)

        print(f"Taxa de crescimento não encontrada para {ticker}.")
        return None

    except Exception as e:
        print(f"Erro ao obter taxa de crescimento para {ticker}: {e}")
        return None

def get_stock_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        financials = stock.financials
        cash_flow = stock.cashflow
        balance_sheet = stock.balance_sheet
        cash_flow_quarterly = stock.quarterly_cashflow
        return stock, info, financials, cash_flow, balance_sheet, cash_flow_quarterly
    except Exception as e:
        print(f"Error obtaining data for ticker {ticker}: {str(e)}")
        return None, None, None, None, None, None

def get_risk_free_rate():
    """
    Retrieve current risk-free rate from 10-year Treasury Note

    Returns:
        float: Risk-free rate or default value
    """
    try:
        tnx = yf.Ticker('^TNX')
        return tnx.info['previousClose'] / 100
    except:
        print("Warning: Could not obtain risk-free rate. Using default value of 2.48%.")
        return 0.0248

def get_market_return():
    """
    Calculate average market return over past 10 years

    Returns:
        float: Average market return or default value
    """
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=10*365)  # Approximately 10 years

        sp500 = yf.Ticker("^GSPC")
        hist = sp500.history(start=start_date, end=end_date)

        annual_returns = hist['Close'].resample('YE').last().pct_change()
        avg_return = annual_returns.mean()
        if pd.isna(avg_return):
            raise ValueError("Calculated return is NaN")
        return avg_return
    except Exception as e:
        print(f"Warning: Could not calculate expected market return. Error: {e}")
        print("Using default value of 10%.")
        return 0.10

def calculate_beta(ticker):
    """
    Retrieve beta value for a given stock ticker

    Args:
        ticker (str): Stock ticker symbol

    Returns:
        float: Beta value or None if not available
    """
    try:
        stock = yf.Ticker(ticker)
        beta = stock.info.get('beta')
        if beta is not None:
            return beta
        else:
            print(f"Warning: Beta not found for {ticker}")
            return None
    except Exception as e:
        print(f"Error retrieving beta for {ticker}: {e}")
        return None

def calculate_ttm_free_cash_flow(cash_flow_quarterly):
    """
    Calculate Trailing Twelve Months (TTM) Free Cash Flow

    Args:
        cash_flow_quarterly (pandas.DataFrame): Quarterly cash flow statement

    Returns:
        float: TTM Free Cash Flow, or None if data is unavailable
    """
    try:
        if 'Free Cash Flow' not in cash_flow_quarterly.index:
            print("Free Cash Flow data not found in quarterly cash flow statement.")
            return None

        quarterly_fcf = cash_flow_quarterly.loc['Free Cash Flow'].head(4)
        if len(quarterly_fcf) < 2:
            print("Insufficient quarterly Free Cash Flow data.")
            return None

        ttm_free_cash_flow = quarterly_fcf.sum()

        print("Quarterly Free Cash Flow:")
        for i, value in enumerate(quarterly_fcf, 1):
            print(f"Q{i}: ${value:,.2f}")
        print(f"TTM Free Cash Flow: ${ttm_free_cash_flow:,.2f}")

        return ttm_free_cash_flow

    except Exception as e:
        print(f"Error calculating TTM Free Cash Flow: {e}")
        return None

def calculate_wacc(info, financials, balance_sheet):
    details = "WACC Calculation:\n"
    try:
        risk_free_rate = get_risk_free_rate()
        details += f"Risk-free rate: {risk_free_rate:.4f}\n"

        beta = calculate_beta(info.get('symbol', ''))
        details += f"Beta: {beta:.4f}\n"

        market_return = get_market_return()
        details += f"Market return: {market_return:.4f}\n"

        cost_of_equity = risk_free_rate + beta * (market_return - risk_free_rate)
        details += f"Cost of equity: {cost_of_equity:.4f}\n\n"

        total_debt = balance_sheet.loc['Total Debt'].iloc[0] if 'Total Debt' in balance_sheet.index else (
            balance_sheet.loc['Long Term Debt'].iloc[0] if 'Long Term Debt' in balance_sheet.index else 0)

        interest_expense = financials.loc['Interest Expense'].iloc[0] if 'Interest Expense' in financials.index else 0

        cost_of_debt = abs(interest_expense) / total_debt if total_debt != 0 else 0.05

        details += f"Total debt: {total_debt:,.2f}\n"
        details += f"Interest expense: {interest_expense:,.2f}\n"
        details += f"Cost of debt: {cost_of_debt:.4f}\n\n"

        income_before_tax = financials.loc['Pretax Income'].iloc[0] if 'Pretax Income' in financials.index else None
        income_tax_expense = financials.loc['Tax Provision'].iloc[0] if 'Tax Provision' in financials.index else None

        if income_before_tax is None or income_tax_expense is None:
            tax_rate = 0.21
        else:
            tax_rate = income_tax_expense / income_before_tax if income_before_tax != 0 else 0.21

        details += f"Income before tax: {income_before_tax:,.2f}\n"
        details += f"Income tax expense: {income_tax_expense:,.2f}\n"
        details += f"Tax rate: {tax_rate:.4f}\n\n"

        market_cap = info.get('marketCap', 0)
        total_capital = market_cap + total_debt

        if total_capital == 0:
            raise ValueError("Total capital is zero")

        equity_weight = market_cap / total_capital
        debt_weight = total_debt / total_capital

        details += f"Market cap: {market_cap:,.2f}\n"
        details += f"Total capital: {total_capital:,.2f}\n"
        details += f"Equity weight: {equity_weight:.4f}\n"
        details += f"Debt weight: {debt_weight:.4f}\n\n"

        wacc = (cost_of_equity * equity_weight) + (cost_of_debt * (1 - tax_rate) * debt_weight)

        details += f"Calculated WACC: {wacc:.4f}\n"

        return wacc, details
    except Exception as e:
        raise ValueError(f"Error calculating WACC: {str(e)}\n\nDetails:\n{details}")

def calculate_intrinsic_value(dcf_value, shares_outstanding):
    if not shares_outstanding:
        return None
    return dcf_value / shares_outstanding

def get_total_stockholder_equity(balance_sheet):
    possible_names = [
        'Total Stockholder Equity',
        'Total Shareholders\' Equity',
        'Stockholders Equity',
        'Shareholders\' Equity',
        'Total Equity'
    ]

    for name in possible_names:
        if name in balance_sheet.index:
            return balance_sheet.loc[name].iloc[0]

    total_assets = balance_sheet.loc['Total Assets'].iloc[0] if 'Total Assets' in balance_sheet.index else None
    total_liabilities = balance_sheet.loc['Total Liabilities'].iloc[0] if 'Total Liabilities' in balance_sheet.index else None

    if total_assets is not None and total_liabilities is not None:
        return total_assets - total_liabilities

    raise ValueError("Could not calculate Total Stockholder Equity")

def get_total_assets(balance_sheet):
    possible_names = ['Total Assets']
    for name in possible_names:
        if name in balance_sheet.index:
            return balance_sheet.loc[name].iloc[0]
    raise ValueError("Could not find Total Assets")

def get_total_liabilities(balance_sheet):
    possible_names = [
        'Total Liabilities Net Minority Interest',
    ]
    for name in possible_names:
        if name in balance_sheet.index:
            return balance_sheet.loc[name].iloc[0]

    current_liabilities = balance_sheet.loc['Total Current Liabilities'].iloc[0] if 'Total Current Liabilities' in balance_sheet.index else 0
    long_term_debt = balance_sheet.loc['Long Term Debt'].iloc[0] if 'Long Term Debt' in balance_sheet.index else 0
    other_long_term_liabilities = balance_sheet.loc['Other Long Term Liabilities'].iloc[0] if 'Other Long Term Liabilities' in balance_sheet.index else 0

    return current_liabilities + long_term_debt + other_long_term_liabilities

def calculate_total_stockholder_equity(balance_sheet):
    try:
        total_assets = get_total_assets(balance_sheet)
        total_liabilities = get_total_liabilities(balance_sheet)

        total_equity = total_assets - total_liabilities

        details = f"Total Stockholder Equity Calculation:\n"
        details += f"Total Assets: {total_assets:,.2f}\n"
        details += f"Total Liabilities: {total_liabilities:,.2f}\n"
        details += f"Total Stockholder Equity: {total_equity:,.2f}\n"

        return total_equity, details
    except Exception as e:
        raise ValueError(f"Error calculating Total Stockholder Equity: {str(e)}")

def print_separator():
    print("______________________________\n")

def print_valuation_comparison(method_name, value, current_price):
    difference = value - current_price
    percentage_difference = (difference / current_price) * 100
    status = "Undervalued" if difference > 0 else "Overvalued"

    print(f"{method_name}: ${value:.2f}")
    print(f"     Difference: ${difference:.2f} ({percentage_difference:.2f}%)")
    print(f"     Status: {status}\n")

def get_quarterly_cash_flow(ticker):
    """
    Get quarterly cash flow data for a ticker
    """
    try:
        stock = yf.Ticker(ticker)
        return stock.quarterly_cashflow
    except Exception as e:
        print(f"Error obtaining quarterly cash flow data for ticker {ticker}: {str(e)}")
        return None

def get_ttm_free_cash_flow(ticker):
    """
    Calculate TTM (Trailing Twelve Months) Free Cash Flow from quarterly data
    """
    details = "TTM Free Cash Flow Calculation:\n"
    try:
        quarterly_cash_flow = get_quarterly_cash_flow(ticker)
        
        if quarterly_cash_flow is None or 'Free Cash Flow' not in quarterly_cash_flow.index:
            raise ValueError("Free Cash Flow data not available")
            
        fcf_data = quarterly_cash_flow.loc['Free Cash Flow']
        if len(fcf_data) < 4:
            raise ValueError("Not enough quarterly data for TTM calculation")
            
        ttm_fcf = fcf_data.head(4).sum()
        
        details += f"Last 4 quarters FCF:\n"
        for i, value in enumerate(fcf_data.head(4)):
            details += f"Quarter {i+1}: ${value:,.2f}\n"
        details += f"\nTTM FCF: ${ttm_fcf:,.2f}\n"
        
        return ttm_fcf, details
    except Exception as e:
        raise ValueError(f"Error calculating TTM FCF: {str(e)}\n\nDetails:\n{details}")

def calculate_dcf(info, financials, ticker, wacc, growth_rate):
    details = "DCF Calculation:\n"
    try:
        current_fcf, ttm_details = get_ttm_free_cash_flow(ticker)
        details += ttm_details + "\n"

        details += f"Using TTM FCF as base: ${current_fcf:,.2f}\n"
        details += f"FCF growth rate: {growth_rate:.4f}\n"

        projected_fcf = []
        for i in range(1, 6):
            fcf = current_fcf * (1 + growth_rate)**i
            projected_fcf.append(fcf)
            details += f"Year {i} projected FCF: ${fcf:,.2f}\n"

        terminal_growth_rate = 0.02
        terminal_value = projected_fcf[-1] * (1 + terminal_growth_rate) / (wacc - terminal_growth_rate)

        dcf_value = sum([cf / (1 + wacc)**(i + 1) for i, cf in enumerate(projected_fcf)]) + terminal_value / (1 + wacc)**5

        details += f"\nTerminal growth rate: {terminal_growth_rate:.4f}\n"
        details += f"Terminal Value: ${terminal_value:,.2f}\n"
        details += f"DCF Value: ${dcf_value:,.2f}\n"

        return dcf_value, terminal_value, projected_fcf, details
    except Exception as e:
        raise ValueError(f"Error calculating DCF: {str(e)}\n\nDetails:\n{details}")

def calculate_stock_valuation(ticker):
    growth = get_yahoo_growth(ticker)
    print(f"Retrieved growth rate for {ticker}: {growth}")
    growth_rate = growth

    stock, info, financials, cash_flow, balance_sheet, cash_flow_quarterly = get_stock_data(ticker)
    
    if growth_rate is None:
        growth_rate = 0.03

    if info is None:
        raise ValueError("Could not retrieve stock data")

    current_price = info.get('currentPrice')
    company_name = info.get('longName')
    shares_outstanding = info.get('sharesOutstanding')

    wacc, wacc_details = calculate_wacc(info, financials, balance_sheet)
    dcf_value, terminal_value, projected_fcf, dcf_details = calculate_dcf(info, financials, ticker, wacc, growth_rate)
    dcf_value_per_share = calculate_intrinsic_value(dcf_value, shares_outstanding)

    cash_flow_projections = "\n".join([f"Year {i+1}: ${fcf:,.2f}" for i, fcf in enumerate(projected_fcf)])

    return {
        "company_name": company_name,
        "current_price": current_price,
        "dcf_value_per_share": dcf_value_per_share,
        "wacc": wacc,
        "growth_rate": growth_rate,
        "terminal_growth_rate": 0.02,
        "terminal_value": terminal_value,
        "cash_flow_projections": cash_flow_projections,
        "dcf_details": dcf_details,
        "wacc_details": wacc_details
    }