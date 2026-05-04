// ════════════════════════════════════════════════════════
// 🐕 PERROBOTILLO DASHBOARD - CYBERPUNK EDITION
// JavaScript App - Real-time Updates
// ════════════════════════════════════════════════════════

// Configuration
const CONFIG = {
    API_URL: '/api/data',
    PRICES_URL: '/api/prices',
    REFRESH_INTERVAL: 10000, // 10 seconds for main data
    PRICES_INTERVAL: 60000,  // 60 seconds for prices
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
    
    // Load prices FIRST so they're available for slots
    loadPrices().then(() => {
        console.log('✅ Prices loaded, now loading main data...');
        loadData();
    });
    
    // Then refresh on intervals
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
        
        updatePortfolio(data);
        // Prices should be available from /api/data endpoint
const pricesCount = data.prices ? Object.keys(data.prices).length : 0;
if (pricesCount > 0) {
    console.log(`✅ Prices available: ${pricesCount} pairs`);
} else {
    console.warn('⚠️ No prices in data object, prices object:', data.prices);
}
updateSlots(data);
        updateSystemStatus(data);
        updateTradesTable(data);
        updateTimestamp(data.timestamp);
        
        // Debug: Show available price keys
const priceKeys = data.prices ? Object.keys(data.prices).filter(k => /^(BTC|ETH|BNB|SOL|LINK|XRP|AVAX)USDT/.test(k)) : [];
console.log('💰 Available price keys for our coins:', priceKeys);

console.log('✅ Data updated:', new Date(data.timestamp).toLocaleTimeString());
    } catch (error) {
        console.error('❌ Error loading data:', error);
    }
}

