// Function to update portfolio percentages
function updatePortfolioPercentages() {
    let table = document.getElementById("portfolioTable");
    let rows = Array.from(table.getElementsByTagName('tbody')[0].rows);
    let totalInvestment = rows.reduce((acc, row) => acc + parseFloat(row.cells[4].innerHTML), 0);

    rows.forEach(row => {
        let totalPurchase = parseFloat(row.cells[4].innerHTML);
        let currentValue = parseFloat(row.cells[3].innerHTML) * parseFloat(row.cells[1].innerHTML);
        let profitLoss = currentValue - totalPurchase;
        let profitLossPercentage = (profitLoss / totalPurchase * 100).toFixed(2);
        let portfolioPercentage = (totalPurchase / totalInvestment * 100).toFixed(2);
        row.cells[5].innerHTML = profitLoss.toFixed(2);
        row.cells[6].innerHTML = profitLossPercentage + "%";
        row.cells[7].innerHTML = portfolioPercentage + "%";
    });

    updateChartFromTable();
}

document.getElementById("addStock").addEventListener("click", function() {
    let symbol = prompt("Digite o símbolo da ação (ex: AAPL para Apple):").toUpperCase();
    if (!symbol) return; // Exit if user cancels

    fetch('/get_price', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symbol: symbol })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            alert(data.error);
        } else {
            let quantity = parseFloat(prompt("Quantidade:"));
            if (isNaN(quantity)) return; // Exit if input is not a number

            let purchasePrice = parseFloat(prompt("Preço de compra por ação:"));
            if (isNaN(purchasePrice)) return; // Exit if input is not a number

            let table = document.getElementById("portfolioTable").getElementsByTagName('tbody')[0];
            let existingRow = Array.from(table.rows).find(row => row.cells[0].innerHTML === symbol);

            if (existingRow) {
                // Update existing stock
                let existingQuantity = parseFloat(existingRow.cells[1].innerHTML);
                let existingTotalPurchase = parseFloat(existingRow.cells[4].innerHTML);
                let newQuantity = existingQuantity + quantity;
                let newTotalPurchase = existingTotalPurchase + (quantity * purchasePrice);
                let newAveragePrice = newTotalPurchase / newQuantity;

                existingRow.cells[1].innerHTML = newQuantity;
                existingRow.cells[2].innerHTML = newAveragePrice.toFixed(2);
                existingRow.cells[4].innerHTML = newTotalPurchase.toFixed(2);
            } else {
                // Add new stock
                let row = table.insertRow();
                let currentPrice = parseFloat(data.price);
                let totalPurchase = purchasePrice * quantity;

                row.innerHTML = `
                    <td>${symbol}</td>
                    <td>${quantity}</td>
                    <td>${purchasePrice.toFixed(2)}</td>
                    <td>${currentPrice.toFixed(2)}</td>
                    <td>${totalPurchase.toFixed(2)}</td>
                    <td>-</td>
                    <td>-</td>
                    <td>-</td>
                    <td>
                        <button onclick="sellStock(this)">Vender</button>
                        <button onclick="removeStock(this)">🗑️</button>
                    </td>
                `;
            }

            updatePortfolioPercentages();
            saveStock(symbol, quantity, purchasePrice);
        }
    })
    .catch(error => {
        console.error('Erro ao obter os dados:', error);
    });
});

function sellStock(button) {
    let row = button.closest('tr');
    let symbol = row.cells[0].innerHTML;
    let currentQuantity = parseFloat(row.cells[1].innerHTML);
    let sellQuantity = parseFloat(prompt(`Quantidade a vender (máximo ${currentQuantity}):`));

    if (isNaN(sellQuantity) || sellQuantity <= 0 || sellQuantity > currentQuantity) {
        alert("Quantidade inválida.");
        return;
    }

    let currentPrice = parseFloat(prompt("Preço de venda por ação:"));
    if (isNaN(currentPrice) || currentPrice <= 0) {
        alert("Preço inválido.");
        return;
    }

    let newQuantity = currentQuantity - sellQuantity;
    let averagePrice = parseFloat(row.cells[2].innerHTML);
    let newTotalPurchase = newQuantity * averagePrice;

    if (newQuantity === 0) {
        removeStock(button);
    } else {
        row.cells[1].innerHTML = newQuantity.toFixed(2);
        row.cells[4].innerHTML = newTotalPurchase.toFixed(2);
    }

    updatePortfolioPercentages();
    registerTransaction(symbol, 'venda', sellQuantity, currentPrice);
}

