// ════════════════════════════════════════════════════════
// 🐕 PERROBOTILLO DASHBOARD - CYBERPUNK EDITION
// JavaScript App - Real-time Updates
// ════════════════════════════════════════════════════════
const CONFIG = {
    API_URL: '/api/status',
    PRICES_URL: '/api/prices',
    REFRESH_INTERVAL: 300000,
    PRICES_INTERVAL: 300000,
    MAX_TRADES_DISPLAY: 10
};

let lastData = null;
let lastPrices = {};
let countdownInterval = null;
let showAllTrades = false;  // Show only 10 by default

// ════════════════════════════════════════════════════════
// 🔊 SOUND EFFECTS
// ════════════════════════════════════════════════════════

const cashRegisterSound = new Audio('/static/sounds/cash-register.wav');
cashRegisterSound.preload = 'auto';

const stopLossSound = new Audio('/static/sounds/stop-loss.mp3');
stopLossSound.preload = 'auto';

function playCashRegister() {
    cashRegisterSound.currentTime = 0;
    cashRegisterSound.volume = 1.0;
    const playPromise = cashRegisterSound.play();
    if (playPromise) {
        playPromise.then(() => console.log('💰 CASH REGISTER! TP HIT! 🔔'))
            .catch(error => console.log('⚠️ Sound play failed:', error));
    }
}

function playStopLoss() {
    stopLossSound.currentTime = 0;
    stopLossSound.volume = 1.0;
    const playPromise = stopLossSound.play();
    if (playPromise) {
        playPromise.then(() => console.log('🛑 STOP LOSS HIT! 💀'))
            .catch(error => console.log('⚠️ Sound play failed:', error));
    }
}

document.addEventListener('DOMContentLoaded', () => {
    console.log('🐕 Perrobotillo Dashboard - Initializing...');
    loadPrices().then(() => {
        loadData();
    });
    setInterval(loadData, CONFIG.REFRESH_INTERVAL);
    setInterval(loadPrices, CONFIG.PRICES_INTERVAL);
});

async function loadData(forceHistory = false) {
    try {
        const url = new URL(CONFIG.API_URL, window.location.origin);
        if (forceHistory) url.searchParams.set('_hl', Date.now());
        const response = await fetch(url.toString());
        const data = await response.json();
        lastData = data;

        updatePortfolio({ portfolio: data.portfolio, history: data.history, pnl: data.pnl });
        updateSlots({ tradeStates: data.tradeStates || {}, prices: lastPrices });
        updateGrid(data);
        updateSystemStatus({ market_mode: data.market_mode, system: data.system });
        updateAutoAdjust({ auto_adjust: data.auto_adjust, market_mode: data.market_mode });
        updateCircuitBreakerStatus(data);
        updateTradesTable({ history: data.history });
        updateTimestamp(data.timestamp);

        if (window.onDashboardDataUpdated) {
            window.onDashboardDataUpdated();
        }

        console.log('✅ Data updated:', new Date(data.timestamp).toLocaleTimeString());
    } catch (error) {
        console.error('❌ Error loading data:', error);
    }
}

