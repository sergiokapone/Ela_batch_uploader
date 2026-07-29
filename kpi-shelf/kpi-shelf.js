document.addEventListener('DOMContentLoaded', function () {
    const url = kpiShelfConfig.scope
        ? kpiShelfConfig.apiUrl + '?scope=' + encodeURIComponent(kpiShelfConfig.scope)
        : kpiShelfConfig.apiUrl + '?author=' + btoa(unescape(encodeURIComponent(kpiShelfConfig.author))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '') + '&enc=base64';

    const status = document.getElementById('kpi-shelf-status');
    const grid   = document.getElementById('kpi-shelf-grid');

    let allWorks = [];

    // ── Контролі ──
    const controls = document.createElement('div');
    controls.id = 'kpi-shelf-controls';
    controls.innerHTML = `
        <input type="text" id="kpi-shelf-search" placeholder="Пошук за назвою або автором...">
        <select id="kpi-shelf-sort">
            <option value="year-desc">Рік ↓</option>
            <option value="year-asc">Рік ↑</option>
            <option value="title">Назва А-Я</option>
        </select>
    `;
    status.after(controls);

    document.getElementById('kpi-shelf-search').addEventListener('input', render);
    document.getElementById('kpi-shelf-sort').addEventListener('change', render);

    function render() {
        const query = document.getElementById('kpi-shelf-search').value.toLowerCase();
        const sort  = document.getElementById('kpi-shelf-sort').value;

        let works = allWorks.filter(w => {
            if (!query) return true;
            const hay = (w.title + ' ' + w.authors.join(' ')).toLowerCase();
            return hay.includes(query);
        });

        works = [...works].sort((a, b) => {
            if (sort === 'year-desc') return (b.year || '') > (a.year || '') ? 1 : -1;
            if (sort === 'year-asc')  return (a.year || '') > (b.year || '') ? 1 : -1;
            if (sort === 'title')     return (a.title || '').localeCompare(b.title || '', 'uk');
            return 0;
        });

        status.textContent = `${works.length} публікацій`;

        if (!works.length) {
            grid.innerHTML = '<p style="color:#999">Нічого не знайдено</p>';
            return;
        }

        grid.innerHTML = works.map(work => {
            const authors = work.authors.join(', ');

            const t = typeInfo(work.type);
            const typeLabel = work.type
                ? `<span class="kpi-shelf-type kpi-shelf-type--${t.cls}">${escHtml(t.label)}</span>`
                : '';

            const abstractHtml = work.abstract
                ? `<p class="kpi-shelf-abstract">${escHtml(work.abstract)}</p>`
                : '';

            return `
            <div class="kpi-shelf-item">
                <div class="kpi-shelf-info">
                    <div class="kpi-shelf-meta">
                        ${typeLabel}
                        ${work.year ? `<span class="kpi-shelf-year">${work.year}</span>` : ''}
                    </div>
                    <h3 class="kpi-shelf-title">
                        <a href="${escHtml(work.url)}" target="_blank" rel="noopener">
                            ${escHtml(work.title)}
                        </a>
                    </h3>
                    <p class="kpi-shelf-authors">${escHtml(authors)}</p>
                    ${abstractHtml}
                </div>
            </div>`;
        }).join('');
    }

    fetch(url)
        .then(r => r.json())
        .then(works => {
            if (!works.length) {
                status.textContent = 'Публікацій не знайдено';
                return;
            }
            allWorks = works;
            render();
        })
        .catch(err => {
            status.textContent = 'Помилка завантаження';
            console.error('KPI Shelf error:', err);
        });
});

function typeInfo(type) {
    const map = {
        'Learning Object':     { label: 'Навчальний матеріал', cls: 'learning' },
        'Methodical Material': { label: 'Методичний матеріал', cls: 'methodical' },
        'Article':             { label: 'Стаття',              cls: 'article' },
        'Thesis':              { label: 'Тези',                cls: 'thesis' },
    };
    return map[type] || { label: type, cls: 'other' };
}

function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
