// ── State ────────────────────────────────────────────────────────────────────
let _sellRow = null; // row being sold

// ── Formatters ───────────────────────────────────────────────────────────────
function fmtMoney(v) {
    return '$' + Math.abs(v).toLocaleString('pt-PT', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}
function sign(v) { return v >= 0 ? '+' : '-'; }

// ── Summary KPI cards ─────────────────────────────────────────────────────────
function updateSummaryCards() {
    const rows = Array.from(document.querySelectorAll('#portfolioBody tr[data-id]'));

    let totalInvested = 0, totalCurrent = 0;
    rows.forEach(row => {
        const qty          = parseFloat(row.cells[1].textContent) || 0;
        const currentPrice = parseFloat(row.cells[3].textContent);
        const invested     = parseFloat(row.cells[4].textContent) || 0;
        totalInvested += invested;
        if (!isNaN(currentPrice)) totalCurrent += qty * currentPrice;
    });

    const pl  = totalCurrent - totalInvested;
    const pct = totalInvested > 0 ? (pl / totalInvested * 100) : 0;

    document.getElementById('kpiInvested').textContent = fmtMoney(totalInvested);
    document.getElementById('kpiCurrent').textContent  = fmtMoney(totalCurrent);

    const plEl = document.getElementById('kpiPL');
    plEl.textContent = sign(pl) + fmtMoney(pl);
    plEl.className   = 'kpi-value ' + (pl >= 0 ? 'pos' : 'neg');

    const pctEl = document.getElementById('kpiPct');
    pctEl.textContent = sign(pct) + Math.abs(pct).toFixed(2) + '%';
    pctEl.className   = 'kpi-value ' + (pct >= 0 ? 'pos' : 'neg');
}

// ── Portfolio percentages (P/L + % Port.) ────────────────────────────────────
function updatePortfolioPercentages() {
    const rows = Array.from(document.querySelectorAll('#portfolioBody tr[data-id]'));

    const totalInvestment = rows.reduce((acc, row) => {
        return acc + (parseFloat(row.cells[4].textContent) || 0);
    }, 0);

    rows.forEach(row => {
        const qty          = parseFloat(row.cells[1].textContent) || 0;
        const currentPrice = parseFloat(row.cells[3].textContent);
        const invested     = parseFloat(row.cells[4].textContent) || 0;

        if (isNaN(currentPrice)) {
            row.cells[5].textContent = '—';
            row.cells[6].textContent = '—';
        } else {
            const currentValue = qty * currentPrice;
            const pl           = currentValue - invested;
            const plPct        = invested > 0 ? (pl / invested * 100) : 0;
            row.cells[5].innerHTML = `<span class="${pl >= 0 ? 'pos' : 'neg'}">${pl >= 0 ? '+' : ''}${pl.toFixed(2)}</span>`;
            row.cells[6].innerHTML = `<span class="${plPct >= 0 ? 'pos' : 'neg'}">${plPct >= 0 ? '+' : ''}${plPct.toFixed(2)}%</span>`;
        }

        const portPct = totalInvestment > 0 ? (invested / totalInvestment * 100) : 0;
        row.cells[7].textContent = portPct.toFixed(2) + '%';
    });

    updateSummaryCards();
    updateChartFromTable();
}

// ── Modal helpers ─────────────────────────────────────────────────────────────
function openModal(id)  { document.getElementById(id).style.display = 'flex'; }
function closeModal(id) { document.getElementById(id).style.display = 'none'; }

// ── Add Stock modal ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Open modal
    document.getElementById('btnAddStock').addEventListener('click', () => {
        document.getElementById('mSym').value   = '';
        document.getElementById('mQty').value   = '';
        document.getElementById('mPrice').value = '';
        document.getElementById('mPriceHint').textContent = '';
        openModal('modalAdd');
        document.getElementById('mSym').focus();
    });

    // Ticker → fetch current price on Enter, move to qty
    document.getElementById('mSym').addEventListener('keydown', async e => {
        if (e.key !== 'Enter') return;
        const sym = document.getElementById('mSym').value.trim().toUpperCase();
        if (!sym) return;
        document.getElementById('mSym').value = sym;
        const hint = document.getElementById('mPriceHint');
        hint.textContent = 'A obter preço atual...';
        try {
            const r = await fetch('/get_price', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({symbol: sym})
            });
            const d = await r.json();
            if (d.price) {
                const p = parseFloat(d.price).toFixed(2);
                hint.textContent = `Preço atual: $${p}`;
                document.getElementById('mPrice').value = p;
            } else {
                hint.textContent = d.error || 'Preço não disponível';
            }
        } catch {
            hint.textContent = 'Erro ao obter preço';
        }
        document.getElementById('mQty').focus();
    });

    document.getElementById('mQty').addEventListener('keydown', e => {
        if (e.key === 'Enter') document.getElementById('mPrice').focus();
    });
    document.getElementById('mPrice').addEventListener('keydown', e => {
        if (e.key === 'Enter') confirmAddStock();
    });

    // Sell modal key nav
    document.getElementById('sQty').addEventListener('keydown', e => {
        if (e.key === 'Enter') document.getElementById('sPrice').focus();
    });
    document.getElementById('sPrice').addEventListener('keydown', e => {
        if (e.key === 'Enter') confirmSell();
    });

    // Close modals on overlay click
    document.getElementById('modalAdd').addEventListener('click', e => {
        if (e.target === e.currentTarget) closeModal('modalAdd');
    });
    document.getElementById('modalSell').addEventListener('click', e => {
        if (e.target === e.currentTarget) closeModal('modalSell');
    });

    loadPortfolio();
    checkPriceAlerts();
});

