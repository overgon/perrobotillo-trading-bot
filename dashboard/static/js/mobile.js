// ════════════════════════════════════════════════════════
// 🐕 PERROBOTILLO DASHBOARD MOBILE - CYBERPUNK EDITION
// Optimizado para iPhone 14 Pro + Safari
// ════════════════════════════════════════════════════════

const CONFIG = {
    API_URL: '/api/status',
    PRICES_URL: '/api/prices',
    REFRESH_INTERVAL: 60000,
    PRICES_INTERVAL: 60000,
    CACHE_BUSTER: true  // Force fresh API calls
};

let lastData = null;
let lastPrices = {};
let countdownInterval = null;
let showAllTrades = false;  // Show only 10 by default

// ════════════════════════════════════════════════════════
// 📱 DEVICE DETECTION
// ════════════════════════════════════════════════════════

function detectDevice() {
    const ua = navigator.userAgent;
    const isIOS = /iPad|iPhone|iPod/.test(ua) && !window.MSStream;
    const isAndroid = /Android/.test(ua);
    const isMobile = /Mobile/.test(ua);
    const isSafari = /Safari/.test(ua) && !/Chrome/.test(ua);
    const isChrome = /Chrome/.test(ua);
    
    console.log('📱 Device Detection:', {
        isIOS,
        isAndroid,
        isMobile,
        isSafari,
        isChrome,
        ua: ua.substring(0, 50)
    });
    
    return { isIOS, isAndroid, isMobile, isSafari, isChrome };
}

// ════════════════════════════════════════════════════════
// 🚀 INITIALIZATION
// ════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    console.log('🐕 Perrobotillo Mobile Dashboard - Initializing...');
    
    const device = detectDevice();
    
    // Optimizaciones específicas para Safari iOS
    if (device.isIOS && device.isSafari) {
        console.log('🍎 Safari iOS detectado - Optimizando...');
        // Forzar repaint para evitar flickering
        document.body.style.opacity = '0.99';
        setTimeout(() => {
            document.body.style.opacity = '1';
        }, 100);
    }
    
    // Cargar precios primero
    loadPrices().then(() => {
        loadData();
    });
    
    // Refresh intervals
    setInterval(loadData, CONFIG.REFRESH_INTERVAL);
    setInterval(loadPrices, CONFIG.PRICES_INTERVAL);
    
    // Prevenir zoom accidental en iOS
    document.addEventListener('gesturestart', function(e) {
        e.preventDefault();
    });
});

// ════════════════════════════════════════════════════════
// 📡 DATA LOADING
// ════════════════════════════════════════════════════════

async function loadData() {
    try {
        console.log('📡 Loading data...');
        // Add cache buster to force fresh data
        const url = CONFIG.CACHE_BUSTER 
            ? `${CONFIG.API_URL}?t=${Date.now()}` 
            : CONFIG.API_URL;
        const response = await fetch(url, {
            cache: 'no-cache',
            headers: { 'Cache-Control': 'no-cache' }
        });
        const data = await response.json();
        lastData = data;
        
        updatePortfolio({ portfolio: data.portfolio, history: data.history, pnl: data.pnl });
        updateSlots({ tradeStates: data.tradeStates || {}, prices: lastPrices });
        updateSystemStatus({ market_mode: data.market_mode, system: data.system });
        updateAutoAdjust({ auto_adjust: data.auto_adjust, market_mode: data.market_mode });
        updateTradesTable({ history: data.history });
        updateTimestamp(data.timestamp);
        
        console.log('✅ Data updated:', new Date(data.timestamp).toLocaleTimeString());
    } catch (error) {
        console.error('❌ Error loading data:', error);
    }
}

