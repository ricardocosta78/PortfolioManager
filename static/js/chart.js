const PALETTE = [
    '#3498db','#e67e22','#2ecc71','#9b59b6','#e74c3c',
    '#1abc9c','#f39c12','#2980b9','#8e44ad','#16a085',
    '#d35400','#27ae60','#c0392b','#2471a3','#1e8449'
];

let portfolioChart = null;

// ── Performance colour scale ──────────────────────────────────────────────────
function getColorByPerformance(pct) {
    if (isNaN(pct)) return '#7f8c8d';
    if (pct >= 15)  return '#0e6b0e';
    if (pct >= 8)   return '#1a9e1a';
    if (pct >= 3)   return '#27ae60';
    if (pct >= 0)   return '#52c97a';
    if (pct >= -3)  return '#e74c3c';
    if (pct >= -8)  return '#c0392b';
    return '#922b21';
}

// ── Squarified treemap ────────────────────────────────────────────────────────
function squarify(items, x, y, w, h) {
    if (!items.length || w <= 0 || h <= 0) return [];
    const total = items.reduce((s, it) => s + it.a, 0);
    if (!total) return [];

    const result = [];
    const nodes  = items
        .map(it => ({...it, a: (it.a / total) * w * h}))
        .sort((a, b) => b.a - a.a);

    function worst(row, side) {
        const s = row.reduce((sum, r) => sum + r.a, 0);
        const t = s / side;
        return row.reduce((m, r) => {
            const len = r.a / t;
            return Math.max(m, Math.max(len / t, t / len));
        }, 0);
    }

    function layoutStrip(row, rx, ry, rw, rh) {
        const s = row.reduce((sum, r) => sum + r.a, 0);
        let cx = rx, cy = ry;
        if (rw >= rh) {
            const bw = s / rh;
            row.forEach(r => {
                const bh = r.a / bw;
                result.push({...r, x: cx, y: cy, w: bw, h: bh});
                cy += bh;
            });
            return {x: rx + bw, y: ry, w: rw - bw, h: rh};
        } else {
            const bh = s / rw;
            row.forEach(r => {
                const bw = r.a / bh;
                result.push({...r, x: cx, y: cy, w: bw, h: bh});
                cx += bw;
            });
            return {x: rx, y: ry + bh, w: rw, h: rh - bh};
        }
    }

    function layout(nodes, rx, ry, rw, rh) {
        if (!nodes.length || rw <= 1 || rh <= 1) return;
        const side = Math.min(rw, rh);
        let row = [nodes[0]], i = 1;
        while (i < nodes.length) {
            const candidate = [...row, nodes[i]];
            if (row.length > 1 && worst(candidate, side) > worst(row, side)) break;
            row = candidate;
            i++;
        }
        const rem = layoutStrip(row, rx, ry, rw, rh);
        layout(nodes.slice(i), rem.x, rem.y, rem.w, rem.h);
    }

    layout(nodes, x, y, w, h);
    return result;
}

// ── Heatmap (squarified treemap) ──────────────────────────────────────────────
function updateHeatmap(data) {
    const container = document.getElementById('heatmapContainer');
    if (!container) return;
    container.innerHTML = '';
    if (!data.length) return;

    const W = container.offsetWidth  || container.parentElement.offsetWidth || 400;
    const H = container.offsetHeight || 270;

    const boxes = squarify(
        data.map(s => ({...s, a: s.percentage})),
        0, 0, W, H
    );

    boxes.forEach(b => {
        const perf = isNaN(b.performance) ? '—'
            : (b.performance >= 0 ? '+' : '') + b.performance.toFixed(2) + '%';

        const fontSize = Math.min(14, Math.max(9, Math.min(b.w / 6, b.h / 3)));
        const showPerf = b.h > 38 && b.w > 46;
        const showPct  = b.h > 54 && b.w > 46;

        const div = document.createElement('div');
        div.style.cssText = `
            position: absolute;
            left: ${b.x + 1}px; top: ${b.y + 1}px;
            width: ${Math.max(b.w - 2, 0)}px; height: ${Math.max(b.h - 2, 0)}px;
            background: ${getColorByPerformance(b.performance)};
            border-radius: 4px; color: #fff;
            display: flex; flex-direction: column;
            justify-content: center; align-items: center;
            overflow: hidden; cursor: default; user-select: none;
            font-size: ${fontSize}px;
            transition: filter .15s;
        `;
        div.innerHTML = `
            <div style="font-weight:700;line-height:1.2;text-align:center">${b.symbol}</div>
            ${showPerf ? `<div style="opacity:.9;font-size:${Math.max(fontSize - 1, 9)}px">${perf}</div>` : ''}
            ${showPct  ? `<div style="opacity:.7;font-size:${Math.max(fontSize - 2, 8)}px">${b.percentage.toFixed(1)}%</div>` : ''}
        `;
        div.addEventListener('mouseover', () => div.style.filter = 'brightness(1.15)');
        div.addEventListener('mouseout',  () => div.style.filter = '');
        container.appendChild(div);
    });
}

// ── Donut chart ───────────────────────────────────────────────────────────────
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
                legend: {position: 'right', labels: {font: {size: 12}, padding: 12}},
                title: {display: false},
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

// ── Read table → update charts ────────────────────────────────────────────────
function updateChartFromTable() {
    const table = document.getElementById('portfolioTable');
    if (!table) return;

    const rows      = Array.from(table.getElementsByTagName('tbody')[0].rows);
    const pieData   = {labels: [], values: []};
    const heatData  = [];

    rows.forEach(row => {
        if (!row.getAttribute('data-id')) return; // skip loading/empty rows
        const symbol  = row.cells[0].textContent.trim();
        const pctPort = parseFloat(row.cells[7].textContent);  // % portfólio
        const pctPerf = parseFloat(row.cells[6].textContent);  // % G/P

        if (!isNaN(pctPort) && pctPort > 0) {
            pieData.labels.push(symbol);
            pieData.values.push(pctPort);
            heatData.push({symbol, percentage: pctPort, performance: pctPerf});
        }
    });

    if (pieData.labels.length) {
        createPortfolioChart(pieData);
        updateHeatmap(heatData);
    }
}
