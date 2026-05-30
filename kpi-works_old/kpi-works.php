<?php
/**
 * Plugin Name: KPI Works
 * Description: Показує магістерські та бакалаврські роботи з ela.kpi.ua
 * Version: 2.0
 */

// ── Щоденне оновлення кешу через WP Cron ─────────────────────────────────
register_activation_hook(__FILE__, function () {
    if (!wp_next_scheduled('kpi_daily_refresh')) {
        wp_schedule_event(strtotime('tomorrow 03:00:00'), 'daily', 'kpi_daily_refresh');
    }
});
register_deactivation_hook(__FILE__, function () {
    wp_clear_scheduled_hook('kpi_daily_refresh');
});
add_action('kpi_daily_refresh', function () {
    delete_transient('kpi_works_magistr');
    delete_transient('kpi_works_bakalavr');
    // Одразу перекачуємо щоб перший відвідувач не чекав
    kpi_get_collection('magistr');
    kpi_get_collection('bakalavr');
});

add_action('rest_api_init', function () {
    register_rest_route('kpi/v1', '/works', [
        'methods'             => 'GET',
        'callback'            => 'kpi_get_works',
        'permission_callback' => '__return_true',
    ]);
    // Endpoint для ручного скидання кешу (тільки для адмінів)
    register_rest_route('kpi/v1', '/clear-cache', [
        'methods'             => 'POST',
        'callback'            => function() {
            delete_transient('kpi_works_magistr');
            delete_transient('kpi_works_bakalavr');
            return ['cleared' => true];
        },
        'permission_callback' => fn() => current_user_can('manage_options'),
    ]);
    register_rest_route('kpi/v1', '/author-works', [
        'methods'             => 'GET',
        'callback'            => 'kpi_get_author_works',
        'permission_callback' => '__return_true',
    ]);
});

// ── Завантажити ВСІ роботи колекції з ela.kpi.ua і закешувати ──────────────
function kpi_fetch_all(string $uuid): array|WP_Error {
    $page      = 0;
    $page_size = 100; // максимум що дозволяє DSpace
    $all       = [];

    do {
        $args = http_build_query([
            'scope'   => $uuid,
            'dsoType' => 'item',
            'page'    => $page,
            'size'    => $page_size,
        ], '', '&', PHP_QUERY_RFC3986);

        $url = 'https://ela.kpi.ua/server/api/discover/search/objects?' . $args;

        $resp = wp_remote_get($url, [
            'timeout'   => 60,
            'sslverify' => false,
            'headers'   => [
                'Accept'     => 'application/json',
                'User-Agent' => 'Mozilla/5.0 (kpi-works WP plugin)',
            ],
        ]);

        if (is_wp_error($resp)) return $resp;

        $code = wp_remote_retrieve_response_code($resp);
        $body = json_decode(wp_remote_retrieve_body($resp), true);

        if ($code !== 200 || !$body) {
            return new WP_Error('upstream_error', "ela.kpi.ua HTTP $code на сторінці $page");
        }

        $objects    = $body['_embedded']['searchResult']['_embedded']['objects'] ?? [];
        $page_info  = $body['_embedded']['searchResult']['page'] ?? [];
        $total_pages = (int)($page_info['totalPages'] ?? 1);

        foreach ($objects as $obj) {
            $item = $obj['_embedded']['indexableObject'] ?? null;
            if (!$item || $item['type'] !== 'item') continue;

            $meta      = $item['metadata'] ?? [];
            $date      = $meta['dc.date.issued'][0]['value'] ?? '';
            $item_year = substr($date, 0, 4);

            $all[] = [
                'uuid'     => $item['uuid'] ?? '',
                'url'      => 'https://ela.kpi.ua/handle/' . ($item['handle'] ?? ''),
                'title'    => $meta['dc.title'][0]['value'] ?? '',
                'authors'  => array_column($meta['dc.contributor.author'] ?? [], 'value'),
                'advisors' => array_column($meta['dc.contributor.advisor'] ?? [], 'value'),
                'year'     => $item_year,
                'abstract' => $meta['dc.description.abstract'][0]['value'] ?? '',
                'keywords' => array_column($meta['dc.subject'] ?? [], 'value'),
            ];
        }

        $page++;
    } while ($page < $total_pages);

    return $all;
}

