const PALETTE = [
    '#3498db','#e67e22','#2ecc71','#9b59b6','#e74c3c',
    '#1abc9c','#f39c12','#2980b9','#8e44ad','#16a085',
    '#d35400','#27ae60','#c0392b','#2471a3','#1e8449'
];

let portfolioChart = null;

function getColorByPerformance(pct) {
    if (pct >= 15)  return '#0e6b0e';
    if (pct >= 8)   return '#1a9e1a';
    if (pct >= 3)   return '#27ae60';
    if (pct >= 0)   return '#52c97a';
    if (pct >= -3)  return '#e74c3c';
    if (pct >= -8)  return '#c0392b';
    return '#922b21';
}

function updateHeatmap(data) {
    const container = document.getElementById('heatmapContainer');
    if (!container) return;
    container.innerHTML = '';

    data.forEach(stock => {
        const size = Math.max(Math.sqrt(stock.percentage) * 32, 64);
        const box  = document.createElement('div');

        box.style.cssText = `
            width:${size}px; height:${size}px;
            background:${getColorByPerformance(stock.performance)};
            display:flex; flex-direction:column;
            justify-content:center; align-items:center;
            border-radius:8px; color:#fff;
            font-weight:bold; text-align:center;
            font-size:${size < 75 ? 11 : 13}px;
            cursor:default; transition:transform .15s, box-shadow .15s;
        `;

        const perf = isNaN(stock.performance)
            ? '—'
            : (stock.performance >= 0 ? '+' : '') + stock.performance.toFixed(2) + '%';

        box.innerHTML = `
            <div>${stock.symbol}</div>
            <div style="opacity:.85;font-size:11px">${stock.percentage.toFixed(1)}%</div>
            <div style="font-size:12px;margin-top:2px">${perf}</div>`;

        box.addEventListener('mouseover', () => {
            box.style.transform = 'scale(1.06)';
            box.style.boxShadow = '0 4px 12px rgba(0,0,0,.2)';
        });
        box.addEventListener('mouseout', () => {
            box.style.transform = 'scale(1)';
            box.style.boxShadow = 'none';
        });

        container.appendChild(box);
    });
}

function createPortfolioChart(data) {
    const canvas = document.getElementById('portfolioChart');
    if (!canvas) return;

    const colors = data.labels.map((_, i) => PALETTE[i % PALETTE.length]);

    if (portfolioChart) portfolioChart.destroy();

    portfolioChart = new Chart(canvas.getContext('2d'), {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: colors,
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right', labels: { font: { size: 12 }, padding: 12 } },
                title: { display: true, text: 'Composição do Portfólio' },
                tooltip: {
                    callbacks: {
                        label: ctx => {
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const pct   = ((ctx.parsed / total) * 100).toFixed(1);
                            return ` ${ctx.label}: ${pct}%`;
                        }
                    }
                }
            }
        }
    });
}

function updateChartFromTable() {
    const table = document.getElementById('portfolioTable');
    if (!table) return;

    const rows    = Array.from(table.getElementsByTagName('tbody')[0].rows);
    const pieData = { labels: [], values: [] };
    const heatmapData = [];

    rows.forEach(row => {
        const symbol     = row.cells[0].textContent.trim();
        const pctPortf   = parseFloat(row.cells[7].textContent);  // % do portfólio
        const pctPerf    = parseFloat(row.cells[6].textContent);  // % lucro/perda

        if (!isNaN(pctPortf)) {
            pieData.labels.push(symbol);
            pieData.values.push(pctPortf);
            heatmapData.push({ symbol, percentage: pctPortf, performance: pctPerf });
        }
    });

    createPortfolioChart(pieData);
    updateHeatmap(heatmapData);
}

document.addEventListener('DOMContentLoaded', updateChartFromTable);
