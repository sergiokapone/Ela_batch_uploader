document.addEventListener('DOMContentLoaded', function () {
    const app    = document.getElementById('kpi-scholar-app');
    const status = document.getElementById('kpi-scholar-status');
    const grid   = document.getElementById('kpi-scholar-grid');

    if (!app) return;

    let allWorks = [];
    const orcid  = kpiScholarConfig.orcid;
    const mailto = kpiScholarConfig.mailto || '';

    // ── Контролі ──────────────────────────────────────────────────────────
    const controls = document.createElement('div');
    controls.id = 'kpi-scholar-controls';
    controls.innerHTML = `
        <div class="kpi-scholar-search-wrap">
            <span class="kpi-scholar-search-icon">🔍</span>
            <input type="text" id="kpi-scholar-search" placeholder="Пошук за назвою, автором...">
        </div>
        <select id="kpi-scholar-year">
            <option value="">Всі роки</option>
        </select>
        <select id="kpi-scholar-sort">
            <option value="year-desc">Рік ↓</option>
            <option value="year-asc">Рік ↑</option>
            <option value="title">Назва А-Я</option>
        </select>
    `;
    status.after(controls);

    document.getElementById('kpi-scholar-search').addEventListener('input', render);
    document.getElementById('kpi-scholar-year').addEventListener('change', render);
    document.getElementById('kpi-scholar-sort').addEventListener('change', render);

    function fillYears() {
        const years = [...new Set(allWorks.map(w => w.year).filter(Boolean))].sort((a,b) => b-a);
        const sel = document.getElementById('kpi-scholar-year');
        years.forEach(y => {
            const opt = document.createElement('option');
            opt.value = y; opt.textContent = y;
            sel.appendChild(opt);
        });
    }

    // ── Рендер ────────────────────────────────────────────────────────────
    function render() {
        const query = document.getElementById('kpi-scholar-search').value.toLowerCase();
        const year  = document.getElementById('kpi-scholar-year').value;
        const sort  = document.getElementById('kpi-scholar-sort').value;

        let works = allWorks.filter(w => {
            if (year && w.year !== year) return false;
            if (query && !(w.title + ' ' + w.authors.join(' ')).toLowerCase().includes(query)) return false;
            return true;
        });

        works = [...works].sort((a, b) => {
            if (sort === 'year-desc') return (b.year || '0') > (a.year || '0') ? 1 : -1;
            if (sort === 'year-asc')  return (a.year || '0') > (b.year || '0') ? 1 : -1;
            if (sort === 'title')     return (a.title || '').localeCompare(b.title || '', 'uk');
            return 0;
        });

        status.textContent = `${works.length} публікацій`;

        if (!works.length) {
            grid.innerHTML = '<p class="kpi-scholar-empty">Нічого не знайдено</p>';
            return;
        }

        grid.innerHTML = works.map(work => {
            const t = typeInfo(work.type);
            const badges = [
                `<span class="kpi-scholar-type kpi-scholar-type--${t.cls}">${esc(t.label)}</span>`,
                work.year ? `<span class="kpi-scholar-year">${work.year}</span>` : '',
            ].filter(Boolean).join('');

            const titleHtml = work.url
                ? `<a href="${esc(work.url)}" target="_blank" rel="noopener">${esc(work.title || 'Без назви')}</a>`
                : esc(work.title || 'Без назви');

            const abstractHtml = work.abstract
                ? `<details><summary>Анотація</summary><p class="kpi-scholar-abstract">${esc(work.abstract)}</p></details>`
                : '';

            return `
            <div class="kpi-scholar-item">
                <div class="kpi-scholar-meta">${badges}</div>
                <h3 class="kpi-scholar-title">${titleHtml}</h3>
                ${work.authors.length ? `<p class="kpi-scholar-authors">${esc(work.authors.join(', '))}</p>` : ''}
                ${abstractHtml}
            </div>`;
        }).join('');
    }

    // ── Крок 1: ORCID → список робіт з put-codes і DOI ────────────────────
    fetch('https://pub.orcid.org/v3.0/' + orcid + '/works', {
        headers: { 'Accept': 'application/json' }
    })
    .then(r => r.json())
    .then(data => {
        const groups = data.group || [];
        if (!groups.length) {
            status.textContent = 'Публікацій не знайдено';
            return;
        }

        status.textContent = `Завантажуємо деталі (${groups.length} робіт)...`;

        // Базові дані з ORCID summary
        const base = groups.map(g => {
            const s      = g['work-summary'][0];
            const extIds = g['external-ids']['external-id'] || [];
            const doiObj = extIds.find(e => e['external-id-type'] === 'doi');
            const doi    = doiObj ? doiObj['external-id-value'].replace(/^https?:\/\/doi\.org\//i, '') : '';

            return {
                title:    s.title?.title?.value || '',
                year:     s['publication-date']?.year?.value || '',
                type:     s.type || '',
                url:      doi ? 'https://doi.org/' + doi : (s.url?.value || ''),
                doi:      doi,
                authors:  [],
                abstract: '',
            };
        }).filter(w => w.title);

        // Крок 2: Crossref по DOI для авторів і abstract
        const withDoi    = base.filter(w => w.doi);
        const withoutDoi = base.filter(w => !w.doi);

        const crossrefUrl = doi => {
            const url = 'https://api.crossref.org/works/' + encodeURIComponent(doi);
            return mailto ? url + '?mailto=' + encodeURIComponent(mailto) : url;
        };

        Promise.allSettled(
            withDoi.map(w =>
                fetch(crossrefUrl(w.doi))
                    .then(r => r.ok ? r.json() : null)
                    .catch(() => null)
            )
        ).then(results => {
            results.forEach((result, i) => {
                if (result.status !== 'fulfilled' || !result.value) return;
                const msg = result.value.message;
                if (!msg) return;

                // Автори
                const authors = (msg.author || []).map(a =>
                    [a.given, a.family].filter(Boolean).join(' ')
                );
                if (authors.length) withDoi[i].authors = authors;

                // Abstract — Crossref повертає з HTML тегами, чистимо
                if (msg.abstract) {
                    withDoi[i].abstract = msg.abstract.replace(/<[^>]+>/g, '').trim();
                }

                // Уточнюємо тип
                if (msg.type) withDoi[i].type = msg.type;
            });

            allWorks = [...withDoi, ...withoutDoi].sort((a, b) =>
                (b.year || '0') > (a.year || '0') ? 1 : -1
            );

            fillYears();
            render();
        });
    })
    .catch(err => {
        status.textContent = 'Помилка завантаження';
        console.error('KPI Scholar error:', err);
    });
});

// ── Хелпери ───────────────────────────────────────────────────────────────
function typeInfo(type) {
    const map = {
        'journal-article':      { label: 'Стаття',       cls: 'article' },
        'JOURNAL_ARTICLE':      { label: 'Стаття',       cls: 'article' },
        'book-chapter':         { label: 'Розділ книги', cls: 'chapter' },
        'BOOK_CHAPTER':         { label: 'Розділ книги', cls: 'chapter' },
        'proceedings-article':  { label: 'Конференція',  cls: 'proceedings' },
        'CONFERENCE_PAPER':     { label: 'Конференція',  cls: 'proceedings' },
        'CONFERENCE_ABSTRACT':  { label: 'Тези',         cls: 'proceedings' },
        'book':                 { label: 'Книга',        cls: 'book' },
        'BOOK':                 { label: 'Книга',        cls: 'book' },
        'preprint':             { label: 'Препринт',     cls: 'preprint' },
        'PREPRINT':             { label: 'Препринт',     cls: 'preprint' },
        'dissertation':         { label: 'Дисертація',   cls: 'other' },
        'DISSERTATION':         { label: 'Дисертація',   cls: 'other' },
    };
    return map[type] || { label: type?.replace(/_/g, ' ') || 'Інше', cls: 'other' };
}

function esc(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;')
        .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
