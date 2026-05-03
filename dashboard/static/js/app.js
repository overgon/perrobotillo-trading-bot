// ════════════════════════════════════════════════════════
// 🐕 PERROBOTILLO DASHBOARD - CYBERPUNK EDITION
// JavaScript App - Real-time Updates
// ════════════════════════════════════════════════════════

// Configuration
const CONFIG = {
    API_URL: '/api/data',
    PRICES_URL: '/api/prices',
    REFRESH_INTERVAL: 10000, // 10 seconds
    MAX_TRADES_DISPLAY: 10
};

// State
let lastData = null;
let alertPlayed = false;

// ════════════════════════════════════════════════════════
// INITIALIZATION
// ════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    console.log('🐕 Perrobotillo Dashboard - Initializing...');
    loadData();
    setInterval(loadData, CONFIG.REFRESH_INTERVAL);
    setInterval(loadPrices, 5000); // Prices update faster
});

// ════════════════════════════════════════════════════════
// DATA LOADING
// ════════════════════════════════════════════════════════

async function loadData() {
    try {
        const response = await fetch(CONFIG.API_URL);
        const data = await response.json();
        lastData = data;
        
        updatePortfolio(data);
        updateSlots(data);
        updateSystemStatus(data);
        updateTradesTable(data);
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
        updatePrices(prices);
    } catch (error) {
        console.error('❌ Error loading prices:', error);
    }
}

// ════════════════════════════════════════════════════════
// UPDATE FUNCTIONS
// ════════════════════════════════════════════════════════

function updatePortfolio(data) {
    const portfolio = data.portfolio;
    
    // Total Portfolio
    animateValue('totalPortfolio', portfolio.total_usdt, '$');
    document.getElementById('totalPortfolioMXN').textContent = 
        `$${portfolio.total_mxn.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MXN`;
    
    // P&L 24h - Calculate from daily_pnl
    let totalPnl = 0;
    Object.values(data.daily_pnl || {}).forEach(coin => {
        totalPnl += parseFloat(coin.profitUSDT || 0) + parseFloat(coin.lossUSDT || 0);
    });
    
    const pnlElement = document.getElementById('pnl24h');
    const pnlPercent = document.getElementById('pnlPercent');
    
    pnlElement.textContent = `${totalPnl >= 0 ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`;
    pnlElement.style.color = totalPnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    
    const pnlPercentValue = portfolio.total_usdt > 0 ? (totalPnl / portfolio.total_usdt) * 100 : 0;
    pnlPercent.textContent = `${pnlPercentValue >= 0 ? '+' : ''}${pnlPercentValue.toFixed(2)}%`;
    pnlPercent.style.color = pnlPercentValue >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    
    // Win Rate & Trades
    const history = data.history;
    document.getElementById('winRate').textContent = `${(history.winRate || 0).toFixed(2)}%`;
    document.getElementById('winLoss').textContent = 
        `${history.totalWins || 0}W / ${history.totalLosses || 0}L`;
    document.getElementById('totalTrades').textContent = history.totalTrades || 0;
    document.getElementById('netPnl').textContent = 
        `${(history.netPnLUSDT || 0) >= 0 ? '+' : ''}$${Math.abs(history.netPnLUSDT || 0).toFixed(2)}`;
}

