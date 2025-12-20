// 労働基準関係法令違反 公表事案アーカイブ - JavaScript

// グローバル変数
let allCompanies = [];
let filteredCompanies = [];
let currentPage = 1;
const ITEMS_PER_PAGE = 50;

document.addEventListener('DOMContentLoaded', function() {
    renderYearChart();
    loadActiveCompanies();
    setupEventListeners();
});

/**
 * イベントリスナーを設定
 */
function setupEventListeners() {
    const searchInput = document.getElementById('search-input');
    const bureauFilter = document.getElementById('bureau-filter');
    
    if (searchInput) {
        searchInput.addEventListener('input', debounce(filterAndRender, 300));
    }
    
    if (bureauFilter) {
        bureauFilter.addEventListener('change', filterAndRender);
    }
}

/**
 * デバウンス関数
 */
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

/**
 * アクティブ企業データを読み込む
 */
async function loadActiveCompanies() {
    try {
        const response = await fetch('data/active.json');
        if (!response.ok) throw new Error('Failed to load data');
        
        allCompanies = await response.json();
        filteredCompanies = [...allCompanies];
        
        populateBureauFilter();
        renderTable();
        updateCounts();
    } catch (error) {
        console.error('Error loading companies:', error);
        const tbody = document.getElementById('companies-tbody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #64748b;">データの読み込みに失敗しました</td></tr>';
        }
    }
}

/**
 * 労働局フィルターを初期化
 */
function populateBureauFilter() {
    const select = document.getElementById('bureau-filter');
    if (!select) return;
    
    const bureaus = [...new Set(allCompanies.map(c => c.labor_bureau).filter(b => b))].sort();
    
    bureaus.forEach(bureau => {
        const option = document.createElement('option');
        option.value = bureau;
        option.textContent = bureau;
        select.appendChild(option);
    });
}

/**
 * フィルタリングしてテーブルを再描画
 */
function filterAndRender() {
    const searchText = document.getElementById('search-input')?.value.toLowerCase() || '';
    const bureauValue = document.getElementById('bureau-filter')?.value || '';
    
    filteredCompanies = allCompanies.filter(company => {
        // 検索条件
        const matchesSearch = !searchText || 
            (company.company_name && company.company_name.toLowerCase().includes(searchText)) ||
            (company.location && company.location.toLowerCase().includes(searchText));
        
        // 労働局フィルター
        const matchesBureau = !bureauValue || company.labor_bureau === bureauValue;
        
        return matchesSearch && matchesBureau;
    });
    
    currentPage = 1;
    renderTable();
    updateCounts();
}

/**
 * 件数表示を更新
 */
function updateCounts() {
    const showingCount = document.getElementById('showing-count');
    const totalCount = document.getElementById('total-count');
    
    if (showingCount) {
        showingCount.textContent = filteredCompanies.length.toLocaleString();
    }
    if (totalCount) {
        totalCount.textContent = allCompanies.length.toLocaleString();
    }
}

/**
 * テーブルを描画
 */
function renderTable() {
    const tbody = document.getElementById('companies-tbody');
    if (!tbody) return;
    
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    const pageData = filteredCompanies.slice(start, end);
    
    if (pageData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: #64748b;">該当するデータがありません</td></tr>';
        renderPagination();
        return;
    }
    
    let html = '';
    for (const company of pageData) {
        const name = escapeHtml(company.company_name || '');
        const location = escapeHtml(company.location || '');
        const law = escapeHtml(truncateText(company.violation_law || '', 30));
        const date = company.first_appeared || '';
        
        html += `
            <tr>
                <td>${name}</td>
                <td>${location}</td>
                <td title="${escapeHtml(company.violation_law || '')}">${law}</td>
                <td>${date}</td>
            </tr>
        `;
    }
    
    tbody.innerHTML = html;
    renderPagination();
}

/**
 * ページネーションを描画
 */
function renderPagination() {
    const container = document.getElementById('pagination');
    if (!container) return;
    
    const totalPages = Math.ceil(filteredCompanies.length / ITEMS_PER_PAGE);
    
    if (totalPages <= 1) {
        container.innerHTML = '';
        return;
    }
    
    let html = '';
    
    // 前へボタン
    html += `<button onclick="goToPage(${currentPage - 1})" ${currentPage === 1 ? 'disabled' : ''}>前へ</button>`;
    
    // ページ番号
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    if (startPage > 1) {
        html += `<button onclick="goToPage(1)">1</button>`;
        if (startPage > 2) html += `<span style="padding: 0.5rem;">...</span>`;
    }
    
    for (let i = startPage; i <= endPage; i++) {
        html += `<button onclick="goToPage(${i})" class="${i === currentPage ? 'active' : ''}">${i}</button>`;
    }
    
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) html += `<span style="padding: 0.5rem;">...</span>`;
        html += `<button onclick="goToPage(${totalPages})">${totalPages}</button>`;
    }
    
    // 次へボタン
    html += `<button onclick="goToPage(${currentPage + 1})" ${currentPage === totalPages ? 'disabled' : ''}>次へ</button>`;
    
    container.innerHTML = html;
}

/**
 * 指定ページに移動
 */
function goToPage(page) {
    const totalPages = Math.ceil(filteredCompanies.length / ITEMS_PER_PAGE);
    if (page < 1 || page > totalPages) return;
    
    currentPage = page;
    renderTable();
    
    // テーブルの先頭にスクロール
    document.getElementById('companies-table')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * HTMLエスケープ
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * テキストを切り詰め
 */
function truncateText(text, maxLength) {
    if (!text || text.length <= maxLength) return text;
    return text.substring(0, maxLength) + '...';
}

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
