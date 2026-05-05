// ════════════════════════════════════════════════════════
// 🐕 PERROBOTILLO DASHBOARD - CYBERPUNK EDITION
// JavaScript App - Real-time Updates
// ════════════════════════════════════════════════════════

// Configuration
const CONFIG = {
    API_URL: '/api/status',
    PRICES_URL: '/api/prices',
    REFRESH_INTERVAL: 30000,
    PRICES_INTERVAL: 60000,
    MAX_TRADES_DISPLAY: 10
};

// State
let lastData = null;
let lastPrices = {};

// ════════════════════════════════════════════════════════
// INITIALIZATION
// ════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    console.log('🐕 Perrobotillo Dashboard - Initializing...');
    loadPrices().then(() => {
        console.log('✅ Prices loaded, now loading main data...');
        loadData();
    });
    setInterval(loadData, CONFIG.REFRESH_INTERVAL);
    setInterval(loadPrices, CONFIG.PRICES_INTERVAL);
});

// ════════════════════════════════════════════════════════
// DATA LOADING
// ════════════════════════════════════════════════════════

async function loadData() {
    try {
        const response = await fetch(CONFIG.API_URL);
        const data = await response.json();
        lastData = data;
        
        updatePortfolio({ portfolio: data.portfolio, history: data.history, pnl: data.pnl });
        updateSlots({ tradeStates: data.tradeStates || {}, prices: lastPrices });
        updateSystemStatus({ market_mode: data.market_mode });
        updateTradesTable({ history: data.history });
        updateTimestamp(data.timestamp);
        
        console.log('✅ Data updated:', new Date(data.timestamp).toLocaleTimeString());
    } catch (error) {
        console.error('❌ Error loading data:', error);
    }
}

async function loadPrices() {
    try {
        const response = await fetch(CONFIG.PRICES_URL);
        const prices = await response.json();
        lastPrices = prices;
        updatePrices(prices);
    } catch (error) {
        console.error('❌ Error loading prices:', error);
    }
}

function getCurrentPrice(coin, prices) {
    const symbol = `${coin}USDT`;
    return prices[symbol] ? parseFloat(prices[symbol]) : 0;
}

// ════════════════════════════════════════════════════════
// UPDATE FUNCTIONS
// ════════════════════════════════════════════════════════

function updatePortfolio(data) {
    const portfolio = data.portfolio || {};
    const history = data.history || {};
    const pnl = data.pnl || {};
    
    const totalValue = portfolio.value || 0;
    animateValue('totalPortfolio', totalValue, '$');
    document.getElementById('totalPortfolioMXN').textContent = 
        `$${(portfolio.value_mx || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MXN`;
    
    const totalPnl = pnl['24h'] || 0;
    const pnlPercent24h = pnl['24h_percent'] || 0;
    
    const pnlElement = document.getElementById('pnl24h');
    const pnlPercent = document.getElementById('pnlPercent');
    const totalPnlElement = document.getElementById('totalPnl24h');
    
    pnlElement.textContent = `${totalPnl >= 0 ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`;
    pnlElement.style.color = totalPnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    
    pnlPercent.textContent = `${pnlPercent24h >= 0 ? '+' : ''}${pnlPercent24h.toFixed(2)}%`;
    pnlPercent.style.color = pnlPercent24h >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    
    if (totalPnlElement) {
        const historicalPnl = history.net_pnl || 0;
        totalPnlElement.textContent = `${historicalPnl >= 0 ? '+' : ''}$${Math.abs(historicalPnl).toFixed(2)}`;
        totalPnlElement.style.color = historicalPnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    }
    
    document.getElementById('winRate').textContent = `${(history.win_rate || 0).toFixed(2)}%`;
    document.getElementById('totalTrades').textContent = history.total_trades || 0;
    
    const netPnlElement = document.getElementById('netPnl');
    if (netPnlElement) {
        netPnlElement.textContent = `${(history.net_pnl || 0) >= 0 ? '+' : ''}$${Math.abs(history.net_pnl || 0).toFixed(2)}`;
    }
}