function removeStock(button) {
    let row = button.closest('tr');
    let stockId = row.getAttribute('data-id');
    
    fetch(`/remove_stock/${stockId}`, {
        method: 'DELETE'
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            row.remove();
            updatePortfolioPercentages();
        } else {
            alert('Erro ao remover a ação.');
        }
    })
    .catch(error => {
        console.error('Erro ao remover a ação:', error);
    });
}

function saveStock(symbol, quantity, purchasePrice) {
    fetch('/add_stock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, quantity, purchase_price: purchasePrice })
    })
    .then(r => r.json())
    .then(data => console.log(data.message))
    .catch(error => console.error('Erro ao guardar a ação:', error));

    // Registar no histórico
    registerTransaction(symbol, 'compra', quantity, purchasePrice);
}

function registerTransaction(symbol, action, quantity, price) {
    fetch('/api/add_transaction', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, action, quantity, price })
    })
    .then(r => r.json())
    .then(data => console.log(data.message))
    .catch(error => console.error('Erro ao registar transação:', error));
}

async function getCurrentPrice(symbol) {
    try {
        const response = await fetch('/get_price', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ symbol: symbol })
        });
        const data = await response.json();
        if (data.error) {
            console.error('Erro ao obter preço para', symbol, ':', data.error);
            return null;
        }
        return data.price;
    } catch (error) {
        console.error('Erro ao obter preço para', symbol, ':', error);
        return null;
    }
}

async function loadPortfolio() {
    try {
        const response = await fetch('/get_portfolio');
        const data = await response.json();
        let table = document.getElementById("portfolioTable").getElementsByTagName('tbody')[0];
        table.innerHTML = ''; // Limpar linhas existentes
        
        for (const stock of data) {
            stock.symbol = stock.symbol.toUpperCase();
            
            const currentPrice = await getCurrentPrice(stock.symbol);
            const totalPurchase = stock.quantity * stock.purchase_price;
            const currentValue = stock.quantity * currentPrice;
            const profitLoss = currentValue - totalPurchase;
            const profitLossPercentage = ((profitLoss / totalPurchase) * 100).toFixed(2);
            
            let row = table.insertRow();
            row.setAttribute('data-id', stock.id);
            row.innerHTML = `
                <td>${stock.symbol}</td>
                <td>${stock.quantity}</td>
                <td>${stock.purchase_price.toFixed(2)}</td>
                <td>${currentPrice ? currentPrice.toFixed(2) : '-'}</td>
                <td>${totalPurchase.toFixed(2)}</td>
                <td>${profitLoss.toFixed(2)}</td>
                <td>${profitLossPercentage}%</td>
                <td>-</td>
                <td>
                    <button onclick="sellStock(this)">Vender</button>
                    <button onclick="removeStock(this)">🗑️</button>
                </td>
            `;
        }
        
        updatePortfolioPercentages();
    } catch (error) {
        console.error('Erro ao carregar o portfólio:', error);
    }
}

// Garantir que o DOM está completamente carregado antes de executar o script
document.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded. Initializing portfolio...");
    loadPortfolio();
    checkPriceAlerts();
});


// Verifica alertas de preço ao carregar o portfólio
function checkPriceAlerts() {
    const banner = document.getElementById('alertBanner');
    if (!banner) return;
    fetch('/api/alerts/check')
        .then(r => r.json())
        .then(triggered => {
            if (!triggered.length) return;
            const fmt = v => '$' + parseFloat(v).toLocaleString('pt-PT', {minimumFractionDigits: 2, maximumFractionDigits: 2});
            const items = triggered.map(a =>
                `<li>${a.symbol}: preço atual ${fmt(a.current_price)} ${a.direction === 'above' ? 'subiu acima' : 'desceu abaixo'} de ${fmt(a.target_price)}</li>`
            ).join('');
            banner.innerHTML = `Alertas Disparados! <a href="/alerts" style="color:#fff;text-decoration:underline">Ver todos</a><ul style="margin:8px 0 0 18px;font-weight:normal;font-size:14px">${items}</ul>`;
            banner.style.display = 'block';
        })
        .catch(() => {});
}

// Adicionar um log para verificar se o script está sendo executado
console.log("Portfolio management script loaded.");