async function loadPrices() {
    try {
        console.log('📊 Loading prices...');
        // Add cache buster to force fresh data
        const url = CONFIG.CACHE_BUSTER 
            ? `${CONFIG.PRICES_URL}?t=${Date.now()}` 
            : CONFIG.PRICES_URL;
        const response = await fetch(url, {
            cache: 'no-cache',
            headers: { 'Cache-Control': 'no-cache' }
        });
        const prices = await response.json();
        lastPrices = prices;
        console.log('✅ Prices loaded:', Object.keys(prices).length, 'coins');
        updatePrices(prices);
    } catch (error) {
        console.error('❌ Error loading prices:', error);
    }
}

function getCurrentPrice(coin, prices) {
    const priceData = prices[coin];
    
    if (priceData && priceData.price) {
        return parseFloat(priceData.price);
    }
    
    return 0;
}

// ════════════════════════════════════════════════════════
// 💰 PORTFOLIO UPDATE
// ════════════════════════════════════════════════════════

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
    
    if (pnlElement) {
        pnlElement.textContent = `${totalPnl >= 0 ? '+' : ''}$${Math.abs(totalPnl).toFixed(2)}`;
        pnlElement.style.color = totalPnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    }
    
    if (pnlPercent) {
        pnlPercent.textContent = `${pnlPercent24h >= 0 ? '+' : ''}${pnlPercent24h.toFixed(2)}%`;
        pnlPercent.style.color = pnlPercent24h >= 0 ? 'var(--neon-green)' : 'var(--neon-red)';
    }
    
    // Update P&L by coin
    updatePnlByCoin(pnlByCoin);
}