function updateSlots(data) {
    const slotsGrid = document.getElementById('slotsGrid');
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    const tradeStates = data.tradeStates || {};
    const prices = data.prices || lastPrices;
    
    if (!tradeStates || Object.keys(tradeStates).length === 0) {
        return;
    }
    
    let html = '';
    
    coins.forEach(coin => {
        const coinData = tradeStates[coin];
        if (!coinData) return;
        
        const status = coinData.status || 'READY';
        const slots = [];
        
        if (status === 'READY') {
            slots.push({ slotId: 1, status: 'READY', entryPrice: 0, tp1: 0, tp2: 0, tp3: 0, tp1Done: false, tp2Done: false, quantity: 0 });
        } else if (status === 'IN_TRADE' || status === 'TP1_HIT' || status === 'TP2_HIT') {
            slots.push({
                slotId: coinData.slotId || 1,
                status: 'ACTIVE',
                entryPrice: coinData.entryPrice || 0,
                currentPrice: coinData.currentPrice || 0,
                tp1: coinData.tp1 || 0,
                tp2: coinData.tp2 || 0,
                tp3: coinData.tp3 || 0,
                tp1Done: status === 'TP1_HIT' || status === 'TP2_HIT',
                tp2Done: status === 'TP2_HIT',
                quantity: coinData.quantity || 0
            });
        }
        
        slots.forEach(slot => {
            const statusClass = slot.status === 'ACTIVE' ? 'active' : 'ready';
            const statusText = slot.status === 'ACTIVE' ? 'IN TRADE' : 'READY';
            
            const entryPrice = parseFloat(slot.entryPrice) || 0;
            const currentPrice = getCurrentPrice(coin, prices) || slot.currentPrice || 0;
            const tp1 = parseFloat(slot.tp1) || 0;
            
            let targetPrice = tp1;
            let targetName = 'TP1';
            let progress = 0;
            
            if (slot.tp1Done) { targetPrice = slot.tp2; targetName = 'TP2'; }
            if (slot.tp2Done) { targetPrice = slot.tp3; targetName = 'TP3'; }
            
            if (entryPrice > 0 && targetPrice > 0 && currentPrice > 0) {
                progress = Math.min(100, ((currentPrice - entryPrice) / (targetPrice - entryPrice)) * 100);
            }
            
            let pnl = 0, pnlPercent = 0;
            if (entryPrice > 0 && currentPrice > 0) {
                pnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100;
                pnl = (currentPrice - entryPrice) * (slot.quantity || 0);
            }
            
            html += `
                <div class="slot-card ${statusClass}">
                    <div class="slot-header">
                        <div class="slot-coin">${coin}</div>
                        <div class="slot-id">Slot ${slot.slotId}</div>
                    </div>
                    <div class="slot-status ${statusText.toLowerCase()}">${statusText}</div>
                    
                    <div class="slot-grid-info">
                        <div class="slot-info-item">
                            <div class="slot-info-label">Entry Price</div>
                            <div class="slot-info-value">$${entryPrice.toFixed(2)}</div>
                        </div>
                        <div class="slot-info-item">
                            <div class="slot-info-label">Current Price</div>
                            <div class="slot-info-value">$${currentPrice.toFixed(2)}</div>
                        </div>
                        <div class="slot-info-item">
                            <div class="slot-info-label">P&L</div>
                            <div class="slot-info-value" style="color: ${pnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)'}">
                                ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)} (${pnlPercent >= 0 ? '+' : ''}${pnlPercent.toFixed(2)}%)
                            </div>
                        </div>
                        <div class="slot-info-item">
                            <div class="slot-info-label">TP1 Target</div>
                            <div class="slot-info-value">$${tp1.toFixed(2)}</div>
                        </div>
                    </div>
                    
                    ${slot.status === 'ACTIVE' ? `
                        <div class="tp-progress-container">
                            <div class="tp-label">
                                <span>Progress to ${targetName}</span>
                                <span>${Math.min(100, progress).toFixed(1)}%</span>
                            </div>
                            <div class="tp-bar ${pnl >= 0 ? 'profit' : 'loss'}">
                                <div class="tp-fill" style="width: ${Math.min(100, progress).toFixed(1)}%"></div>
                            </div>
                        </div>
                    ` : ''}
                </div>
            `;
        });
    });
    
    slotsGrid.innerHTML = html;
}