function updateSlots(data) {
    const slotsGrid = document.getElementById('slotsGrid');
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    
    let html = '';
    
    coins.forEach(coin => {
        const coinData = data.coins[coin];
        if (!coinData || coinData.error) {
            html += `
                <div class="slot-card">
                    <div class="slot-header">
                        <div class="slot-coin">${coin}</div>
                        <div class="slot-id">--</div>
                    </div>
                    <div class="slot-status ready">DATA UNAVAILABLE</div>
                </div>
            `;
            return;
        }
        
        const slots = coinData.slots || [];
        slots.forEach(slot => {
            const statusClass = slot.status === 'ACTIVE' ? 'active' : 
                               slot.status === 'READY' ? 'ready' : 'loss';
            const statusText = slot.status || 'UNKNOWN';
            
            const entryPrice = slot.entryPrice || 0;
            const currentPrice = getCurrentPrice(coin, data.prices);
            const tp1 = slot.tp1 || 0;
            const tp2 = slot.tp2 || 0;
            const tp3 = slot.tp3 || 0;
            
            // Calculate progress to TP1
            let progress = 0;
            if (entryPrice > 0 && tp1 > 0 && currentPrice > 0) {
                progress = Math.min(100, ((currentPrice - entryPrice) / (tp1 - entryPrice)) * 100);
            }
            
            // Calculate P&L
            let pnl = 0;
            let pnlPercent = 0;
            if (entryPrice > 0 && currentPrice > 0) {
                pnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100;
                pnl = (currentPrice - entryPrice) * (slot.quantity || 0);
            }
            
            html += `
                <div class="slot-card ${statusClass.toLowerCase()}">
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
                                <span>Progress to TP1</span>
                                <span>${Math.min(100, progress).toFixed(1)}%</span>
                            </div>
                            <div class="tp-bar">
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
    // Prices are updated within slots
    console.log('Prices updated:', prices);
}

function updateSystemStatus(data) {
    const system = data.system;
    
    document.getElementById('apiStatus').textContent = system.api_binance || 'Unknown';
    document.getElementById('ipStatus').textContent = system.ip_whitelist || 'Unknown';
    document.getElementById('gatewayStatus').textContent = system.gateway || 'Unknown';
}

function updateTradesTable(data) {
    const history = data.history;
    const trades = history.trades || [];
    const tbody = document.getElementById('tradesTableBody');
    
    if (trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No trades yet</td></tr>';
        return;
    }
    
    let html = '';
    trades.slice(0, CONFIG.MAX_TRADES_DISPLAY).forEach(trade => {
        const pnlClass = trade.pnlUSDT >= 0 ? 'profit' : 'loss';
        const pnlColor = trade.pnlUSDT >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
        const closeType = trade.closeType || 'UNKNOWN';
        const typeClass = closeType.includes('TP') ? 'active' : closeType.includes('SL') ? 'loss' : 'ready';
        
        html += `
            <tr>
                <td>#${trade.id}</td>
                <td><strong>${trade.symbol}</strong></td>
                <td>${trade.type}</td>
                <td>$${trade.entryPrice.toFixed(2)}</td>
                <td>$${trade.exitPrice.toFixed(2)}</td>
                <td style="color: ${pnlColor}">${trade.pnlUSDT >= 0 ? '+' : ''}$${trade.pnlUSDT.toFixed(2)}</td>
                <td><span class="slot-status ${typeClass}">${closeType}</span></td>
                <td>${new Date(trade.timestamp).toLocaleDateString()}</td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

function updateTimestamp(timestamp) {
    const date = new Date(timestamp);
    document.getElementById('lastUpdate').textContent = date.toLocaleTimeString();
}

// ════════════════════════════════════════════════════════
// HELPER FUNCTIONS
// ════════════════════════════════════════════════════════

function getCurrentPrice(coin, prices) {
    const symbol = `${coin}USDT`;
    const priceData = prices[symbol];
    if (priceData) {
        return parseFloat(priceData.replace('$', ''));
    }
    return 0;
}

function animateValue(elementId, value, prefix = '') {
    const element = document.getElementById(elementId);
    const start = parseFloat(element.textContent.replace(/[^0-9.-]+/g, '')) || 0;
    const end = value;
    const duration = 1000;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        // Ease out quart
        const ease = 1 - Math.pow(1 - progress, 4);
        
        const current = start + (end - start) * ease;
        element.textContent = `${prefix}${current.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

// ════════════════════════════════════════════════════════
// ALERT SYSTEM
// ════════════════════════════════════════════════════════

function checkAlerts(data) {
    // Check if any slot is very close to TP (within 0.5%)
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    
    coins.forEach(coin => {
        const coinData = data.coins[coin];
        if (!coinData || !coinData.slots) return;
        
        coinData.slots.forEach(slot => {
            if (slot.status !== 'ACTIVE') return;
            
            const entryPrice = slot.entryPrice || 0;
            const currentPrice = getCurrentPrice(coin, data.prices);
            const tp1 = slot.tp1 || 0;
            
            if (entryPrice > 0 && tp1 > 0 && currentPrice > 0) {
                const distance = ((tp1 - currentPrice) / currentPrice) * 100;
                
                if (distance > 0 && distance < 0.5) {
                    // Very close to TP!
                    triggerAlert(coin, slot.slotId, distance);
                }
            }
        });
    });
}

function triggerAlert(coin, slotId, distance) {
    const alertKey = `${coin}-${slotId}-${new Date().toDateString()}`;
    
    // Don't alert multiple times for the same slot
    if (alertPlayed) return;
    
    // Play sound
    const audio = document.getElementById('alertSound');
    if (audio) {
        audio.play().catch(e => console.log('Audio play failed:', e));
    }
    
    // Visual alert (could add a toast notification here)
    console.log(`🚨 ALERT: ${coin} Slot ${slotId} is ${distance.toFixed(2)}% from TP!`);
    
    alertPlayed = true;
    setTimeout(() => { alertPlayed = false; }, 60000); // Cooldown 1 minute
}
