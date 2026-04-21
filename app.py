from flask import Flask, render_template, request, jsonify, Response, redirect, url_for, flash
import yfinance as yf
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from valuation import calculate_stock_valuation
from calculos import calculate_stock_metrics
from collections import defaultdict
from datetime import datetime
import os
import csv
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

# Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faz login para aceder à app.'
login_manager.login_message_category = 'info'

# Configuração da base de dados
# Render usa "postgres://" mas SQLAlchemy requer "postgresql://"
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///portfolio.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
db = SQLAlchemy(app)

# Modelo de utilizadores
class User(UserMixin, db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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

# Criação da base de dados e utilizador padrão
with app.app_context():
    db.create_all()
    default_user = os.environ.get('ADMIN_USER', 'admin')
    default_pass = os.environ.get('ADMIN_PASS', 'portfolio2026')
    if not User.query.filter_by(username=default_user).first():
        u = User(username=default_user)
        u.set_password(default_pass)
        db.session.add(u)
        try:
            db.session.commit()
            print(f"Utilizador criado: {default_user} / {default_pass}")
        except Exception:
            db.session.rollback()

# ── Autenticação ─────────────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember') == 'on')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        flash('Utilizador ou palavra-passe incorretos.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    old_pw  = request.form.get('old_password', '')
    new_pw  = request.form.get('new_password', '')
    if not current_user.check_password(old_pw):
        flash('Palavra-passe atual incorreta.', 'error')
    elif len(new_pw) < 6:
        flash('A nova palavra-passe deve ter pelo menos 6 caracteres.', 'error')
    else:
        current_user.set_password(new_pw)
        db.session.commit()
        flash('Palavra-passe alterada com sucesso.', 'success')
    return redirect(url_for('index'))

# Rota para a página inicial
@app.route('/')
@login_required
def index():
    return render_template('index.html')

# Rota para a página de portfólio
@app.route('/portfolio')
@login_required
def portfolio():
    return render_template('portfolio.html')

# Rota para a página de análise de ações
@app.route('/stock_analysis')
@login_required
def stock_analysis():
    return render_template('stock_analysis.html')

# Rota para a página de cálculo DCF
@app.route('/dcf')
@login_required
def dcf():
    return render_template('dcf.html')

@app.route('/api/calculate_valuation', methods=['POST'])
def calculate_valuation():
    data = request.json
    ticker = data.get('symbol')
    overrides = {
        'market_return':        data.get('market_return'),
        'growth_rate':          data.get('growth_rate'),
        'terminal_growth_rate': data.get('terminal_growth_rate'),
    }
    # Only pass keys where user provided a value
    overrides = {k: v for k, v in overrides.items() if v is not None}

    try:
        result = calculate_stock_valuation(ticker, **overrides)
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
    return jsonify({'message': 'Ação adicionada com sucesso!', 'id': new_stock.id}), 201

# Rota para atualizar uma ação existente (quando se compra mais do mesmo)
@app.route('/update_stock/<int:stock_id>', methods=['PUT'])
def update_stock(stock_id):
    stock = db.session.get(Stock, stock_id)
    if not stock:
        return jsonify({'error': 'Ação não encontrada.'}), 404
    data = request.json
    if 'quantity' in data:
        stock.quantity = data['quantity']
    if 'purchase_price' in data:
        stock.purchase_price = data['purchase_price']
    db.session.commit()
    return jsonify({'message': 'Ação atualizada com sucesso!'})

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
@login_required
def transactions():
    return render_template('transactions.html')

# Rota para registar uma transação
@app.route('/api/add_transaction', methods=['POST'])
def add_transaction():
    data = request.json
    # Accept optional date for manual entry
    tx_date = datetime.utcnow()
    if data.get('date'):
        try:
            tx_date = datetime.fromisoformat(data['date'])
        except Exception:
            pass
    t = Transaction(
        symbol=data['symbol'].upper(),
        action=data['action'],
        quantity=float(data['quantity']),
        price=float(data['price']),
        total=float(data['quantity']) * float(data['price']),
        date=tx_date
    )
    db.session.add(t)
    db.session.commit()
    return jsonify({'message': 'Transação registada com sucesso!', 'id': t.id}), 201

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
        'date': t.date.strftime('%d/%m/%Y %H:%M'),
        'date_iso': t.date.strftime('%Y-%m-%dT%H:%M:%S')
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

# ── Watchlist ────────────────────────────────────────────────────────────────

class Watchlist(db.Model):
    id     = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), nullable=False, unique=True)
    note   = db.Column(db.String(120), nullable=True)
    added_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