async function confirmAddStock() {
    const symbol       = document.getElementById('mSym').value.trim().toUpperCase();
    const quantity     = parseFloat(document.getElementById('mQty').value);
    const purchasePrice = parseFloat(document.getElementById('mPrice').value);

    if (!symbol)                             { alert('Introduz o ticker.');       return; }
    if (isNaN(quantity) || quantity <= 0)    { alert('Quantidade inválida.');      return; }
    if (isNaN(purchasePrice) || purchasePrice <= 0) { alert('Preço inválido.'); return; }

    // Fetch current price for display (best-effort)
    let currentPrice = purchasePrice;
    try {
        const r = await fetch('/get_price', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({symbol})
        });
        const d = await r.json();
        if (d.price) currentPrice = parseFloat(d.price);
    } catch { /* use purchase price as fallback */ }

    const tbody = document.getElementById('portfolioBody');
    const existingRow = Array.from(tbody.querySelectorAll('tr[data-id]'))
        .find(r => r.cells[0].textContent.trim() === symbol);

    if (existingRow) {
        // Update existing position
        const existingQty   = parseFloat(existingRow.cells[1].textContent);
        const existingTotal = parseFloat(existingRow.cells[4].textContent);
        const newQty        = existingQty + quantity;
        const newTotal      = existingTotal + (quantity * purchasePrice);
        const newAvgPrice   = newTotal / newQty;

        existingRow.cells[1].textContent = newQty;
        existingRow.cells[2].textContent = newAvgPrice.toFixed(2);
        existingRow.cells[3].textContent = currentPrice.toFixed(2);
        existingRow.cells[4].textContent = newTotal.toFixed(2);

        // Update DB (no duplicate)
        const stockId = existingRow.getAttribute('data-id');
        fetch(`/update_stock/${stockId}`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({quantity: newQty, purchase_price: newAvgPrice})
        }).catch(err => console.error('Erro ao atualizar:', err));

        registerTransaction(symbol, 'compra', quantity, purchasePrice);
    } else {
        // New position
        const row = tbody.insertRow();
        const totalPurchase = purchasePrice * quantity;
        row.setAttribute('data-id', 'pending');
        row.innerHTML = `
            <td class="sym-cell">${symbol}</td>
            <td>${quantity}</td>
            <td>${purchasePrice.toFixed(2)}</td>
            <td>${currentPrice.toFixed(2)}</td>
            <td>${totalPurchase.toFixed(2)}</td>
            <td>—</td>
            <td>—</td>
            <td>—</td>
            <td>
              <div class="row-actions">
                <button class="btn-sell-row" onclick="openSellModal(this)">Vender</button>
                <button class="btn-del-row"  onclick="removeStock(this)">🗑️</button>
              </div>
            </td>`;

        saveStock(symbol, quantity, purchasePrice, row);
    }

    updatePortfolioPercentages();
    closeModal('modalAdd');
}

