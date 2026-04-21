let fcfChart = null;
let _autoRm = null;      // valor automático recebido do backend
let _autoGrowth = null;  // valor automático de crescimento

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtMoney(v, decimals = 2) {
    if (v == null || isNaN(v)) return '—';
    return '$' + Math.abs(v).toLocaleString('pt-PT', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

function fmtB(v) {
    // Format large numbers in billions/millions
    if (v == null || isNaN(v)) return '—';
    const abs = Math.abs(v);
    const sign = v < 0 ? '-' : '';
    if (abs >= 1e12) return sign + '$' + (abs / 1e12).toFixed(2) + 'T';
    if (abs >= 1e9)  return sign + '$' + (abs / 1e9).toFixed(2) + 'B';
    if (abs >= 1e6)  return sign + '$' + (abs / 1e6).toFixed(2) + 'M';
    return sign + '$' + abs.toLocaleString('pt-PT');
}

function pct(v, decimals = 1) {
    if (v == null || isNaN(v)) return '—';
    return (v * 100).toFixed(decimals) + '%';
}

// ── Slider helpers ────────────────────────────────────────────────────────────
function updateSliderLabels() {
    const rm     = parseFloat(document.getElementById('sliderRm').value);
    const growth = parseFloat(document.getElementById('sliderGrowth').value);
    const term   = parseFloat(document.getElementById('sliderTerm').value);
    document.getElementById('rmVal').textContent     = rm.toFixed(1) + '%';
    document.getElementById('growthVal').textContent = growth.toFixed(1) + '%';
    document.getElementById('termVal').textContent   = term.toFixed(2) + '%';
}

function syncSlidersFromData(d) {
    // Sync Rm slider to auto value from backend
    if (d.wacc_components && d.wacc_components.market_return != null) {
        _autoRm = d.wacc_components.market_return * 100;
        const rmSlider = document.getElementById('sliderRm');
        rmSlider.value = Math.min(20, Math.max(5, _autoRm)).toFixed(1);
    }
    // Sync growth slider to auto value from backend
    if (d.growth_rate != null) {
        _autoGrowth = d.growth_rate * 100;
        const gSlider = document.getElementById('sliderGrowth');
        gSlider.value = Math.min(150, Math.max(-20, _autoGrowth)).toFixed(1);
    }
    // Sync terminal slider
    if (d.terminal_growth_rate != null) {
        const tSlider = document.getElementById('sliderTerm');
        tSlider.value = Math.min(5, Math.max(0.5, d.terminal_growth_rate * 100)).toFixed(2);
    }
    updateSliderLabels();
}

// ── Main function ─────────────────────────────────────────────────────────────
function runValuation() {
    const ticker = document.getElementById('tickerInput').value.trim().toUpperCase();
    if (!ticker) { alert('Introduz um ticker.'); return; }

    const rm     = parseFloat(document.getElementById('sliderRm').value) / 100;
    const growth = parseFloat(document.getElementById('sliderGrowth').value) / 100;
    const term   = parseFloat(document.getElementById('sliderTerm').value) / 100;

    document.getElementById('tickerInput').value = ticker;
    document.getElementById('btnCalc').disabled = true;
    document.getElementById('loadingState').style.display = 'block';
    document.getElementById('errorState').style.display  = 'none';
    document.getElementById('results').style.display     = 'none';

    // Só envia override se o utilizador já tem os valores auto e os alterou
    // Na primeira chamada (_auto* == null), deixa o backend calcular tudo automaticamente
    const rmOverride     = (_autoRm     != null && Math.abs(rm * 100     - _autoRm)     > 0.1) ? rm     : null;
    const growthOverride = (_autoGrowth != null && Math.abs(growth * 100 - _autoGrowth) > 0.1) ? growth : null;

    const payload = { symbol: ticker };
    if (rmOverride     !== null) payload.market_return = rmOverride;
    if (growthOverride !== null) payload.growth_rate   = growthOverride;
    payload.terminal_growth_rate = term;  // sempre enviado (utilizador controla)

    fetch('/api/calculate_valuation', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('btnCalc').disabled = false;

        if (data.error) {
            document.getElementById('errorState').innerHTML =
                `<strong>Erro:</strong> ${data.error}`;
            document.getElementById('errorState').style.display = 'block';
            return;
        }
        syncSlidersFromData(data);
        renderResults(data);
    })
    .catch(err => {
        document.getElementById('loadingState').style.display = 'none';
        document.getElementById('btnCalc').disabled = false;
        document.getElementById('errorState').innerHTML =
            `<strong>Erro de rede:</strong> ${err.message}`;
        document.getElementById('errorState').style.display = 'block';
    });
}

// ── Render ────────────────────────────────────────────────────────────────────
function renderResults(d) {
    const price = d.current_price;
    const dcf   = d.dcf_value_per_share;
    const mos   = (price && dcf) ? ((dcf - price) / price * 100) : null;

    // ── Verdict banner ────────────────────────────────────────────────────────
    const banner = document.getElementById('verdictBanner');
    banner.className = 'verdict-banner';
    let icon, title, sub, cls;

    if (mos === null) {
        icon = '❓'; title = 'Não determinado'; sub = 'Dados insuficientes para avaliação.'; cls = 'slight-over';
    } else if (mos >= 30) {
        icon = '🟢'; title = 'SUBVALORIZADO'; sub = `${d.company_name} está significativamente abaixo do valor intrínseco.`; cls = 'undervalued';
    } else if (mos >= 10) {
        icon = '🟡'; title = 'LIGEIRAMENTE SUBVALORIZADO'; sub = `${d.company_name} oferece uma margem de segurança razoável.`; cls = 'slight-under';
    } else if (mos >= -10) {
        icon = '🟠'; title = 'COTAÇÃO JUSTA'; sub = `${d.company_name} está próximo do valor intrínseco estimado.`; cls = 'slight-over';
    } else {
        icon = '🔴'; title = 'SOBREVALORIZADO'; sub = `${d.company_name} está acima do valor intrínseco estimado.`; cls = 'overvalued';
    }

    banner.classList.add(cls);
    document.getElementById('verdictIcon').textContent = icon;
    document.getElementById('verdictTitle').textContent = title;
    document.getElementById('verdictSub').textContent   = sub;
    const mosSign = mos != null ? (mos >= 0 ? '+' : '') : '';
    document.getElementById('verdictMargin').innerHTML =
        `${mosSign}${mos != null ? mos.toFixed(1) + '%' : '—'}<span>Margem de Segurança</span>`;

    // ── KPI cards ─────────────────────────────────────────────────────────────
    document.getElementById('kpiPrice').textContent = price ? fmtMoney(price) : '—';
    document.getElementById('kpiName').textContent  = d.company_name || d.ticker;
    document.getElementById('kpiDCF').textContent   = dcf  ? fmtMoney(dcf)  : '—';

    const mosEl = document.getElementById('kpiMOS');
    mosEl.textContent = mos != null ? (mos >= 0 ? '+' : '') + mos.toFixed(1) + '%' : '—';
    mosEl.className   = 'kpi-value ' + (mos == null ? '' : mos >= 0 ? 'pos' : 'neg');

    document.getElementById('kpiWACC').textContent = pct(d.wacc);

    // ── Price position bar ────────────────────────────────────────────────────
    if (price && dcf) {
        const minV = Math.min(price, dcf) * 0.85;
        const maxV = Math.max(price, dcf) * 1.15;
        const range = maxV - minV;
        const pricePct = ((price - minV) / range * 100).toFixed(1);

        document.getElementById('barLabelMin').textContent = fmtMoney(minV);
        document.getElementById('barLabelMax').textContent = fmtMoney(maxV);
        document.getElementById('barFill').style.width = '100%';

        // Marker = current price position
        document.getElementById('barMarker').style.left = pricePct + '%';
        document.getElementById('barMarkerLabel').textContent = 'Preço Atual ' + fmtMoney(price);

        // DCF marker
        const dcfPct = ((dcf - minV) / range * 100).toFixed(1);
        const track  = document.getElementById('barTrack');
        // Remove old DCF marker if any
        const old = track.querySelector('.dcf-marker');
        if (old) old.remove();

        const dcfMarker = document.createElement('div');
        dcfMarker.className = 'price-bar-marker dcf-marker';
        dcfMarker.style.cssText = `left:${dcfPct}%;background:#27ae60;position:absolute;top:-4px;transform:translateX(-50%);width:20px;height:20px;border-radius:50%;border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.25);`;
        const dcfLabel = document.createElement('div');
        dcfLabel.className = 'price-bar-marker-label';
        dcfLabel.style.cssText = `position:absolute;top:20px;transform:translateX(-50%);font-size:11px;font-weight:700;color:#27ae60;white-space:nowrap;`;
        dcfLabel.textContent = 'DCF ' + fmtMoney(dcf);
        dcfMarker.appendChild(dcfLabel);
        track.appendChild(dcfMarker);
    }

    // ── FCF chart ─────────────────────────────────────────────────────────────
    if (fcfChart) { fcfChart.destroy(); fcfChart = null; }

    if (d.projected_fcf && d.projected_fcf.length) {
        const labels = d.projected_fcf.map((_, i) => `Ano ${i + 1}`);
        const colors = d.projected_fcf.map(v => v >= 0 ? 'rgba(39,174,96,.85)' : 'rgba(231,76,60,.85)');
        const borders = d.projected_fcf.map(v => v >= 0 ? '#1e8449' : '#c0392b');

        fcfChart = new Chart(document.getElementById('fcfChart').getContext('2d'), {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'FCF Projetado',
                    data: d.projected_fcf,
                    backgroundColor: colors,
                    borderColor: borders,
                    borderWidth: 1.5,
                    borderRadius: 5,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {display: false},
                    tooltip: {
                        callbacks: {
                            label: ctx => ' ' + fmtB(ctx.parsed.y)
                        }
                    }
                },
                scales: {
                    y: {
                        ticks: {
                            callback: v => fmtB(v),
                            font: {size: 11}
                        },
                        grid: {color: '#f0f0f0'}
                    },
                    x: {
                        grid: {display: false},
                        ticks: {font: {size: 12}}
                    }
                }
            }
        });
    }

    // ── WACC breakdown ────────────────────────────────────────────────────────
    const wc = d.wacc_components || {};
    const eqW  = wc.equity_weight != null ? (wc.equity_weight * 100).toFixed(1) : null;
    const debtW = wc.debt_weight  != null ? (wc.debt_weight  * 100).toFixed(1) : null;

    document.getElementById('waccBreakdown').innerHTML = `
        ${(eqW && debtW) ? `
        <div class="capital-bar">
            <div class="capital-bar-eq"  style="width:${eqW}%"></div>
            <div class="capital-bar-dbt" style="width:${debtW}%"></div>
        </div>
        <div class="capital-legend">
            <span><span class="dot-blue"></span>Capital Próprio ${eqW}%</span>
            <span><span class="dot-red"></span>Dívida ${debtW}%</span>
        </div>` : ''}

        <div class="wacc-row"><span class="wacc-label">Taxa Isenta de Risco (Rf)</span><span class="wacc-val">${pct(wc.risk_free_rate)}</span></div>
        <div class="wacc-row"><span class="wacc-label">Beta (β)</span><span class="wacc-val">${wc.beta != null ? wc.beta.toFixed(2) : '—'}</span></div>
        <div class="wacc-row"><span class="wacc-label">Retorno Mercado (Rm)</span><span class="wacc-val">${pct(wc.market_return)}</span></div>
        <div class="wacc-row"><span class="wacc-label">Custo Capital Próprio (Ke)</span><span class="wacc-val">${pct(wc.cost_of_equity)}</span></div>
        <div class="wacc-row"><span class="wacc-label">Custo Dívida (Kd)</span><span class="wacc-val">${pct(wc.cost_of_debt)}</span></div>
        <div class="wacc-row"><span class="wacc-label">Taxa Imposto Efectiva</span><span class="wacc-val">${pct(wc.tax_rate)}</span></div>
        <div class="wacc-row" style="border-top:2px solid #3498db;margin-top:4px;padding-top:9px">
            <span class="wacc-label" style="font-weight:700;color:#2c3e50">WACC Total</span>
            <span class="wacc-val" style="color:#3498db">${pct(d.wacc)}</span>
        </div>
    `;

    // ── Assumptions ───────────────────────────────────────────────────────────
    document.getElementById('aGrowth').textContent  = pct(d.growth_rate);
    document.getElementById('aTerminal').textContent = pct(d.terminal_growth_rate);
    document.getElementById('aTermVal').textContent  = fmtB(d.terminal_value);

    // Show results
    document.getElementById('results').style.display = 'block';
}

// ── Enter key support + init sliders ─────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    updateSliderLabels();
    document.getElementById('tickerInput').addEventListener('keydown', e => {
        if (e.key === 'Enter') runValuation();
    });
});