// ════════════════════════════════════════════════════════
// 🎯 SLOTS UPDATE
// ════════════════════════════════════════════════════════

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
        
        // Count active slots
        slots.forEach(slot => {
            const status = slot.status || 'ACTIVE';
            if (status === 'ACTIVE') {
                activeCount++;
            }
        });
        
        if (slots.length === 0) {
            const slotClass = isEmergencyMode ? 'emergency-pause' : 'ready';
            const statusIcon = isEmergencyMode ? '🟠' : '🟡';
            const statusText = isEmergencyMode ? 'PAUSED (CB)' : 'READY';
            html += `
                <div class="slot-card ${slotClass}">
                    <div class="slot-header">
                        <div class="slot-coin">${coin}</div>
                        <div class="slot-id">Slot 1</div>
                    </div>
                    <div class="slot-status ${slotClass}">${statusText} ${statusIcon}</div>
                </div>
            `;
            return;
        }
        
        slots.forEach(slot => {
            const status = slot.status || 'ACTIVE';
            
            // Si el slot está READY, mostrar tarjeta READY (amarillo o naranja si emergency)
            if (status === 'READY') {
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
            
            // Slots cerrados → mostrar como PAUSE (gris o naranja si emergency)
            if (status.startsWith('CLOSED')) {
                const closeReason = status.replace('CLOSED_', '') || 'CLOSED';
                const slotClass = isEmergencyMode ? 'emergency-pause' : 'pause';
                const statusText = isEmergencyMode ? `EMERGENCY PAUSE 🟠 (${closeReason})` : `PAUSE ⏸️ (${closeReason})`;
                html += `
                    <div class="slot-card ${slotClass}">
                        <div class="slot-header">
                            <div class="slot-coin">${coin}</div>
                            <div class="slot-id">Slot ${slot.slotId}</div>
                        </div>
                        <div class="slot-status ${slotClass}">${statusText}</div>
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
            const stopLoss = parseFloat(slot.stopLoss) || 0;
            const quantity = parseFloat(slot.quantity) || 0;
            
            // Calcular P&L primero para determinar modo
            let pnl = 0, pnlPercent = 0;
            if (entryPrice > 0 && currentPrice > 0) {
                pnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100;
                pnl = (currentPrice - entryPrice) * quantity;
            }
            
            // Determinar target actual basado en P&L (negativo → SL, positivo → TP)
            let targetPrice = tp1;
            let targetName = 'TP1';
            let progress = 0;
            let isLossMode = pnl < 0;
            
            // Si está en negativo, mostrar SL como next target
            if (isLossMode && stopLoss > 0) {
                targetPrice = stopLoss;
                targetName = 'SL';
                // Progreso hacia SL (0% = entry, 100% = SL hit)
                // Si el precio ya cruzó el SL, mostrar 100% pero con indicador visual
                if (entryPrice > 0 && stopLoss > 0 && stopLoss !== entryPrice) {
                    progress = ((entryPrice - currentPrice) / (entryPrice - stopLoss)) * 100;
                    // Clamp entre 0-100 para display, pero mantener valor real para lógica
                    if (progress >= 100) {
                        progress = 100;
                        targetName = 'SL HIT ⚠️';
                    }
                }
            } else {
                // Positivo o neutral → mostrar TP normal
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
                    progress = Math.min(100, ((currentPrice - entryPrice) / (targetPrice - entryPrice)) * 100);
                }
            }
            
            html += `
                <div class="slot-card active ${pnl >= 0 ? 'profit' : 'loss'}">
                    <div class="slot-header">
                        <div class="slot-coin">${coin}</div>
                        <div class="slot-id">Slot ${slot.slotId}</div>
                    </div>
                    <div class="slot-status in-trade ${pnl >= 0 ? 'profit' : 'loss'}">${pnl >= 0 ? 'IN TRADE 🟢' : 'IN TRADE 🔴'}</div>
                    
                    <div class="slot-grid-info">
                        <div class="slot-info-item">
                            <div class="slot-info-label">Entry</div>
                            <div class="slot-info-value">$${entryPrice.toFixed(2)}</div>
                        </div>
                        <div class="slot-info-item">
                            <div class="slot-info-label">Current</div>
                            <div class="slot-info-value">$${currentPrice.toFixed(2)}</div>
                        </div>
                        <div class="slot-info-item">
                            <div class="slot-info-label">P&L</div>
                            <div class="slot-info-value" style="color: ${pnl >= 0 ? 'var(--neon-green)' : 'var(--neon-red)'}">
                                ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}
                            </div>
                        </div>
                        <div class="slot-info-item">
                            <div class="slot-info-label">Target</div>
                            <div class="slot-info-value" style="color: ${isLossMode ? 'var(--neon-red)' : 'var(--neon-blue)'}">$${targetPrice.toFixed(2)} (${targetName}${isLossMode ? ' ⚠️' : ''})</div>
                        </div>
                    </div>
                    
                    <div class="tp-progress-container">
                        <div class="tp-label">
                            <span>${isLossMode ? '⚠️ Distance to SL' : 'Progress to ' + targetName}</span>
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

// ════════════════════════════════════════════════════════
// 💰 PRICES UPDATE
// ════════════════════════════════════════════════════════

function updatePnlByCoin(pnlByCoin) {
    const grid = document.getElementById('pnlByCoinGrid');
    const container = document.getElementById('pnlByCoinContainer');
    const coins = ['BTC', 'ETH', 'BNB', 'SOL', 'LINK', 'XRP', 'AVAX'];
    
    if (!grid || !container) return;
    
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
        
        html += `
            <div class="pnl-coin-item">
                <div class="pnl-coin-name">${coin}</div>
                <div class="pnl-coin-value ${pnlClass}">${pnlSign}$${Math.abs(pnl).toFixed(2)}</div>
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

// ════════════════════════════════════════════════════════
// ⚙️ SYSTEM STATUS UPDATE
// ════════════════════════════════════════════════════════

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
    
    const apiStatus = document.getElementById('apiStatus');
    if (apiStatus) {
        apiStatus.textContent = system.api_binance === 'ok' ? '✅' : '❌';
        apiStatus.title = system.api_binance === 'ok' ? 'Binance API Online' : 'Binance API Offline';
    }
    
    const ipStatus = document.getElementById('ipStatus');
    if (ipStatus) {
        if (system.ip_whitelist && system.ip_whitelist !== 'error') {
            ipStatus.textContent = `✅ ${system.ip_whitelist}`;
            ipStatus.title = 'IP Pública Actual';
        } else {
            ipStatus.textContent = '❌ Error';
        }
    }
    
    const gatewayStatus = document.getElementById('gatewayStatus');
    if (gatewayStatus) {
        if (system.gateway === 'ok') {
            gatewayStatus.textContent = '✅';
            gatewayStatus.title = 'Gateway Online';
        } else {
            gatewayStatus.textContent = '❌';
            gatewayStatus.title = 'Gateway Offline';
        }
    }
}

// ════════════════════════════════════════════════════════
// 🧠 AUTO-ADJUST UPDATE
// ════════════════════════════════════════════════════════

function updateAutoAdjust(data) {
    const autoAdjust = data.auto_adjust || {};
    const marketMode = data.market_mode || {};
    
    const strategyName = document.getElementById('strategyName');
    if (strategyName) {
        strategyName.textContent = marketMode.MARKET_MODE || 'LATERAL';
    }
    
    const countdownEl = document.getElementById('autoAdjustCountdown');
    if (countdownEl && autoAdjust.hours_until !== undefined && autoAdjust.minutes_until !== undefined) {
        const hours = autoAdjust.hours_until;
        const minutes = autoAdjust.minutes_until;
        const seconds = Math.floor(Math.random() * 60);
        
        countdownEl.textContent = `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
        
        if (countdownInterval) clearInterval(countdownInterval);
        
        countdownInterval = setInterval(() => {
            const now = new Date();
            const nextAdjustment = new Date(autoAdjust.next_adjustment);
            const diff = nextAdjustment - now;
            
            if (diff <= 0) {
                countdownEl.textContent = '00:00:00';
                clearInterval(countdownInterval);
                setTimeout(loadData, 2000);
                return;
            }
            
            const h = Math.floor(diff / 3600000);
            const m = Math.floor((diff % 3600000) / 60000);
            const s = Math.floor((diff % 60000) / 1000);
            
            countdownEl.textContent = `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
        }, 1000);
    }
}

// ════════════════════════════════════════════════════════
// 📜 TRADES TABLE UPDATE
// ════════════════════════════════════════════════════════

function updateTradesTable(data) {
    const history = data.history || {};
    const trades = history.trades || [];
    const tbody = document.getElementById('tradesTableBody');
    
    console.log('📜 Updating trades table, trades:', trades.length);
    
    // Ordenar del más reciente al más antiguo (descendente por timestamp)
    const sortedTrades = [...trades].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    const limit = showAllTrades ? sortedTrades.length : 10;
    const tradesToShow = sortedTrades.slice(0, limit);
    
    console.log('📋 Trades ordenados (más recientes primero):');
    tradesToShow.forEach((t, i) => {
        console.log(`  ${i+1}. #${t.id} ${t.symbol} ${t.closeType} - ${new Date(t.timestamp).toLocaleString()}`);
    });
    
    if (tradesToShow.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="loading-row">No trades yet</td></tr>';
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
                <td style="color: ${pnlColor}">${trade.pnlUSDT >= 0 ? '+' : ''}$${(trade.pnlUSDT || 0).toFixed(2)}</td>
                <td><span class="status-badge ${pnlClass}">${closeType}</span></td>
            </tr>
        `;
    });
    
    tbody.innerHTML = html;
}

// ════════════════════════════════════════════════════════
// ⏰ TIMESTAMP UPDATE
// ════════════════════════════════════════════════════════

function updateTimestamp(timestamp) {
    const el = document.getElementById('lastUpdate');
    if (el && timestamp) {
        el.textContent = new Date(timestamp).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    }
}

// ════════════════════════════════════════════════════════
// ✨ ANIMATE VALUE
// ════════════════════════════════════════════════════════

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
        btn.textContent = showAllTrades ? '📋 Ver menos trades' : `📋 Ver más trades (${lastData?.history?.trades?.length || 0})`;
    }
    loadData();
}