// ── Sell modal ────────────────────────────────────────────────────────────────
function openSellModal(btn) {
    _sellRow = btn.closest('tr');
    const symbol       = _sellRow.cells[0].textContent.trim();
    const maxQty       = parseFloat(_sellRow.cells[1].textContent);
    const currentPrice = _sellRow.cells[3].textContent;

    document.getElementById('sellSymLabel').textContent = symbol;
    document.getElementById('sQty').value   = '';
    document.getElementById('sPrice').value = currentPrice !== '—' ? currentPrice : '';
    document.getElementById('sMaxHint').textContent = `Máximo disponível: ${maxQty}`;
    document.getElementById('sCurHint').textContent  =
        currentPrice !== '—' ? `Preço atual de mercado: $${currentPrice}` : '';

    openModal('modalSell');
    document.getElementById('sQty').focus();
}

function confirmSell() {
    if (!_sellRow) return;

    const symbol     = _sellRow.cells[0].textContent.trim();
    const currentQty = parseFloat(_sellRow.cells[1].textContent);
    const avgPrice   = parseFloat(_sellRow.cells[2].textContent);
    const sellQty    = parseFloat(document.getElementById('sQty').value);
    const sellPrice  = parseFloat(document.getElementById('sPrice').value);

    if (isNaN(sellQty) || sellQty <= 0 || sellQty > currentQty) {
        alert(`Quantidade inválida. Máximo: ${currentQty}`); return;
    }
    if (isNaN(sellPrice) || sellPrice <= 0) {
        alert('Preço inválido.'); return;
    }

    const newQty   = +(currentQty - sellQty).toFixed(8);
    const newTotal = newQty * avgPrice;

    if (newQty === 0) {
        removeStock(_sellRow.querySelector('.btn-del-row'));
    } else {
        _sellRow.cells[1].textContent = newQty;
        _sellRow.cells[4].textContent = newTotal.toFixed(2);
        updatePortfolioPercentages();
    }

    registerTransaction(symbol, 'venda', sellQty, sellPrice);
    closeModal('modalSell');
    _sellRow = null;
}

// ── Remove stock ──────────────────────────────────────────────────────────────
function removeStock(button) {
    const row     = button.closest('tr');
    const stockId = row.getAttribute('data-id');

    if (!stockId || stockId === 'pending') {
        row.remove();
        updatePortfolioPercentages();
        return;
    }

    if (!confirm('Remover esta ação do portfólio?')) return;

    fetch(`/remove_stock/${stockId}`, {method: 'DELETE'})
        .then(r => r.json())
        .then(d => {
            if (d.message) { row.remove(); updatePortfolioPercentages(); }
            else alert('Erro ao remover a ação.');
        })
        .catch(() => alert('Erro ao remover a ação.'));
}

// ── Save to DB ────────────────────────────────────────────────────────────────
function saveStock(symbol, quantity, purchasePrice, row) {
    fetch('/add_stock', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({symbol, quantity, purchase_price: purchasePrice})
    })
    .then(r => r.json())
    .then(data => {
        if (data.id && row) row.setAttribute('data-id', String(data.id));
    })
    .catch(err => console.error('Erro ao guardar:', err));

    registerTransaction(symbol, 'compra', quantity, purchasePrice);
}