async function loadPrices() {
    try {
        console.log('📊 Loading prices...');
        const response = await fetch(CONFIG.PRICES_URL, { 
            method: 'GET',
            headers: { 'Accept': 'application/json' },
            timeout: 10000
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const prices = await response.json();
        lastPrices = prices;
        console.log('✅ Prices loaded:', Object.keys(prices).length, 'coins');
        updatePrices(prices);
    } catch (error) {
        console.log('⚠️ Prices fetch failed (will retry):', error.message);
        // No loguear como error crítico - se reintenta en 60s
    }
}

function getCurrentPrice(coin, prices) {
    // prices[coin] es un objeto: {price: 80000, change_24h: 0.5}
    // La API devuelve prices["BTC"], NO prices["BTCUSDT"]
    const priceData = prices[coin];
    
    if (priceData && priceData.price) {
        return parseFloat(priceData.price);
    }
    
    return 0;
}

function updatePortfolio(data) {
    const portfolio = data.portfolio || {};
    const history = data.history || {};
    const pnl = data.pnl || {};
    const pnlByCoin = pnl.by_coin || {};
    
    const totalValue = portfolio.value || 0;
    animateValue('totalPortfolio', totalValue, '$');
    document.getElementById('totalPortfolioMXN').textContent = 
        `$${(portfolio.value_mx || 0).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})} MXN`;
    
    const totalPnl = pnl['24h'] || 0;
    const pnlPercent24h = pnl['24h_percent'] || 0;
    
    const pnlElement = document.getElementById('pnl24h');
    const pnlPercent = document.getElementById('pnlPercent');
    const totalPnlElement = document.getElementById('totalPnl24h');
    
    if (pnlElement) {
        pnlElement.textContent = `${totalPnl >= 0 ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`;
        pnlElement.style.color = totalPnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    }
    
    if (pnlPercent) {
        pnlPercent.textContent = `${pnlPercent24h >= 0 ? '+' : ''}${pnlPercent24h.toFixed(2)}%`;
        pnlPercent.style.color = pnlPercent24h >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    }
    
    if (totalPnlElement) {
        const historicalPnl = history.net_pnl || 0;
        totalPnlElement.textContent = `${historicalPnl >= 0 ? '+' : ''}$${Math.abs(historicalPnl).toFixed(2)}`;
        totalPnlElement.style.color = historicalPnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    }
    
    const winRateEl = document.getElementById('winRate');
    if (winRateEl) winRateEl.textContent = `${(history.win_rate || 0).toFixed(2)}%`;
    
    const totalTradesEl = document.getElementById('totalTrades');
    if (totalTradesEl) totalTradesEl.textContent = history.total_trades || 0;
    
    const netPnlElement = document.getElementById('netPnl');
    if (netPnlElement) {
        netPnlElement.textContent = `${(history.net_pnl || 0) >= 0 ? '+' : ''}$${Math.abs(history.net_pnl || 0).toFixed(2)}`;
    }
    
    // Update P&L by coin
    updatePnlByCoin(pnlByCoin);
}

function updateSlots(data) {
    const slotsGrid = document.getElementById('slotsGrid');
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    const tradeStates = data.tradeStates || {};
    const prices = data.prices || lastPrices;
    
    console.log('🔧 Updating slots, tradeStates:', Object.keys(tradeStates).length, 'coins');
    
    // 🟠 VERIFICAR CIRCUIT BREAKER STATUS
    const circuitBreakerActive = data.circuitBreakerActive || false;
    const circuitStatus = data.circuitStatus || 'NORMAL';
    const isEmergencyMode = circuitBreakerActive && (circuitStatus === 'GLOBAL_PAUSE' || circuitStatus === 'EMERGENCY_CONSERVATIVE');
    
    if (isEmergencyMode) {
        console.log('🟠 EMERGENCY MODE ACTIVE - Circuit Breaker:', circuitStatus);
    }
    
    if (!tradeStates || Object.keys(tradeStates).length === 0) return;
    
    let html = '';
    let activeCount = 0;
    let totalCount = 0;
    
    coins.forEach(coin => {
        const coinData = tradeStates[coin];
        if (!coinData) return;
        
        const slots = coinData.slots || [];
        totalCount += slots.length;
        
        if (slots.length === 0) {
            html += `
                <div class="slot-card ready">
                    <div class="slot-header">
                        <div class="slot-coin">${coin}</div>
                        <div class="slot-id">Slot 1</div>
                    </div>
                    <div class="slot-status ready">READY</div>
                </div>
            `;
            return;
        }
        
        // Count active slots (ACTIVE status, not READY or CLOSED)
        slots.forEach(slot => {
            const status = slot.status || 'ACTIVE';
            if (status === 'ACTIVE') {
                activeCount++;
            }
        });
        
        slots.forEach(slot => {
            const status = slot.status || 'ACTIVE';
            
            // Si el slot está READY o CLOSED, mostrar tarjeta READY/PAUSE
            if (status === 'READY') {
                // 🟠 EMERGENCY MODE: READY slots también muestran naranja metálico
                const slotClass = isEmergencyMode ? 'emergency-pause' : 'ready';
                const statusIcon = isEmergencyMode ? '🟠' : '🟡';
                const statusText = isEmergencyMode ? 'PAUSED (CB)' : 'READY';
                html += `
                    <div class="slot-card ${slotClass}">
                        <div class="slot-header">
                            <div class="slot-coin">${coin}</div>
                            <div class="slot-id">Slot ${slot.slotId}</div>
                        </div>
                        <div class="slot-status ${slotClass}">${statusText} ${statusIcon}</div>
                    </div>
                `;
                return;
            }
            
            // Slots cerrados → mostrar como CLOSED_<tipo>
            if (status.startsWith('CLOSED')) {
                const closeReason = status.replace('CLOSED_', '') || 'CLOSED';
                const slotClass = 'closed';
                const statusText = `CLOSED ${closeReason} 🟢`;
                const statusIcon = '🟢';
                html += `
                    <div class="slot-card ${slotClass}">
                        <div class="slot-header">
                            <div class="slot-coin">${coin}</div>
                            <div class="slot-id">Slot ${slot.slotId}</div>
                        </div>
                        <div class="slot-status ${slotClass}">${statusText} ${statusIcon}</div>
                    </div>
                `;
                return;
            }
            
            // Slot está IN TRADE
            const entryPrice = parseFloat(slot.entryPrice) || 0;
            const currentPrice = getCurrentPrice(coin, prices) || 0;
            const tp1 = parseFloat(slot.tp1) || 0;
            const tp2 = parseFloat(slot.tp2) || 0;
            const tp3 = parseFloat(slot.tp3) || 0;
            const sl = parseFloat(slot.stopLoss) || 0;
            const quantity = parseFloat(slot.quantity) || 0;
            
            console.log(`🔍 ${coin} Slot ${slot.slotId}: entry=$${entryPrice}, current=$${currentPrice}, tp1=$${tp1}, sl=$${sl}`);
            
            // Determinar target actual basado en P&L (negativo → SL, positivo → TP)
            let pnl = 0, pnlPercent = 0;
            if (entryPrice > 0 && currentPrice > 0) {
                pnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100;
                pnl = (currentPrice - entryPrice) * quantity;
            }
            
            let targetPrice = tp1;
            let targetName = 'TP1';
            let progress = 0;
            let isLossMode = pnl < 0;
            const isClosed = status.startsWith('CLOSED');
            const isPaused = status === 'PAUSED' || status === 'PAUSE';
            
            // Solo mostrar 100% si el slot está cerrado realmente
            if (isClosed) {
                progress = 100;
                targetName = status.replace('CLOSED_', '').toUpperCase();
            } else if (isPaused) {
                progress = Math.min(100, Math.max(0, progress));
                targetName = 'PAUSED';
            } else if (isLossMode && sl > 0) {
                targetPrice = sl;
                targetName = 'SL';
                if (entryPrice > 0 && sl > 0 && sl !== entryPrice) {
                    progress = ((entryPrice - currentPrice) / (entryPrice - sl)) * 100;
                    if (progress >= 100) {
                        progress = 100;
                        targetName = 'SL HIT';
                    }
                }
            } else {
                if (slot.tp1Done && slot.tp2Done) {
                    targetPrice = tp3;
                    targetName = 'TP3';
                } else if (slot.tp1Done) {
                    targetPrice = tp2;
                    targetName = 'TP2';
                } else {
                    targetPrice = tp1;
                    targetName = 'TP1';
                }
                
                if (entryPrice > 0 && targetPrice > 0 && currentPrice > 0 && targetPrice !== entryPrice) {
                    progress = Math.min(99.9, ((currentPrice - entryPrice) / (targetPrice - entryPrice)) * 100);
                }
            }
            
            // Determinar clase según P&L (rojo para negativos, verde para positivos)
            const pnlClass = pnl >= 0 ? 'profit' : 'loss';
            const pnlIcon = pnl >= 0 ? '🟢' : '🔴';
            
            html += `
                <div class="slot-card active ${pnlClass}">
                    <div class="slot-header">
                        <div class="slot-coin">${coin}</div>
                        <div class="slot-id">Slot ${slot.slotId}</div>
                    </div>
                    <div class="slot-status in-trade ${pnlClass}">IN TRADE ${pnlIcon}</div>
                    
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
                            <div class="slot-info-label">Next Target</div>
                            <div class="slot-info-value" style="color: ${isLossMode ? 'var(--neon-red)' : 'var(--neon-blue)'}">
                                $${targetPrice.toFixed(2)} (${targetName}${isLossMode ? ' ⚠️' : ''})
                            </div>
                        </div>
                    </div>
                    
                    <div class="tp-progress-container">
                        <div class="tp-label">
                            <span>${isLossMode ? '⚠️ Distance to SL' : `Progress to ${targetName}`}</span>
                            <span>${Math.max(0, progress).toFixed(1)}%</span>
                        </div>
                        <div class="tp-bar ${isLossMode ? 'danger' : (pnl >= 0 ? 'profit' : 'loss')}">
                            <div class="tp-fill ${isLossMode ? 'danger-fill' : ''}" style="width: ${Math.max(0, progress).toFixed(1)}%"></div>
                        </div>
                    </div>
                </div>
            `;
        });
    });
    
    slotsGrid.innerHTML = html;
    
    // Update slots counter
    const counterEl = document.getElementById('slotsCounter');
    if (counterEl) {
        counterEl.textContent = `${activeCount}/21`;
    }
    
    console.log('✅ Slots updated:', `${activeCount}/21`);
}

// 🆕 GRID TRADING UPDATE FUNCTION
function updateGrid(data) {
    const gridData = data.grid;
    if (!gridData) return;
    
    // Update status badge
    const statusBadge = document.getElementById('gridStatusBadge');
    if (statusBadge) {
        const status = gridData.status || 'inactive';
        if (status === 'active') {
            statusBadge.textContent = '● ACTIVE';
            statusBadge.style.color = '#00ff00';
            statusBadge.style.background = '';
        } else if (status === 'disabled') {
            statusBadge.textContent = '● DESACTIVADO';
            statusBadge.style.color = '#ffffff';
            statusBadge.style.background = '#666';
        } else {
            statusBadge.textContent = '○ INACTIVE';
            statusBadge.style.color = '#ff4444';
            statusBadge.style.background = '';
        }
    }
    
    // 🆕 Count actual Grid trades from history
    const history = data.history || {};
    const allTrades = history.trades || [];
    const gridTrades = allTrades.filter(t => t.slotId === 99);
    const gridPnL = gridTrades.reduce((sum, t) => sum + (t.pnlUSDT || 0), 0);
    
    // Update summary stats with REAL data from trade-history
    const totalBots = document.getElementById('gridTotalBots');
    const totalOrders = document.getElementById('gridTotalOrders');
    const tradesExecuted = document.getElementById('gridTradesExecuted');
    const totalPnL = document.getElementById('gridTotalPnL');
    
    if (totalBots) totalBots.textContent = gridData.totalBots || 7;
    if (totalOrders) totalOrders.textContent = gridData.totalOrders || 0;
    if (tradesExecuted) tradesExecuted.textContent = gridTrades.length;  // 🆕 Real count
    if (totalPnL) {
        const pnl = gridPnL;  // 🆕 Real P&L from trades
        totalPnL.textContent = `$${pnl.toFixed(2)}`;
        totalPnL.className = `grid-stat-value pnl ${pnl >= 0 ? 'profit' : 'loss'}`;
    }
    
    // Update bots table
    const tbody = document.getElementById('gridBotsTableBody');
    if (!tbody || !gridData.bots) return;
    
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    let html = '';
    
    coins.forEach(coin => {
        const bot = gridData.bots[coin];
        if (bot && bot.active) {
            const range = bot.range || {};
            html += `
                <tr>
                    <td><strong>${coin}</strong></td>
                    <td><span style="color: #00ff00;">● Active</span></td>
                    <td>$${bot.price ? bot.price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) : '0.00'}</td>
                    <td>${bot.orders || 0}</td>
                    <td>$${range.low ? range.low.toLocaleString() : '0'} - $${range.high ? range.high.toLocaleString() : '0'}</td>
                    <td>$${(bot.balanceUSDT || 0).toFixed(2)}</td>
                </tr>
            `;
        }
    });
    
    tbody.innerHTML = html || '<tr><td colspan="6" class="loading-row">No bots active</td></tr>';
    
    console.log('✅ Grid Trading updated:', `${gridTrades.length} trades executed, $${gridPnL.toFixed(2)} P&L`);
}

function updatePnlByCoin(pnlByCoin) {
    const grid = document.getElementById('pnlByCoinGrid');
    const container = document.getElementById('pnlByCoinContainer');
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    
    if (!grid || !container) return;
    
    // Hide if no data
    if (!pnlByCoin || Object.keys(pnlByCoin).length === 0) {
        container.style.display = 'none';
        return;
    }
    
    container.style.display = 'block';
    
    let html = '';
    coins.forEach(coin => {
        const pnl = pnlByCoin[coin] || 0;
        const pnlClass = pnl >= 0 ? '' : 'loss';
        const pnlSign = pnl >= 0 ? '+' : '';
        const percentClass = pnl >= 0 ? 'positive' : 'negative';
        
        html += `
            <div class="pnl-coin-item">
                <div class="pnl-coin-name">${coin}</div>
                <div class="pnl-coin-value ${pnlClass}">${pnlSign}$${Math.abs(pnl).toFixed(2)}</div>
                <div class="pnl-coin-percent ${percentClass}">${pnlSign}${((pnl / 2527) * 100).toFixed(2)}%</div>
            </div>
        `;
    });
    
    grid.innerHTML = html;
    console.log('✅ P&L by coin updated:', pnlByCoin);
}

function updatePrices(prices) {
    const chartsGrid = document.getElementById('chartsGrid');
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    
    console.log('📈 Updating prices, received:', Object.keys(prices).length, 'coins');
    
    if (!prices || Object.keys(prices).length === 0) {
        console.warn('⚠️ No prices data');
        return;
    }
    
    let html = '';
    
    coins.forEach(coin => {
        
        const priceData = prices[coin];
        
        if (priceData && priceData.price) {
            const price = parseFloat(priceData.price);
            const change = parseFloat(priceData.change_24h) || 0;
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
        } else {
            console.warn(`⚠️ No price data for ${coin}`);
        }
    });
    
    chartsGrid.innerHTML = html;
    console.log('✅ Price charts updated');
}

function updateSystemStatus(data) {
    const marketMode = data.market_mode || {};
    const system = data.system || {};
    
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
    
    // API Binance Status
    const apiStatus = document.getElementById('apiStatus');
    if (apiStatus) {
        apiStatus.textContent = system.api_binance === 'ok' ? '✅' : '❌';
        apiStatus.title = system.api_binance === 'ok' ? 'Binance API Online' : 'Binance API Offline';
    }
    
    // IP Whitelist Status
    const ipStatus = document.getElementById('ipStatus');
    if (ipStatus) {
        if (system.ip_whitelist && system.ip_whitelist !== 'error') {
            ipStatus.textContent = `✅ ${system.ip_whitelist}`;
            ipStatus.title = 'IP Pública Actual';
        } else {
            ipStatus.textContent = '❌ No disponible';
            ipStatus.title = 'No se pudo obtener IP';
        }
    }
    
    // Gateway Status
    const gatewayStatus = document.getElementById('gatewayStatus');
    if (gatewayStatus) {
        gatewayStatus.textContent = system.gateway === 'ok' ? '✅' : '❌';
        gatewayStatus.title = system.gateway === 'ok' ? 'Gateway Online' : 'Gateway Offline';
    }
}

function updateAutoAdjust(data) {
    const autoAdjust = data.auto_adjust || {};
    const marketMode = data.market_mode || {};
    
    // Actualizar nombre de estrategia
    const strategyName = document.getElementById('strategyName');
    if (strategyName) {
        strategyName.textContent = marketMode.MARKET_MODE || 'LATERAL';
    }
    
    // Actualizar countdown
    const countdownEl = document.getElementById('autoAdjustCountdown');
    if (countdownEl && autoAdjust.hours_until !== undefined && autoAdjust.minutes_until !== undefined) {
        const hours = autoAdjust.hours_until;
        const minutes = autoAdjust.minutes_until;
        const seconds = Math.floor(Math.random() * 60); // Random seconds for visual effect
        
        countdownEl.textContent = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        
        // Clear existing interval
        if (countdownInterval) clearInterval(countdownInterval);
        
        // Start countdown timer
        countdownInterval = setInterval(() => {
            const now = new Date();
            const nextAdjustment = new Date(autoAdjust.next_adjustment);
            const diff = nextAdjustment - now;
            
            if (diff <= 0) {
                countdownEl.textContent = '00:00:00';
                clearInterval(countdownInterval);
                // Reload data when adjustment time arrives
                
                return;
            }
            
            const h = Math.floor(diff / 3600000);
            const m = Math.floor((diff % 3600000) / 60000);
            const s = Math.floor((diff % 60000) / 1000);
            
            countdownEl.textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        }, 1000);
    }
}

function updateCircuitBreakerStatus(data) {
    const cb = (data.circuitBreakerStatus || {}).circuitBreakerActive ? (data.circuitBreakerStatus || {}) : {};
    const cbLabel = document.getElementById('cbLabel');
    const cbCountdown = document.getElementById('cbCountdown');
    const cbBadge = document.getElementById('cbBadge');
    if (!cbLabel || !cbCountdown || !cbBadge) return;

    if (!cb.circuitBreakerActive) {
        cbLabel.textContent = 'CB OFF';
        cbCountdown.textContent = '';
        cbBadge.className = 'cb-badge off';
        return;
    }

    cbLabel.textContent = 'CB ON';
    cbBadge.className = 'cb-badge on';
    const until = cb.pauseUntil ? new Date(cb.pauseUntil) : null;
    if (!until) {
        cbCountdown.textContent = '';
        return;
    }

    const update = () => {
        const now = new Date();
        const diff = until - now;
        if (diff <= 0) {
            cbCountdown.textContent = '00:00:00';
            
            return;
        }
        const h = Math.floor(diff / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        cbCountdown.textContent = `⏳ ${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    };
    update();
    setInterval(update, 1000);
}

// ═══════════════════════════════════════════════════════
// TRADES HISTORY TABLE
// ═══════════════════════════════════════════════════════

function updateTradesTable(data) {
    const history = data.history || {};
    const trades = history.trades || [];
    const tbody = document.getElementById('tradesTableBody');
    
    console.log('📜 Updating trades table, trades:', trades.length);
    
    // Ordenar del más reciente al más antiguo (descendente por timestamp)
    const sortedTrades = [...trades].sort((a, b) => {
      const ta = new Date((b.timestamp || '').replace(' ', 'T')).getTime();
      const tb = new Date((a.timestamp || '').replace(' ', 'T')).getTime();
      const da = ta || 0;
      const db = tb || 0;
      if (da !== db) return da - db;
      return (b.id || 0) - (a.id || 0);
    });
    const limit = showAllTrades ? sortedTrades.length : CONFIG.MAX_TRADES_DISPLAY;
    const tradesToShow = sortedTrades.slice(0, limit);
    
    console.log('📋 Trades ordenados (más recientes primero):');
    tradesToShow.forEach((t, i) => {
        console.log(`  ${i+1}. #${t.id} ${t.symbol} ${t.closeType} - ${new Date(t.timestamp).toLocaleString()}`);
    });
    
    if (tradesToShow.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="loading-row">No trades yet (estrategia dinámica reseteada)</td></tr>';
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
                <td style="color: ${pnlColor}">${trade.pnlUSDT != null ? (trade.pnlUSDT >= 0 ? '+' : '') + '$' + trade.pnlUSDT.toFixed(2) : '--'}</td>
                <td><span class="status-badge ${pnlClass}">${closeType}</span></td>
                <td>${new Date(trade.timestamp).toLocaleString()}</td>
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
        
        if (progress < 1) requestAnimationFrame(update);
    }
    
    requestAnimationFrame(update);
}

// Toggle show all trades
function toggleAllTrades() {
    showAllTrades = !showAllTrades;
    const btn = document.getElementById('viewMoreBtn');
    if (btn) {
        btn.textContent = showAllTrades ? '📋 Ver menos trades' : `📋 Ver más trades (${CONFIG.MAX_TRADES_DISPLAY} de ${lastData?.history?.trades?.length || 0})`;
    }
    loadData();  // Reload to show/hide trades
}


// ════════════════════════════════════════════════════════
// 🔔 TP/SL NOTIFICATION SYSTEM
// ════════════════════════════════════════════════════════

let playedNotificationIds = new Set();  // Track notification IDs already played (in-memory)

// Check for new TP/SL notifications
async function checkTPNotifications() {
    try {
        const response = await fetch('/crypto-bots/tp-notifications.json?v=' + Date.now());
        if (!response.ok) return;
        
        const notifications = await response.json();
        if (!Array.isArray(notifications)) return;
        
        // Find new notifications (only play once per unique notification)
        let hasNewNotifications = false;
        const newNotifications = [];  // Keep only unplayed notifications
        
        for (let notif of notifications) {
            // Create unique ID from coin + slot_id + tp + timestamp
            const notifId = `${notif.coin}-${notif.slot_id}-${notif.tp}-${notif.timestamp}`;
            
            if (!playedNotificationIds.has(notifId)) {
                console.log('🔔 TP/SL Notification:', notif.coin, 'Slot', notif.slot_id, '-', notif.tp, '| P&L:', notif.pnl);
                
                // Play appropriate sound based on TP or SL
                if (notif.tp === 'SL') {
                    playStopLoss();  // 🛑 Stop Loss sound
                } else {
                    playCashRegister();  // 💰 TP hit sound
                }
                
                showTPNotification(notif);
                playedNotificationIds.add(notifId);  // Mark as played in memory
                hasNewNotifications = true;
                
                // Mark as played and keep temporarily
                notif.played = true;
                newNotifications.push(notif);
            } else {
                // Already played, remove from file
                console.log(`📝 ${notif.coin} ${notif.tp} already played - removing`);
            }
        }
        
        // Write back only unplayed notifications (cleanup old ones)
        if (notifications.length > 0 && newNotifications.length === 0) {
            // All notifications played, clear the file
            await fetch('/crypto-bots/tp-notifications.json', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: '[]'
            });
        }
        
        if (!hasNewNotifications && notifications.length > 0) {
            console.log(`📝 Cleaned up ${notifications.length} old notification(s)`);
        }
    } catch (error) {
        // Silently fail
    }
}

// Show visual notification
function showTPNotification(notif) {
    const pnlClass = notif.pnl >= 0 ? 'profit' : 'loss';
    const pnlIcon = notif.pnl >= 0 ? '🟢' : '🔴';
    const pnlSign = notif.pnl >= 0 ? '+' : '';
    const isSL = notif.tp === 'SL';
    
    const notification = document.createElement('div');
    notification.className = `tp-notification ${pnlClass}`;
    notification.innerHTML = `
        <div class="tp-notification-content">
            <div class="tp-notification-icon">${isSL ? '🛑' : pnlIcon} ${notif.tp}</div>
            <div class="tp-notification-coin">${notif.coin}</div>
            <div class="tp-notification-slot">Slot ${notif.slot_id}</div>
            <div class="tp-notification-pnl">${pnlSign}$${notif.pnl.toFixed(2)}</div>
        </div>
    `;
    
    document.body.appendChild(notification);
    setTimeout(() => notification.classList.add('show'), 100);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 500);
    }, 5000);
}