function updatePrices(prices) {
    const chartsGrid = document.getElementById('chartsGrid');
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    
    if (!prices || Object.keys(prices).length === 0) return;
    
    let html = '';
    
    coins.forEach(coin => {
        const symbol = `${coin}USDT`;
        const priceData = prices[symbol];
        
        if (priceData) {
            const price = parseFloat(priceData);
            const change = prices[`${symbol}_change`] || 0;
            const changeColor = change >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
            
            html += `
                <div class="price-card">
                    <div class="price-header">
                        <div class="price-coin">${coin}</div>
                        <div class="price-change" style="color: ${changeColor}">
                            ${change >= 0 ? '+' : ''}${change.toFixed(2)}%
                        </div>
                    </div>
                    <div class="price-value">$${price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                </div>
            `;
        }
    });
    
    chartsGrid.innerHTML = html;
}

function updateSystemStatus(data) {
    const marketMode = data.market_mode || {};
    
    const modeElement = document.getElementById('marketMode');
    if (modeElement) {
        modeElement.textContent = marketMode.MARKET_MODE || 'LATERAL';
    }
    
    const configElement = document.getElementById('marketConfig');
    if (configElement) {
        const tp1 = marketMode.TP1 || '2.5';
        const tp2 = marketMode.TP2 || '5.0';
        const tp3 = marketMode.TP3 || '7.0';
        const sl = marketMode.SL || '5.0';
        configElement.textContent = `TP1: ${tp1}% | TP2: ${tp2}% | TP3: ${tp3}% | SL: ${sl}%`;
    }
}

function updateTradesTable(data) {
    const history = data.history || {};
    const trades = history.trades || [];
    const tbody = document.getElementById('tradesTableBody');
    
    const sortedTrades = [...trades].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    const tradesToShow = sortedTrades.slice(0, CONFIG.MAX_TRADES_DISPLAY);
    
    if (tradesToShow.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No trades yet</td></tr>';
        return;
    }
    
    let html = '';
    tradesToShow.forEach(trade => {
        const pnlClass = trade.pnlUSDT >= 0 ? 'profit' : 'loss';
        const pnlColor = trade.pnlUSDT >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
        const closeType = trade.closeType || 'UNKNOWN';
        
        html += `
            <tr>
                <td>#${trade.id}</td>
                <td><strong>${trade.symbol}</strong></td>
                <td>${trade.type}</td>
                <td>$${(trade.entryPrice || 0).toFixed(2)}</td>
                <td>$${(trade.exitPrice || 0).toFixed(2)}</td>
                <td><span class="status-badge ${pnlClass}">${closeType}</span></td>
                <td style="color: ${pnlColor}">${trade.pnlUSDT >= 0 ? '+' : ''}$${(trade.pnlUSDT || 0).toFixed(2)}</td>
                <td>${new Date(trade.timestamp).toLocaleDateString()}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

function updateTimestamp(timestamp) {
    const el = document.getElementById('lastUpdate');
    if (el && timestamp) {
        el.textContent = new Date(timestamp).toLocaleTimeString();
    }
}

function animateValue(id, end, prefix = '') {
    const el = document.getElementById(id);
    if (!el) return;
    
    const start = parseFloat(el.textContent.replace(/[^0-9.]/g, '')) || 0;
    const duration = 1000;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const value = start + (end - start) * progress;
        el.textContent = `${prefix}${value.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}