// ── Отримати колекцію (з кешу або завантажити) ─────────────────────────────
function kpi_get_collection(string $collection): array|WP_Error {
    $collections = [
        'magistr'  => 'e475e84c-48ff-4236-9633-694b923e4a82',
        'bakalavr' => '13647e65-d1d5-49d3-abfb-49957e3b0d00',
    ];

    if (!isset($collections[$collection])) {
        return new WP_Error('invalid_collection', 'Невідома колекція', ['status' => 400]);
    }

    $cache_key = 'kpi_works_' . $collection;
    $cached    = get_transient($cache_key);

    if ($cached !== false) return $cached;

    // Кешу нема — качаємо все з ela.kpi.ua
    $works = kpi_fetch_all($collections[$collection]);
    if (is_wp_error($works)) return $works;

    // Додаємо collection до кожного запису і кешуємо на 24 години
    foreach ($works as &$w) $w['collection'] = $collection;
    set_transient($cache_key, $works, DAY_IN_SECONDS);

    return $works;
}

// ── REST endpoint: фільтрація і пагінація по локальному кешу ───────────────
function kpi_get_works(WP_REST_Request $request) {
    try {
        $collection = $request->get_param('collection') ?? 'magistr';
        $year       = $request->get_param('year') ?? '';
        $raw   = $request->get_param('query') ?? '';
        $enc   = $request->get_param('q_enc') ?? '';
        if ($enc === 'base64') {
            $raw = base64_decode($raw);
        }
        $query = mb_strtolower(wp_strip_all_tags($raw));
        $page       = max(0, intval($request->get_param('page') ?? 0));
        $page_size  = 20; // менше на сторінці бо фільтруємо локально

        $all = kpi_get_collection($collection);
        if (is_wp_error($all)) return $all;

        // ── Фільтрація ────────────────────────────────────────────────────
        // Сортуємо по прізвищу першого автора — українська абетка
        // Витягуємо прізвище (до коми) і нормалізуємо латинські двійники
        $surname = function(string $full): string {
            $s = trim(explode(',', $full)[0]); // "Ільчук, Юлія" → "Ільчук"
            return strtr($s, ['I'=>'І','i'=>'і','A'=>'А','E'=>'Е','O'=>'О',
                               'P'=>'Р','C'=>'С','X'=>'Х','B'=>'В','H'=>'Н']);
        };
        if (class_exists('Collator')) {
            $collator = new Collator('uk_UA');
            usort($all, function($a, $b) use ($collator, $surname) {
                return $collator->compare(
                    $surname($a['authors'][0] ?? ''),
                    $surname($b['authors'][0] ?? '')
                );
            });
        } else {
            usort($all, function($a, $b) use ($surname) {
                return mb_strtolower($surname($a['authors'][0] ?? ''))
                   <=> mb_strtolower($surname($b['authors'][0] ?? ''));
            });
        }

        $filtered = array_values(array_filter($all, function($w) use ($year, $query) {

            // Фільтр по року
            if ($year && $w['year'] !== $year) return false;

            // Пошук по назві, авторах, керівниках
            if ($query) {
                $haystack = mb_strtolower(
                    $w['title'] . ' ' .
                    implode(' ', $w['authors']) . ' ' .
                    implode(' ', $w['advisors'])
                );
                if (mb_strpos($haystack, $query) === false) return false;
            }

            return true;
        }));

        // ── Пагінація ─────────────────────────────────────────────────────
        $total       = count($filtered);
        $total_pages = (int)ceil($total / $page_size);
        $works       = array_slice($filtered, $page * $page_size, $page_size);

        return rest_ensure_response([
            'works'       => $works,
            'total'       => $total,
            'total_pages' => max(1, $total_pages),
            'page'        => $page,
        ]);

    } catch (Throwable $e) {
        return new WP_Error('php_error', $e->getMessage(), [
            'status' => 500,
            'file'   => $e->getFile(),
            'line'   => $e->getLine(),
        ]);
    }
}

// ── Підключаємо JS/CSS ─────────────────────────────────────────────────────
add_action('wp_enqueue_scripts', function () {
    wp_register_style('kpi-works-style', plugins_url('kpi-style.css', __FILE__));
    wp_register_script('kpi-works-script', plugins_url('kpi-script.js', __FILE__), [], '2.1', true);
    wp_register_style('kpi-shelf-style', plugins_url('kpi-shelf.css', __FILE__));
    wp_register_script('kpi-shelf-script', plugins_url('kpi-shelf.js', __FILE__), [], '1.0', true);
    wp_localize_script('kpi-works-script', 'kpiWorksConfig', [
        'apiUrl' => rest_url('kpi/v1/works'),
    ]);
});

// ── Шорткод [kpi_works] ────────────────────────────────────────────────────
add_shortcode('kpi_works', function () {
    wp_enqueue_script('kpi-works-script');
    wp_enqueue_style('kpi-works-style');

    ob_start(); ?>
    <div id="kpi-works-app">
        <div class="kpi-filters">
            <div class="kpi-search-wrap">
                <span class="kpi-search-icon">🔍</span>
                <input type="text" id="kpi-search" placeholder="Пошук за назвою, автором, керівником...">
            </div>
            <select id="kpi-collection">
                <option value="magistr">Магістерські</option>
                <option value="bakalavr">Бакалаврські</option>
            </select>
            <select id="kpi-year">
                <option value="">Всі роки</option>
                <?php
                for ($y = intval(date('Y')); $y >= 2015; $y--) {
                    echo "<option value=\"$y\">$y</option>";
                }
                ?>
            </select>
        </div>
        <div id="kpi-status"></div>
        <div id="kpi-list"></div>
        <div id="kpi-pagination"></div>
    </div>
    <?php
    return ob_get_clean();
});

