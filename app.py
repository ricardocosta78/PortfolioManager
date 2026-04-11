from flask import Flask, render_template, request, jsonify
import yfinance as yf
from flask_sqlalchemy import SQLAlchemy
from valuation import calculate_stock_valuation
from calculos import calculate_stock_metrics
from collections import defaultdict
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Configuração da base de dados
# Render usa "postgres://" mas SQLAlchemy requer "postgresql://"
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
db = SQLAlchemy(app)

# Modelo da tabela de portfólio
class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    purchase_price = db.Column(db.Float, nullable=False)

# Modelo de alertas de preço
class PriceAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    target_price = db.Column(db.Float, nullable=False)
    direction = db.Column(db.String(5), nullable=False)  # 'above' or 'below'
    active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    triggered_at = db.Column(db.DateTime, nullable=True)

# Modelo do histórico de transações
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False)
    action = db.Column(db.String(10), nullable=False)  # 'compra' ou 'venda'
    quantity = db.Column(db.Float, nullable=False)
    price = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# Criação da base de dados
with app.app_context():
    db.create_all()

# Rota para a página inicial
@app.route('/')
def index():
    return render_template('index.html')

# Rota para a página de portfólio
@app.route('/portfolio')
def portfolio():
    return render_template('portfolio.html')

# Rota para a página de análise de ações
@app.route('/stock_analysis')
def stock_analysis():
    return render_template('stock_analysis.html')

# Rota para a página de cálculo DCF
@app.route('/dcf')
def dcf():
    return render_template('dcf.html')

@app.route('/api/calculate_valuation', methods=['POST'])
def calculate_valuation():
    data = request.json
    ticker = data.get('symbol')
    
    try:
        result = calculate_stock_valuation(ticker)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Rota para obter o preço da ação