async function loadPrices() {
    try {
        // Fetch 24h ticker data from Binance directly (includes price AND 24h change)
        const response = await fetch('https://api.binance.com/api/v3/ticker/24hr');
        const tickers = await response.json();
        
        // Convert to format expected by updatePrices
        const prices = {};
        const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
        
        coins.forEach(coin => {
            const ticker = tickers.find(t => t.symbol === `${coin}USDT`);
            if (ticker) {
                prices[`${coin}USDT`] = ticker.lastPrice;
                // Store 24h change percentage
                prices[`${coin}USDT_change`] = parseFloat(ticker.priceChangePercent);
            }
        });
        
        updatePrices(prices);
    } catch (error) {
        console.error('❌ Error loading prices:', error);
        // Don't clear prices on error - keep last known values
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
    
    // P&L 24h - Calculate from daily_pnl using .pnl field
    let totalPnl = 0;
    const dailyPnl = data.daily_pnl || {};
    
    // Sum all coins P&L
    Object.values(dailyPnl).forEach(coin => {
        const coinPnl = parseFloat(coin.pnl || 0);
        totalPnl += coinPnl;
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
            
            const entryPrice = parseFloat(slot.entryPrice) || 0;
            const currentPrice = getCurrentPrice(coin, data.prices);
            const tp1 = parseFloat(slot.tp1) || 0;
            const tp2 = parseFloat(slot.tp2) || 0;
            const tp3 = parseFloat(slot.tp3) || 0;
            
            // Debug logging for price issues
            if (currentPrice === 0 && slot.status === 'ACTIVE') {
                console.warn(`⚠️ ${coin} Slot ${slot.slotId}: currentPrice is 0!`, {
                    entryPrice,
                    tp1,
                    tp2,
                    tp3,
                    pricesAvailable: Object.keys(data.prices || {}).length
                });
            }
            
            // Calculate progress to NEXT target (not always TP1)
            let targetPrice = tp1;
            let targetName = 'TP1';
            
            if (slot.tp1Done) {
                targetPrice = tp2;
                targetName = 'TP2';
            }
            if (slot.tp2Done) {
                targetPrice = tp3;
                targetName = 'TP3';
            }
            
            let progress = 0;
            if (entryPrice > 0 && targetPrice > 0 && currentPrice > 0) {
                progress = Math.min(100, ((currentPrice - entryPrice) / (targetPrice - entryPrice)) * 100);
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
    const chartsGrid = document.getElementById('chartsGrid');
    
    // Don't clear prices if data is empty/invalid - keep last known values
    if (!prices || Object.keys(prices).length === 0) {
        console.log('⚠️ No price data received, keeping last values');
        return;
    }
    
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    let html = '';
    
    coins.forEach(coin => {
        const symbol = `${coin}USDT`;
        const priceData = prices[symbol];
        const changeData = prices[`${symbol}_change`];
        
        if (priceData) {
            const price = parseFloat(priceData);
            const change = changeData || 0;
            const changeClass = change >= 0 ? 'positive' : 'negative';
            const changeColor = change >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
            
            html += `
                <div class="price-card">
                    <div class="price-header">
                        <div class="price-coin">${coin}</div>
                        <div class="price-change ${changeClass}" style="color: ${changeColor}">
                            ${change >= 0 ? '+' : ''}${change.toFixed(2)}%
                        </div>
                    </div>
                    <div class="price-value">$${price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</div>
                </div>
            `;
        } else {
            // Show placeholder if price data missing
            html += `
                <div class="price-card">
                    <div class="price-header">
                        <div class="price-coin">${coin}</div>
                        <div class="price-change" style="color: var(--text-secondary)">--</div>
                    </div>
                    <div class="price-value" style="color: var(--text-secondary)">$--.--</div>
                </div>
            `;
        }
    });
    
    chartsGrid.innerHTML = html;
}

function updateSystemStatus(data) {
    const system = data.system;
    
    // API Binance - Show checkmark if online
    const apiStatus = document.getElementById('apiStatus');
    if (system.api_binance === 'ok') {
        apiStatus.textContent = '✅';
        apiStatus.title = 'Binance API Online';
    } else if (system.api_binance === 'error') {
        apiStatus.textContent = '❌';
        apiStatus.title = 'Binance API Offline';
    } else {
        apiStatus.textContent = '⏳';
        apiStatus.title = 'Checking...';
    }
    
    // IP Whitelist - Show checkmark + IP
    const ipStatus = document.getElementById('ipStatus');
    if (system.ip_whitelist && system.ip_whitelist !== 'error' && system.ip_whitelist !== 'warning') {
        // It's an IP address
        ipStatus.textContent = `✅ ${system.ip_whitelist}`;
        ipStatus.title = 'IP Whitelist Configured';
    } else if (system.ip_whitelist === 'warning') {
        ipStatus.textContent = '⚠️';
        ipStatus.title = 'IP Whitelist Warning';
    } else {
        ipStatus.textContent = '❌';
        ipStatus.title = 'IP Whitelist Not Configured';
    }
    
    // Gateway - Show checkmark if online
    const gatewayStatus = document.getElementById('gatewayStatus');
    if (system.gateway === 'ok') {
        gatewayStatus.textContent = '✅';
        gatewayStatus.title = 'Gateway Online';
    } else if (system.gateway === 'error') {
        gatewayStatus.textContent = '❌';
        gatewayStatus.title = 'Gateway Offline';
    } else {
        gatewayStatus.textContent = '⏳';
        gatewayStatus.title = 'Checking...';
    }
}

function updateTradesTable(data) {
    const history = data.history;
    const trades = history.trades || [];
    const tbody = document.getElementById('tradesTableBody');
    const tableContainer = document.querySelector('.trades-table-container');
    
    // Sort trades by timestamp (most recent first)
    const sortedTrades = [...trades].sort((a, b) => {
        return new Date(b.timestamp) - new Date(a.timestamp);
    });
    
    // Show only first 10 by default
    const initialDisplay = 10;
    const tradesToShow = sortedTrades.slice(0, initialDisplay);
    
    if (tradesToShow.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No trades yet</td></tr>';
        // Remove any existing "View More" button
        const existingBtn = document.getElementById('viewMoreBtn');
        if (existingBtn) existingBtn.remove();
        return;
    }
    
    let html = '';
    tradesToShow.forEach(trade => {
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
    
    // Add "View More" button if there are more trades
    const existingBtn = document.getElementById('viewMoreBtn');
    if (existingBtn) existingBtn.remove();
    
    if (sortedTrades.length > initialDisplay) {
        const viewMoreBtn = document.createElement('button');
        viewMoreBtn.id = 'viewMoreBtn';
        viewMoreBtn.className = 'cyber-button';
        viewMoreBtn.textContent = `📊 Ver más (${sortedTrades.length - initialDisplay} trades adicionales)`;
        viewMoreBtn.onclick = () => showAllTrades(sortedTrades);
        
        tableContainer.appendChild(viewMoreBtn);
    }
}

function showAllTrades(sortedTrades) {
    const tbody = document.getElementById('tradesTableBody');
    
    let html = '';
    sortedTrades.forEach(trade => {
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
    
    // Remove "View More" button
    const viewMoreBtn = document.getElementById('viewMoreBtn');
    if (viewMoreBtn) viewMoreBtn.remove();
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
    
    // Method 1: Direct lookup
    let priceData = prices[symbol];
    if (priceData) {
        const price = typeof priceData === 'string' ? parseFloat(priceData) : priceData;
        if (!isNaN(price) && price > 0) {
            console.log(`✅ ${coin} price found (direct): $${price}`);
            return price;
        }
    }
    
    // Method 2: Case-insensitive search
    for (const [key, value] of Object.entries(prices)) {
        if (key.toUpperCase() === symbol.toUpperCase()) {
            const price = typeof value === 'string' ? parseFloat(value) : value;
            if (!isNaN(price) && price > 0) {
                console.log(`✅ ${coin} price found (case-insensitive): $${price}`);
                return price;
            }
        }
    }
    
    // Method 3: Search for exact match with different formats
    const variants = [
        symbol,
        symbol.toLowerCase(),
        symbol.toUpperCase(),
        `${coin.toLowerCase()}usdt`,
        `${coin.toUpperCase()}USDT`
    ];
    
    for (const variant of variants) {
        if (prices[variant]) {
            const price = typeof prices[variant] === 'string' ? parseFloat(prices[variant]) : prices[variant];
            if (!isNaN(price) && price > 0) {
                console.log(`✅ ${coin} price found (variant ${variant}): $${price}`);
                return price;
            }
        }
    }
    
    // If nothing found, log available keys for debugging
    const coinKeys = Object.keys(prices).filter(k => k.includes(coin));
    console.warn(`❌ ${coin} price NOT found. Available variants:`, coinKeys.slice(0, 5));
    
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
