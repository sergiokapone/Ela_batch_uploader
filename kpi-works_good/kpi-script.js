// kpiWorksConfig.apiUrl — передається з PHP через wp_localize_script

let currentPage = 0;
let currentCollection = 'magistr';
let currentYear = '';
let currentQuery = '';
let searchDebounceTimer = null;

// Коли сторінка завантажилась — одразу показуємо роботи
document.addEventListener('DOMContentLoaded', function () {
    loadWorks();

    // document.getElementById('kpi-search-btn').addEventListener('click', function () {
        // currentPage = 0;
        // currentCollection = document.getElementById('kpi-collection').value;
        // currentYear = document.getElementById('kpi-year').value;
        // loadWorks();
    // });
    
    document.getElementById('kpi-collection').addEventListener('change', function () {
        currentPage = 0;
        currentCollection = this.value;
        loadWorks();
    });
    
    document.getElementById('kpi-search').addEventListener('input', function () {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(function () {
            currentPage = 0;
            currentQuery = document.getElementById('kpi-search').value.trim();
            loadWorks();
        }, 450);
    });

    document.getElementById('kpi-year').addEventListener('change', function () {
        currentPage = 0;
        currentYear = this.value;
        loadWorks();
    });
});

function loadWorks() {
    const status = document.getElementById('kpi-status');
    const list   = document.getElementById('kpi-list');

    status.textContent = 'Завантажуємо...';
    list.innerHTML = '';

    // Будуємо URL запиту до нашого PHP endpoint
    const url = new URL(kpiWorksConfig.apiUrl);
    url.searchParams.set('collection', currentCollection);
    url.searchParams.set('page', currentPage);
    if (currentYear) {
        url.searchParams.set('year', currentYear);
    }
    if (currentQuery) {
        url.searchParams.set('query', btoa(unescape(encodeURIComponent(currentQuery))));
        url.searchParams.set('q_enc', 'base64');
    }

    // Робимо запит до свого WordPress (не до КПІ напряму!)
    fetch(url.toString())
        .then(response => response.json().then(data => ({ ok: response.ok, httpStatus: response.status, data })))
        .then(({ ok, httpStatus, data }) => {
            if (!ok) {
                const detail = data?.data?.response ?? data?.message ?? JSON.stringify(data);
                const reqUrl = data?.data?.url ?? '';
                status.textContent = `Помилка від сервера (HTTP ${data?.data?.http_code ?? httpStatus})`;
                console.error('KPI Works API error:', data);
                console.error('URL запиту до ela.kpi.ua:', reqUrl);
                console.error('Відповідь ela.kpi.ua:', detail);
                return;
            }
            status.textContent = `Знайдено: ${data.total} робіт`;
            renderWorks(data.works);
            renderPagination(data.total_pages);
        })
        .catch(err => {
            status.textContent = 'Помилка завантаження (мережа або невалідна відповідь)';
            console.error('KPI Works fetch error:', err);
        });
}

function renderWorks(works) {
    const list = document.getElementById('kpi-list');

    if (!works.length) {
        list.innerHTML = '<p>Нічого не знайдено</p>';
        return;
    }

    list.innerHTML = works.map(work => `
        <div class="kpi-work-item ${work.collection}">
            <div>
                <span class="kpi-badge ${work.collection}">
                    ${work.collection === 'magistr' ? 'Магістерська' : 'Бакалаврська'}
                </span>
                ${work.year ? `<span class="kpi-year-pill">${work.year}</span>` : ''}
            </div>
            <h3>
                <a href="${work.url}" target="_blank">${work.title || 'Без назви'}</a>
            </h3>
            <div class="kpi-meta">
                <span class="kpi-meta-icon">👤</span>
                <span>${work.authors.join(', ') || '—'}</span>
            </div>
            <div class="kpi-meta">
                <span class="kpi-meta-icon">🎓</span>
                <span>${work.advisors.join(', ') || '—'}</span>
            </div>
            ${work.abstract ? `
            <details>
                <summary>Анотація</summary>
                <p class="kpi-abstract">${work.abstract}</p>
            </details>` : ''}
        </div>
    `).join('');
}

function renderPagination(totalPages) {
    const pagination = document.getElementById('kpi-pagination');

    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';

    if (currentPage > 0) {
        html += `<button onclick="goToPage(${currentPage - 1})">← Назад</button>`;
    }

    html += ` <span>Сторінка ${currentPage + 1} з ${totalPages}</span> `;

    if (currentPage + 1 < totalPages) {
        html += `<button onclick="goToPage(${currentPage + 1})">Далі →</button>`;
    }

    pagination.innerHTML = html;
}

function goToPage(page) {
    currentPage = page;
    loadWorks();
    // Прокрутити вгору до списку
    document.getElementById('kpi-works-app').scrollIntoView({ behavior: 'smooth' });
}