@app.route('/get_price', methods=['POST'])
def get_price():
    symbol = request.json['symbol']
    
    try:
        stock = yf.Ticker(symbol)
        price = stock.history(period='1d')['Close'].iloc[-1]  # Preço de fechamento do último dia
        return jsonify({'price': price})
    except IndexError:
        return jsonify({'error': 'Não foi possível obter o preço. Verifica o símbolo da ação.'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Rota para adicionar uma ação ao portfólio
@app.route('/add_stock', methods=['POST'])
def add_stock():
    data = request.json
    new_stock = Stock(symbol=data['symbol'], quantity=data['quantity'], purchase_price=data['purchase_price'])
    db.session.add(new_stock)
    db.session.commit()
    return jsonify({'message': 'Ação adicionada com sucesso!'}), 201

# Rota para remover uma ação do portfólio
@app.route('/remove_stock/<int:stock_id>', methods=['DELETE'])
def remove_stock(stock_id):
    stock_to_remove = db.session.get(Stock, stock_id)
    if stock_to_remove:
        db.session.delete(stock_to_remove)
        db.session.commit()
        return jsonify({'message': 'Ação removida com sucesso!'}), 200
    return jsonify({'error': 'Ação não encontrada.'}), 404

# Nova rota para obter o portfólio completo
@app.route('/get_portfolio', methods=['GET'])
def get_portfolio():
    stocks = Stock.query.all()
    portfolio = []
    for stock in stocks:
        portfolio.append({
            'id': stock.id,
            'symbol': stock.symbol,
            'quantity': stock.quantity,
            'purchase_price': stock.purchase_price
        })
    return jsonify(portfolio)

def format_percentage(value):
    if isinstance(value, (int, float)):
        return f"{value * 100:.2f}%".replace('.', ',')
    return value

def format_number(value):
    if isinstance(value, (int, float)):
        return f"${value:,}".replace(',', ' ')
    return value

# Rota para obter informações do estoque
@app.route('/stock_analysis', methods=['POST'])
def stock_info():
    data = request.get_json()
    symbol = data.get('symbol').upper()
    
    try:
        stock_data = calculate_stock_metrics(symbol)
        return jsonify(stock_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/portfolio_summary', methods=['GET'])
def portfolio_summary():
    stocks = Stock.query.all()
    if not stocks:
        return jsonify({
            'total_invested': 0, 'current_value': 0,
            'profit_loss': 0, 'profit_loss_pct': 0, 'stocks': []
        })

    # Agrupar por símbolo (pode haver entradas duplicadas na DB)
    grouped = defaultdict(lambda: {'quantity': 0, 'total_cost': 0})
    for stock in stocks:
        grouped[stock.symbol]['quantity'] += stock.quantity
        grouped[stock.symbol]['total_cost'] += stock.quantity * stock.purchase_price

    # Buscar preços atuais
    prices = {}
    for sym in grouped:
        try:
            hist = yf.Ticker(sym).history(period='5d')
            prices[sym] = float(hist['Close'].iloc[-1]) if not hist.empty else None
        except Exception:
            prices[sym] = None

    stock_list = []
    total_invested = 0
    current_value = 0

    for sym, data in grouped.items():
        avg_price = data['total_cost'] / data['quantity'] if data['quantity'] else 0
        invested = data['total_cost']
        price = prices.get(sym)
        cur = data['quantity'] * price if price else None
        pl = cur - invested if cur is not None else None
        pl_pct = (pl / invested * 100) if pl is not None and invested else None

        total_invested += invested
        if cur is not None:
            current_value += cur

        stock_list.append({
            'symbol': sym,
            'quantity': data['quantity'],
            'avg_price': round(avg_price, 2),
            'current_price': round(price, 2) if price else None,
            'invested': round(invested, 2),
            'current_value': round(cur, 2) if cur is not None else None,
            'profit_loss': round(pl, 2) if pl is not None else None,
            'profit_loss_pct': round(pl_pct, 2) if pl_pct is not None else None,
        })

    profit_loss = current_value - total_invested
    profit_loss_pct = (profit_loss / total_invested * 100) if total_invested > 0 else 0

    # Ordenar por % lucro/perda
    stock_list.sort(key=lambda x: x['profit_loss_pct'] if x['profit_loss_pct'] is not None else 0, reverse=True)

    return jsonify({
        'total_invested': round(total_invested, 2),
        'current_value': round(current_value, 2),
        'profit_loss': round(profit_loss, 2),
        'profit_loss_pct': round(profit_loss_pct, 2),
        'stocks': stock_list
    })

# Rota para a página de histórico
@app.route('/transactions')
def transactions():
    return render_template('transactions.html')

# Rota para registar uma transação
@app.route('/api/add_transaction', methods=['POST'])
def add_transaction():
    data = request.json
    t = Transaction(
        symbol=data['symbol'].upper(),
        action=data['action'],
        quantity=data['quantity'],
        price=data['price'],
        total=data['quantity'] * data['price']
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({'message': 'Transação registada com sucesso!'}), 201

# Rota para obter todas as transações
@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    symbol = request.args.get('symbol', '').upper()
    query = Transaction.query
    if symbol:
        query = query.filter_by(symbol=symbol)
    txs = query.order_by(Transaction.date.desc()).all()
    return jsonify([{
        'id': t.id,
        'symbol': t.symbol,
        'action': t.action,
        'quantity': t.quantity,
        'price': t.price,
        'total': t.total,
        'date': t.date.strftime('%d/%m/%Y %H:%M')
    } for t in txs])

# Rota para apagar uma transação
@app.route('/api/transactions/<int:tx_id>', methods=['DELETE'])
def delete_transaction(tx_id):
    t = db.session.get(Transaction, tx_id)
    if t:
        db.session.delete(t)
        db.session.commit()
        return jsonify({'message': 'Transação removida.'}), 200
    return jsonify({'error': 'Transação não encontrada.'}), 404

# ── Comparador de Ações ──────────────────────────────────────────────────────

@app.route('/comparator')
def comparator():
    return render_template('comparator.html')

@app.route('/api/compare', methods=['POST'])
def compare_stocks():
    symbols = request.json.get('symbols', [])
    symbols = [s.upper().strip() for s in symbols if s.strip()][:4]
    if not symbols:
        return jsonify({'error': 'Sem símbolos.'}), 400

    results = []
    for sym in symbols:
        try:
            tk = yf.Ticker(sym)
            info = tk.info
            hist = tk.history(period='1y')

            def g(key, default=None):
                v = info.get(key)
                return v if v is not None else default

            # Variação 1 ano
            chg_1y = None
            if len(hist) >= 2:
                start = float(hist['Close'].iloc[0])
                end   = float(hist['Close'].iloc[-1])
                chg_1y = round((end - start) / start * 100, 2) if start else None

            results.append({
                'symbol':          sym,
                'name':            g('longName', sym),
                'price':           g('currentPrice') or g('regularMarketPrice'),
                'market_cap':      g('marketCap'),
                'pe':              g('trailingPE'),
                'forward_pe':      g('forwardPE'),
                'pb':              g('priceToBook'),
                'ps':              g('priceToSalesTrailing12Months'),
                'peg':             g('trailingPegRatio') or g('pegRatio'),
                'eps':             g('trailingEps'),
                'roe':             g('returnOnEquity'),
                'roa':             g('returnOnAssets'),
                'profit_margin':   g('profitMargins'),
                'gross_margin':    g('grossMargins'),
                'op_margin':       g('operatingMargins'),
                'revenue_growth':  g('revenueGrowth'),
                'earnings_growth': g('earningsGrowth'),
                'dividend_yield':  g('dividendYield'),
                'beta':            g('beta'),
                'week52_high':     g('fiftyTwoWeekHigh'),
                'week52_low':      g('fiftyTwoWeekLow'),
                'debt_to_equity':  g('debtToEquity'),
                'current_ratio':   g('currentRatio'),
                'chg_1y':          chg_1y,
            })
        except Exception as e:
            results.append({'symbol': sym, 'error': str(e)})

    return jsonify(results)

# ── Alertas de Preço ──────────────────────────────────────────────────────────

@app.route('/alerts')
def alerts():
    return render_template('alerts.html')

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    alerts_list = PriceAlert.query.order_by(PriceAlert.active.desc(), PriceAlert.created_at.desc()).all()
    return jsonify([{
        'id': a.id,
        'symbol': a.symbol,
        'target_price': a.target_price,
        'direction': a.direction,
        'active': a.active,
        'created_at': a.created_at.strftime('%d/%m/%Y %H:%M'),
        'triggered_at': a.triggered_at.strftime('%d/%m/%Y %H:%M') if a.triggered_at else None
    } for a in alerts_list])

@app.route('/api/alerts', methods=['POST'])
def add_alert():
    data = request.json
    symbol = data.get('symbol', '').upper().strip()
    target_price = data.get('target_price')
    direction = data.get('direction')  # 'above' or 'below'

    if not symbol or target_price is None or direction not in ('above', 'below'):
        return jsonify({'error': 'Dados inválidos.'}), 400

    alert = PriceAlert(symbol=symbol, target_price=float(target_price), direction=direction)
    db.session.add(alert)
    db.session.commit()
    return jsonify({'message': 'Alerta criado.', 'id': alert.id}), 201

@app.route('/api/alerts/<int:alert_id>', methods=['DELETE'])
def delete_alert(alert_id):
    alert = db.session.get(PriceAlert, alert_id)
    if alert:
        db.session.delete(alert)
        db.session.commit()
        return jsonify({'message': 'Alerta removido.'}), 200
    return jsonify({'error': 'Alerta não encontrado.'}), 404

@app.route('/api/alerts/check', methods=['GET'])
def check_alerts():
    """Verifica alertas activos contra preços actuais. Marca os disparados."""
    active_alerts = PriceAlert.query.filter_by(active=True).all()
    if not active_alerts:
        return jsonify([])

    # Buscar preços únicos
    symbols = list({a.symbol for a in active_alerts})
    prices = {}
    for sym in symbols:
        try:
            hist = yf.Ticker(sym).history(period='1d')
            prices[sym] = float(hist['Close'].iloc[-1]) if not hist.empty else None
        except Exception:
            prices[sym] = None

    triggered = []
    for a in active_alerts:
        price = prices.get(a.symbol)
        if price is None:
            continue
        hit = (a.direction == 'above' and price >= a.target_price) or \
              (a.direction == 'below' and price <= a.target_price)
        if hit:
            a.active = False
            a.triggered_at = datetime.utcnow()
            triggered.append({
                'id': a.id,
                'symbol': a.symbol,
                'target_price': a.target_price,
                'direction': a.direction,
                'current_price': round(price, 2)
            })

    if triggered:
        db.session.commit()

    return jsonify(triggered)

# Executa o servidor
if __name__ == '__main__':
    app.run(debug=True)