@app.route('/watchlist')
@login_required
def watchlist():
    return render_template('watchlist.html')

@app.route('/api/watchlist', methods=['GET'])
def get_watchlist():
    items = Watchlist.query.order_by(Watchlist.added_at.desc()).all()
    return jsonify([{'id': w.id, 'symbol': w.symbol, 'note': w.note or '',
                     'added_at': w.added_at.strftime('%d/%m/%Y')} for w in items])

@app.route('/api/watchlist', methods=['POST'])
def add_watchlist():
    data   = request.json
    symbol = data.get('symbol', '').upper().strip()
    note   = data.get('note', '').strip()[:120]
    if not symbol:
        return jsonify({'error': 'Símbolo em falta.'}), 400
    if Watchlist.query.filter_by(symbol=symbol).first():
        return jsonify({'error': f'{symbol} já está na watchlist.'}), 409
    db.session.add(Watchlist(symbol=symbol, note=note))
    db.session.commit()
    return jsonify({'message': 'Adicionado.'}), 201

@app.route('/api/watchlist/<int:wid>', methods=['DELETE'])
def delete_watchlist(wid):
    w = db.session.get(Watchlist, wid)
    if not w:
        return jsonify({'error': 'Não encontrado.'}), 404
    db.session.delete(w)
    db.session.commit()
    return jsonify({'message': 'Removido.'})

@app.route('/api/watchlist/prices', methods=['POST'])
def watchlist_prices():
    """Recebe lista de símbolos, devolve preço + variação diária + métricas."""
    symbols = request.json.get('symbols', [])
    result  = {}
    for sym in symbols:
        try:
            tk   = yf.Ticker(sym)
            info = tk.info
            hist = tk.history(period='2d')
            prev  = float(hist['Close'].iloc[-2]) if len(hist) >= 2 else None
            price = float(hist['Close'].iloc[-1]) if not hist.empty else None
            chg_pct = round((price - prev) / prev * 100, 2) if price and prev else None
            result[sym] = {
                'price':        round(price, 2) if price else None,
                'chg_pct':      chg_pct,
                'market_cap':   info.get('marketCap'),
                'pe':           info.get('trailingPE'),
                'week52_high':  info.get('fiftyTwoWeekHigh'),
                'week52_low':   info.get('fiftyTwoWeekLow'),
                'volume':       info.get('regularMarketVolume'),
                'name':         info.get('longName', sym),
            }
        except Exception:
            result[sym] = {'error': True}
    return jsonify(result)

# ── Gráfico Histórico ────────────────────────────────────────────────────────

@app.route('/chart')
@login_required
def chart_page():
    return render_template('chart.html')