function kpi_get_author_works(WP_REST_Request $request) {
    try {
        $author = sanitize_text_field($request->get_param('author') ?? '');
        if (!$author) {
            return new WP_Error('no_author', 'Параметр author обов\'язковий', ['status' => 400]);
        }

        $cache_key = 'kpi_shelf_' . md5($author);
        $cached    = get_transient($cache_key);
        if ($cached !== false) return rest_ensure_response($cached);

        $scopes = [
            '228bd228-cc4d-44eb-8456-26c6b7804bb9',
            'bbd00047-58de-4bd9-bfa1-799c53edf020',
        ];

        $all  = [];
        $seen = [];

        foreach ($scopes as $scope) {
            $params = http_build_query([
                'scope'    => $scope,
                'dsoType'  => 'item',
                'page'     => 0,
                'size'     => 100,
                'f.author' => $author . ',equals',
            ], '', '&', PHP_QUERY_RFC3986);

            $resp = wp_remote_get(
                'https://ela.kpi.ua/server/api/discover/search/objects?' . $params,
                ['timeout' => 30, 'sslverify' => false, 'headers' => [
                    'Accept'     => 'application/json',
                    'User-Agent' => 'Mozilla/5.0 (kpi-works WP plugin)',
                ]]
            );

            if (is_wp_error($resp) || wp_remote_retrieve_response_code($resp) !== 200) continue;

            $body    = json_decode(wp_remote_retrieve_body($resp), true);
            $objects = $body['_embedded']['searchResult']['_embedded']['objects'] ?? [];

            foreach ($objects as $obj) {
                $item = $obj['_embedded']['indexableObject'] ?? null;
                if (!$item || $item['type'] !== 'item') continue;
                $uuid = $item['uuid'] ?? '';
                if (!$uuid || isset($seen[$uuid])) continue;
                $seen[$uuid] = true;

                $meta     = $item['metadata'] ?? [];
                $date     = $meta['dc.date.issued'][0]['value'] ?? '';
                $abstract = $meta['dc.description.abstractuk'][0]['value']
                         ?? $meta['dc.description.abstract'][0]['value']
                         ?? '';

                $thumb = '';
                $tr = wp_remote_get(
                    "https://ela.kpi.ua/server/api/core/items/{$uuid}/thumbnail",
                    ['timeout' => 10, 'sslverify' => false, 'headers' => [
                        'Accept'     => 'application/json',
                        'User-Agent' => 'Mozilla/5.0 (kpi-works WP plugin)',
                    ]]
                );
                if (!is_wp_error($tr) && wp_remote_retrieve_response_code($tr) === 200) {
                    $tb    = json_decode(wp_remote_retrieve_body($tr), true);
                    $thumb = $tb['_links']['content']['href'] ?? '';
                }

                $all[] = [
                    'uuid'      => $uuid,
                    'url'       => 'https://ela.kpi.ua/handle/' . ($item['handle'] ?? ''),
                    'title'     => $meta['dc.title'][0]['value'] ?? '',
                    'authors'   => array_column($meta['dc.contributor.author'] ?? [], 'value'),
                    'year'      => substr($date, 0, 4),
                    'abstract'  => $abstract,
                    'type'      => $meta['dc.type'][0]['value'] ?? '',
                    'thumbnail' => $thumb,
                ];
            }
        }

        usort($all, fn($a, $b) => strcmp($b['year'], $a['year']));
        set_transient($cache_key, $all, DAY_IN_SECONDS);
        return rest_ensure_response($all);

    } catch (Throwable $e) {
        return new WP_Error('php_error', $e->getMessage(), ['status' => 500]);
    }
}

add_shortcode('kpi_author_works', function ($atts) {
    $atts = shortcode_atts(['author' => ''], $atts);
    wp_enqueue_style('kpi-shelf-style');
    wp_enqueue_script('kpi-shelf-script');
    wp_localize_script('kpi-shelf-script', 'kpiShelfConfig', [
        'apiUrl' => rest_url('kpi/v1/author-works'),
        'author' => esc_attr($atts['author']),
    ]);
    return '<div id="kpi-shelf-app"><div id="kpi-shelf-status">Завантажуємо...</div><div id="kpi-shelf-grid"></div></div>';
});
