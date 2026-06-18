// ════════════════════════════════════════════════════════
// 🐕 PERROBOTILLO DASHBOARD - ANIME.JS ANIMATIONS
// ════════════════════════════════════════════════════════
// Cyberpunk animations for trading dashboard
// Author: Perrobotillo 🐕
// ════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
  
  console.log('🎨 Anime.js loaded - Cyberpunk animations ready');
  
  // ════════════════════════════════════════════════════════
  // 1. GLOW EFFECT EN TARJETAS CYBERPUNK
  // ════════════════════════════════════════════════════════
  
  const cyberCards = document.querySelectorAll('.cyber-card');
  
  cyberCards.forEach((card, index) => {
    anime({
      targets: card,
      boxShadow: [
        '0 0 5px rgba(0, 243, 255, 0.2)',
        '0 0 15px rgba(0, 243, 255, 0.5)',
        '0 0 5px rgba(0, 243, 255, 0.2)'
      ],
      duration: 3000 + (index * 500), // Stagger por carta
      loop: true,
      easing: 'easeInOutQuad',
      delay: index * 300
    });
  });
  
  // ════════════════════════════════════════════════════════
  // 2. ANIMACIÓN DE PRECIOS AL ACTUALIZAR
  // ════════════════════════════════════════════════════════
  
  window.animatePriceChange = function(selector, newValue, duration = 1000) {
    const element = document.querySelector(selector);
    if (!element) return;
    
    const currentValue = element.innerHTML.replace('$', '').replace(',', '').trim();
    const oldValue = parseFloat(currentValue) || 0;
    
    anime({
      targets: element,
      innerHTML: [oldValue, newValue],
      round: 0.01,
      easing: 'easeInOutQuad',
      duration: duration,
      update: function(anim) {
        const value = parseFloat(anim.animatables[0].target.innerHTML);
        if (!isNaN(value)) {
          element.innerHTML = '$' + value.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
          });
        }
      }
    });
  };
  
  // ════════════════════════════════════════════════════════
  // 3. BARRAS DE PORTFOLIO - CRECIMIENTO SUAVE
  // ════════════════════════════════════════════════════════
  
  window.animatePortfolioBars = function() {
    const bars = document.querySelectorAll('.portfolio-bar, .allocation-bar');
    
    bars.forEach((bar, index) => {
      const targetWidth = bar.getAttribute('data-target') || bar.getAttribute('data-width') || 0;
      
      // Reset width to 0 first
      bar.style.width = '0%';
      
      anime({
        targets: bar,
        width: targetWidth + '%',
        easing: 'easeOutQuart',
        duration: 1200,
        delay: index * 100 // Stagger effect
      });
    });
  };
  
  // ════════════════════════════════════════════════════════
  // 4. FLASH EN TRADES EJECUTADOS
  // ════════════════════════════════════════════════════════
  
  window.flashTradeExecuted = function(coin, pnl) {
    const row = document.querySelector(`.trade-row[data-coin="${coin}"]`);
    if (!row) return;
    
    const color = pnl >= 0 
      ? 'rgba(0, 255, 0, 0.6)'  // Verde para profit
      : 'rgba(255, 0, 0, 0.6)'; // Rojo para loss
    
    anime({
      targets: row,
      backgroundColor: [color, 'transparent'],
      translateX: [-5, 5, -5, 5, 0], // Pequeño shake
      duration: 1500,
      easing: 'easeInOutQuad'
    });
  };
  
  // ════════════════════════════════════════════════════════
  // 5. GRID TRADING - ÓRDENES EJECUTADAS
  // ════════════════════════════════════════════════════════
  
  window.animateGridOrder = function(row, type) {
    const color = type === 'buy' 
      ? 'rgba(0, 255, 0, 0.3)'
      : 'rgba(255, 0, 0, 0.3)';
    
    anime({
      targets: row,
      backgroundColor: [color, 'transparent'],
      scale: [0.98, 1.02, 1],
      duration: 1200,
      easing: 'easeOutQuad'
    });
  };
  
  // ════════════════════════════════════════════════════════
  // 6. LOADING SPINNER
  // ════════════════════════════════════════════════════════
  
  const loadingSpinners = document.querySelectorAll('.loading-spinner');
  loadingSpinners.forEach(spinner => {
    anime({
      targets: spinner,
      rotate: '1turn',
      duration: 1000,
      loop: true,
      easing: 'linear'
    });
  });
  
  // ════════════════════════════════════════════════════════
  // 7. PULSO EN VALORES IMPORTANTES
  // ════════════════════════════════════════════════════════
  
  const importantValues = document.querySelectorAll('.important-value, .pnl-positive, .pnl-negative');
  importantValues.forEach(value => {
    anime({
      targets: value,
      scale: [1, 1.05, 1],
      duration: 2000,
      loop: true,
      easing: 'easeInOutQuad'
    });
  });
  
  // ════════════════════════════════════════════════════════
  // 8. ENTRADA DE DATOS - FADE IN
  // ════════════════════════════════════════════════════════
  
  const sections = document.querySelectorAll('.cyber-card, section');
  sections.forEach((section, index) => {
    section.style.opacity = '0';
    
    anime({
      targets: section,
      opacity: 1,
      translateY: [20, 0],
      duration: 800,
      delay: index * 100,
      easing: 'easeOutQuad'
    });
  });
  
  // ════════════════════════════════════════════════════════
  // 9. ACTUALIZACIÓN DE DATOS EN TIEMPO REAL
  // ════════════════════════════════════════════════════════
  
  window.animateDataUpdate = function() {
    // Animar números de portfolio
    const portfolioValues = document.querySelectorAll('.portfolio-value, .pnl-value');
    portfolioValues.forEach(value => {
      anime({
        targets: value,
        scale: [1, 1.02, 1],
        color: ['#ffffff', '#00ff00', '#ffffff'],
        duration: 800,
        easing: 'easeInOutQuad'
      });
    });
    
    // Animar Grid stats
    const gridStats = document.querySelectorAll('.grid-stat-value');
    gridStats.forEach(stat => {
      anime({
        targets: stat,
        scale: [1, 1.1, 1],
        duration: 600,
        easing: 'easeOutQuad'
      });
    });
  };
  
  // ════════════════════════════════════════════════════════
  // 10. EFECTO EN BOTONES AL HACER HOVER
  // ════════════════════════════════════════════════════════
  
  const buttons = document.querySelectorAll('button, .cyber-button');
  buttons.forEach(button => {
    button.addEventListener('mouseenter', () => {
      anime({
        targets: button,
        scale: 1.05,
        boxShadow: '0 0 15px rgba(0, 243, 255, 0.6)',
        duration: 300,
        easing: 'easeOutQuad'
      });
    });
    
    button.addEventListener('mouseleave', () => {
      anime({
        targets: button,
        scale: 1,
        boxShadow: '0 0 5px rgba(0, 243, 255, 0.2)',
        duration: 300,
        easing: 'easeOutQuad'
      });
    });
  });
  
  console.log('✅ All animations initialized');
});

// ════════════════════════════════════════════════════════
// FUNCIONES GLOBALES PARA USAR DESDE OTROS SCRIPTS
// ════════════════════════════════════════════════════════

// Llamar después de actualizar datos del API
window.onDashboardDataUpdated = function() {
  if (window.animatePortfolioBars) {
    window.animatePortfolioBars();
  }
  if (window.animateDataUpdate) {
    window.animateDataUpdate();
  }
};