@app.route('/api/history', methods=['GET'])
def get_history():
    symbol = request.args.get('symbol', '').upper().strip()
    period = request.args.get('period', '1y')   # 1w 1mo 3mo 6mo 1y 2y 5y
    if not symbol:
        return jsonify({'error': 'Símbolo em falta.'}), 400

    period_map = {
        '1w': '5d', '1mo': '1mo', '3mo': '3mo',
        '6mo': '6mo', '1y': '1y', '2y': '2y', '5y': '5y'
    }
    yf_period = period_map.get(period, '1y')
    interval  = '1d' if period not in ('1w',) else '1h'

    try:
        tk   = yf.Ticker(symbol)
        hist = tk.history(period=yf_period, interval=interval)
        if hist.empty:
            return jsonify({'error': f'Sem dados para {symbol}.'}), 404

        info = tk.info
        closes = hist['Close'].tolist()

        # Médias móveis
        def ma(closes, n):
            result = [None] * len(closes)
            for i in range(n - 1, len(closes)):
                result[i] = round(sum(closes[i - n + 1:i + 1]) / n, 4)
            return result

        dates   = [str(d.date()) if hasattr(d, 'date') else str(d)[:10] for d in hist.index]
        payload = {
            'symbol':   symbol,
            'name':     info.get('longName', symbol),
            'currency': info.get('currency', 'USD'),
            'dates':    dates,
            'close':    [round(float(v), 4) for v in closes],
            'open':     [round(float(v), 4) for v in hist['Open'].tolist()],
            'high':     [round(float(v), 4) for v in hist['High'].tolist()],
            'low':      [round(float(v), 4) for v in hist['Low'].tolist()],
            'volume':   [int(v) for v in hist['Volume'].tolist()],
            'ma50':     ma(closes, 50),
            'ma200':    ma(closes, 200),
            'current_price': info.get('currentPrice') or round(float(closes[-1]), 2),
            'chg':      round((closes[-1] - closes[0]) / closes[0] * 100, 2) if closes[0] else 0,
        }
        return jsonify(payload)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ── Comparador de Ações ──────────────────────────────────────────────────────

@app.route('/comparator')
@login_required
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
@login_required
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

# ── Exportar CSV ─────────────────────────────────────────────────────────────

def make_csv(headers, rows, filename):
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(headers)
    w.writerows(rows)
    return Response(
        out.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.route('/export/portfolio')
def export_portfolio():
    stocks = Stock.query.all()
    headers = ['Símbolo', 'Quantidade', 'Preço Compra', 'Total Investido']
    rows = [(s.symbol, s.quantity, s.purchase_price,
             round(s.quantity * s.purchase_price, 2)) for s in stocks]
    return make_csv(headers, rows, 'portfolio.csv')

@app.route('/export/transactions')
def export_transactions():
    symbol = request.args.get('symbol', '').upper()
    q = Transaction.query
    if symbol:
        q = q.filter_by(symbol=symbol)
    txs = q.order_by(Transaction.date.desc()).all()
    headers = ['Data', 'Ticker', 'Tipo', 'Quantidade', 'Preço', 'Total']
    rows = [(t.date.strftime('%d/%m/%Y %H:%M'), t.symbol, t.action,
             t.quantity, t.price, t.total) for t in txs]
    return make_csv(headers, rows, 'transacoes.csv')

@app.route('/export/watchlist')
def export_watchlist():
    items = Watchlist.query.order_by(Watchlist.added_at.desc()).all()
    headers = ['Ticker', 'Nota', 'Adicionado em']
    rows = [(w.symbol, w.note or '', w.added_at.strftime('%d/%m/%Y')) for w in items]
    return make_csv(headers, rows, 'watchlist.csv')

@app.route('/export/alerts')
def export_alerts():
    alerts = PriceAlert.query.order_by(PriceAlert.created_at.desc()).all()
    headers = ['Ticker', 'Preço Alvo', 'Condição', 'Estado', 'Criado em', 'Disparado em']
    rows = [(a.symbol, a.target_price, a.direction,
             'Activo' if a.active else 'Disparado',
             a.created_at.strftime('%d/%m/%Y %H:%M'),
             a.triggered_at.strftime('%d/%m/%Y %H:%M') if a.triggered_at else '') for a in alerts]
    return make_csv(headers, rows, 'alertas.csv')

# Executa o servidor
if __name__ == '__main__':
    app.run(debug=True)