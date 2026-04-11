// Function to update portfolio percentages
function updatePortfolioPercentages() {
    let table = document.getElementById("portfolioTable");
    let rows = Array.from(table.getElementsByTagName('tbody')[0].rows);
    let totalInvestment = rows.reduce((acc, row) => acc + parseFloat(row.cells[4].innerHTML), 0);

    rows.forEach(row => {
        let totalPurchase = parseFloat(row.cells[4].innerHTML);
        let currentValue = parseFloat(row.cells[1].innerHTML) * parseFloat(row.cells[3].innerHTML);
        let profitLoss = parseFloat(row.cells[5].innerHTML);
        let profitLossPercentage = (profitLoss / totalPurchase * 100).toFixed(2);
        let portfolioPercentage = (totalPurchase / totalInvestment * 100).toFixed(2);
        row.cells[6].innerHTML = profitLossPercentage + "%";
        row.cells[7].innerHTML = portfolioPercentage + "%";
    });

    updateChartFromTable();
}

document.getElementById("addStock").addEventListener("click", function() {
    let symbol = prompt("Digite o símbolo da ação (ex: AAPL para Apple):");
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
            let quantity = prompt("Quantidade:");
            if (!quantity) return; // Exit if user cancels

            let purchasePrice = parseFloat(prompt("Preço de compra por ação:"));
            if (isNaN(purchasePrice)) return; // Exit if input is not a number

            let table = document.getElementById("portfolioTable").getElementsByTagName('tbody')[0];
            let row = table.insertRow();
            let currentPrice = parseFloat(data.price);
            let totalPurchase = purchasePrice * parseFloat(quantity);
            let totalCurrent = currentPrice * parseFloat(quantity);
            let marginValue = totalCurrent - totalPurchase;
            let marginPercentage = ((marginValue / totalPurchase) * 100).toFixed(2);

            row.innerHTML = `
        <td>${symbol}</td>
        <td>${sector}</td>
        <td>${quantity}</td>
        <td>${purchasePrice.toFixed(2)}</td>
        <td>${currentPrice.toFixed(2)}</td>
        <td>${totalPurchase.toFixed(2)}</td>
        <td>${marginValue.toFixed(2)}</td>
        <td>${marginPercentage}%</td>
        <td></td>
        <td><button onclick="removeStock(this)">🗑️</button></td>
    `;

    updatePortfolioPercentages();
        }
    })
    .catch(error => {
        console.error('Erro ao obter os dados:', error);
    });
});

function removeStock(button) {
    button.closest('tr').remove();
    updatePortfolioPercentages();
}

// Função para fechar a modal
function closeModal() {
    document.getElementById("stockInfoModal").style.display = "none";
}


function savePortfolio() {
    let table = document.getElementById("portfolioTable");
    let rows = Array.from(table.getElementsByTagName('tbody')[0].rows);
    let portfolio = rows.map(row => ({
        symbol: row.cells[0].innerHTML,
        quantity: parseFloat(row.cells[1].innerHTML),
        purchase_price: parseFloat(row.cells[2].innerHTML)
    }));

    fetch('/save_portfolio', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(portfolio)
    })
    .then(response => response.json())
    .then(data => {
        alert(data.message);
    })
    .catch(error => {
        console.error('Error saving portfolio:', error);
    });
}


function loadPortfolio() {
    fetch('/load_portfolio')
    .then(response => response.json())
    .then(data => {
        let table = document.getElementById("portfolioTable").getElementsByTagName('tbody')[0];
        table.innerHTML = ''; // Clear existing rows
        data.forEach(stock => {
            let row = table.insertRow();
            row.innerHTML = `
                <td>${stock.symbol}</td>
                <td>${stock.quantity}</td>
                <td>${stock.purchase_price.toFixed(2)}</td>
                <td>-</td>
                <td>${(stock.quantity * stock.purchase_price).toFixed(2)}</td>
                <td>-</td>
                <td>-</td>
                <td>-</td>
                <td><button onclick="removeStock(this)">🗑️</button></td>
            `;
        });
        updatePortfolioPercentages();
    })
    .catch(error => {
        console.error('Error loading portfolio:', error);
    });
}

// Initial update when the page loads
document.addEventListener('DOMContentLoaded', updatePortfolioPercentages);