// Add CSS for notifications
const notificationStyle = document.createElement('style');
notificationStyle.textContent = `
    .tp-notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: var(--bg-card);
        border: 2px solid var(--neon-green);
        border-radius: 10px;
        padding: 20px;
        z-index: 10000;
        transform: translateX(400px);
        transition: transform 0.5s ease;
        box-shadow: 0 0 30px rgba(0, 255, 136, 0.3);
    }
    .tp-notification.show { transform: translateX(0); }
    .tp-notification.loss {
        border-color: var(--neon-red);
        box-shadow: 0 0 30px rgba(255, 51, 102, 0.3);
    }
    .tp-notification-content { display: flex; flex-direction: column; gap: 5px; }
    .tp-notification-icon { font-size: 1.5em; font-weight: bold; }
    .tp-notification-coin { font-size: 1.2em; font-weight: bold; }
    .tp-notification-slot { color: var(--text-secondary); }
    .tp-notification-pnl { font-size: 1.3em; font-weight: bold; }
    .tp-notification.profit .tp-notification-pnl { color: var(--neon-green); }
    .tp-notification.loss .tp-notification-pnl { color: var(--neon-red); }
`;
document.head.appendChild(notificationStyle);

// Check every 5 seconds
setInterval(checkTPNotifications, 30000);
console.log('🔔 TP/SL Notification system initialized');