// ── Register transaction ──────────────────────────────────────────────────────
function registerTransaction(symbol, action, quantity, price) {
    fetch('/api/add_transaction', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({symbol, action, quantity, price})
    })
    .then(r => r.json())
    .then(d => console.log(d.message))
    .catch(err => console.error('Erro ao registar transação:', err));
}

// ── Fetch current price ───────────────────────────────────────────────────────
async function getCurrentPrice(symbol) {
    try {
        const r = await fetch('/get_price', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({symbol})
        });
        const d = await r.json();
        return d.error ? null : parseFloat(d.price);
    } catch {
        return null;
    }
}

// ── Load portfolio from DB ────────────────────────────────────────────────────
async function loadPortfolio() {
    const tbody = document.getElementById('portfolioBody');
    tbody.innerHTML = '<tr><td colspan="9" class="loading-cell"><span class="spinner-sm"></span>A carregar portfólio...</td></tr>';

    try {
        const r    = await fetch('/get_portfolio');
        const data = await r.json();
        tbody.innerHTML = '';

        if (!data.length) {
            tbody.innerHTML = '<tr><td colspan="9" class="empty-cell">Portfólio vazio. Clica em "+ Adicionar Ação" para começar.</td></tr>';
            updateSummaryCards();
            return;
        }

        // Insert rows with spinner for current price
        for (const stock of data) {
            const sym   = stock.symbol.toUpperCase();
            const total = stock.quantity * stock.purchase_price;
            const row   = tbody.insertRow();
            row.setAttribute('data-id', stock.id);
            row.innerHTML = `
                <td class="sym-cell">${sym}</td>
                <td>${stock.quantity}</td>
                <td>${stock.purchase_price.toFixed(2)}</td>
                <td><span class="spinner-sm"></span></td>
                <td>${total.toFixed(2)}</td>
                <td>—</td>
                <td>—</td>
                <td>—</td>
                <td>
                  <div class="row-actions">
                    <button class="btn-sell-row" onclick="openSellModal(this)">Vender</button>
                    <button class="btn-del-row"  onclick="removeStock(this)">🗑️</button>
                  </div>
                </td>`;
        }

        // Fetch all prices in parallel
        await Promise.all(data.map(async stock => {
            const price = await getCurrentPrice(stock.symbol);
            const row   = tbody.querySelector(`tr[data-id="${stock.id}"]`);
            if (!row) return;
            row.cells[3].textContent = price != null ? price.toFixed(2) : '—';
        }));

        updatePortfolioPercentages();
    } catch (err) {
        tbody.innerHTML = `<tr><td colspan="9" class="empty-cell" style="color:#e74c3c">Erro ao carregar portfólio: ${err.message}</td></tr>`;
    }
}

// ── Price alerts banner ───────────────────────────────────────────────────────
function checkPriceAlerts() {
    const banner = document.getElementById('alertBanner');
    if (!banner) return;
    fetch('/api/alerts/check')
        .then(r => r.json())
        .then(triggered => {
            if (!triggered.length) return;
            const fmt = v => '$' + parseFloat(v).toLocaleString('pt-PT', {
                minimumFractionDigits: 2, maximumFractionDigits: 2
            });
            const items = triggered.map(a =>
                `<li>${a.symbol}: ${fmt(a.current_price)} ${a.direction === 'above' ? 'subiu acima' : 'desceu abaixo'} de ${fmt(a.target_price)}</li>`
            ).join('');
            banner.innerHTML = `Alertas Disparados! <a href="/alerts" style="color:#fff;text-decoration:underline">Ver todos</a><ul>${items}</ul>`;
            banner.style.display = 'block';
        })
        .catch(() => {});
}

console.log('Portfolio script loaded.');
