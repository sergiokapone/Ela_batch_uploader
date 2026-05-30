document.addEventListener('DOMContentLoaded', function () {
    const encoded = btoa(unescape(encodeURIComponent(kpiShelfConfig.author)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
    const url = kpiShelfConfig.apiUrl + '?author=' + encoded + '&enc=base64';

    fetch(url.toString())
        .then(r => r.json())
        .then(works => {
            const status = document.getElementById('kpi-shelf-status');
            const grid   = document.getElementById('kpi-shelf-grid');

            if (!works.length) {
                status.textContent = 'Публікацій не знайдено';
                return;
            }

            status.textContent = `${works.length} публікацій`;

            grid.innerHTML = works.map(work => {
                const authors = work.authors.join(', ');
                // const thumb   = work.thumbnail
                    // ? `<img src="${escHtml(work.thumbnail)}" alt="${escHtml(work.title)}" loading="lazy">`
                    // : `<div class="kpi-shelf-nocover">📄</div>`;
                
                function typeInfo(type) {
                   const map = {
                       'Learning Object':     { label: 'Навчальний матеріал', cls: 'learning' },
                       'Methodical Material': { label: 'Методичний матеріал', cls: 'methodical' },
                       'Article':             { label: 'Стаття',              cls: 'article' },
                       'Thesis':              { label: 'Тези',                cls: 'thesis' },
                   };
                   return map[type] || { label: type, cls: 'other' };
}               

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
        })
        .catch(err => {
            document.getElementById('kpi-shelf-status').textContent = 'Помилка завантаження';
            console.error('KPI Shelf error:', err);
        });
});

function escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
