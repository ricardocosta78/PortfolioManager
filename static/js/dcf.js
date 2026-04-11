document.getElementById('dcfForm').addEventListener('submit', function(event) {
    event.preventDefault();

    const ticker = document.getElementById('stockSymbol').value;
    
    fetch('/api/calculate_valuation', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ symbol: ticker }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            document.getElementById('resultado').innerHTML = `<p class="error">Error: ${data.error}</p>`;
        } else {
            const resultado = `
                <div class="result-section">
                    <h3>Company Overview</h3>
                    <div class="result-item">
                        <span class="result-label">Company Name:</span>
                        <span class="result-value">${data.company_name}</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Current Price:</span>
                        <span class="result-value">$${data.current_price.toFixed(2)}</span>
                    </div>
                </div>

                <div class="result-section">
                    <h3>DCF Valuation</h3>
                    <div class="result-item">
                        <span class="result-label">DCF Value per Share:</span>
                        <span class="result-value">$${data.dcf_value_per_share.toFixed(2)}</span>
                    </div>
                </div>

                <div class="result-section">
                    <h3>Calculation Details</h3>
                    <div class="result-item">
                        <span class="result-label">WACC:</span>
                        <span class="result-value">${(data.wacc * 100).toFixed(2)}%</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Growth Rate:</span>
                        <span class="result-value">${(data.growth_rate * 100).toFixed(2)}%</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Terminal Growth Rate:</span>
                        <span class="result-value">${(data.terminal_growth_rate * 100).toFixed(2)}%</span>
                    </div>
                    <div class="result-item">
                        <span class="result-label">Terminal Value:</span>
                        <span class="result-value">$${data.terminal_value.toLocaleString()}</span>
                    </div>
                </div>

                <div class="result-section">
                    <h3>Cash Flow Projections</h3>
                    <pre>${data.cash_flow_projections}</pre>
                </div>

                <div class="result-section">
                    <h3>Additional Details</h3>
                    <pre>${data.dcf_details}</pre>
                </div>
            `;
            document.getElementById('resultado').innerHTML = resultado;
        }
    })
    .catch(error => {
        document.getElementById('resultado').innerHTML = `<p class="error">Network error: ${error.message}</p>`;
    });
});