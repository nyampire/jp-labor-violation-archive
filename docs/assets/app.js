// 労働基準関係法令違反 公表事案アーカイブ - JavaScript

document.addEventListener('DOMContentLoaded', function() {
    renderYearChart();
});

/**
 * 年別推移のバーチャートを描画
 */
function renderYearChart() {
    const container = document.getElementById('year-chart');
    if (!container) return;
    
    // yearData はHTMLにインラインで埋め込まれている
    if (typeof yearData === 'undefined' || Object.keys(yearData).length === 0) {
        return;
    }
    
    const years = Object.keys(yearData).sort();
    const values = years.map(y => yearData[y]);
    const maxValue = Math.max(...values);
    
    let html = '<div class="bar-chart">';
    
    for (const year of years) {
        const value = yearData[year];
        const width = (value / maxValue * 100).toFixed(1);
        
        html += `
            <div class="bar-row">
                <span class="bar-label">${year}</span>
                <div class="bar-container">
                    <div class="bar" style="width: ${width}%"></div>
                </div>
                <span class="bar-value">${value.toLocaleString()}</span>
            </div>
        `;
    }
    
    html += '</div>';
    container.innerHTML = html;
}
