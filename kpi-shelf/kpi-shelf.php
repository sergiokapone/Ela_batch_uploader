<?php
/**
 * Plugin Name: KPI Shelf
 * Description: Книжкова полиця публікацій автора з ela.kpi.ua
 * Version: 1.0
 */

if (!defined('ABSPATH')) exit;

add_action('rest_api_init', function () {
    register_rest_route('kpi/v1', '/shelf-works', [
        'methods'             => 'GET',
        'callback'            => 'kpi_shelf_get_works',
        'permission_callback' => '__return_true',
    ]);
        register_rest_route('kpi/v1', '/shelf-collection', [
        'methods'             => 'GET',
        'callback'            => 'kpi_shelf_get_collection',
        'permission_callback' => '__return_true',
    ]);
});

function kpi_shelf_get_works(WP_REST_Request $request) {
    try {
        $author_raw = $request->get_param('author') ?? '';
        $enc        = $request->get_param('enc') ?? '';
        if ($enc === 'base64') {
            $b64      = str_replace(['-', '_'], ['+', '/'], $author_raw);
            $padded   = $b64 . str_repeat('=', (4 - strlen($b64) % 4) % 4);
            $author_raw = base64_decode($padded);
        }
        $author = trim(wp_strip_all_tags($author_raw));
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
                'scope'   => $scope,
                'dsoType' => 'item',
                'page'    => 0,
                'size'    => 100,
            ], '', '&', PHP_QUERY_RFC3986);
            
            $params .= '&f.author=' . rawurlencode($author) . ',equals';
            
            error_log('ELA URL: https://ela.kpi.ua/server/api/discover/search/objects?' . $params);
            
            $resp = wp_remote_get(
                'https://ela.kpi.ua/server/api/discover/search/objects?' . $params,
                ['timeout' => 30, 'sslverify' => false, 'headers' => [
                    'Accept' => 'application/json',
                    'User-Agent' => 'Mozilla/5.0 (kpi-shelf WP plugin)',
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

                $meta = $item['metadata'] ?? [];
                $date = $meta['dc.date.issued'][0]['value'] ?? '';
                $abstract = $meta['dc.description.abstractuk'][0]['value']
                         ?? $meta['dc.description.abstract'][0]['value']
                         ?? '';

                // Thumbnail
                $thumb = '';
                $tr = wp_remote_get(
                    "https://ela.kpi.ua/server/api/core/items/{$uuid}/thumbnail",
                    ['timeout' => 10, 'sslverify' => false, 'headers' => [
                        'Accept' => 'application/json',
                        'User-Agent' => 'Mozilla/5.0 (kpi-shelf WP plugin)',
                    ]]
                );
                if (!is_wp_error($tr) && wp_remote_retrieve_response_code($tr) === 200) {
                    $tb = json_decode(wp_remote_retrieve_body($tr), true);
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


function kpi_shelf_get_collection(WP_REST_Request $request) {
    try {
        $scope = sanitize_text_field($request->get_param('scope') ?? '');
        if (!$scope) {
            return new WP_Error('no_scope', 'Параметр scope обов\'язковий', ['status' => 400]);
        }

        $cache_key = 'kpi_shelf_col_' . md5($scope);
        $cached    = get_transient($cache_key);
        if ($cached !== false) return rest_ensure_response($cached);

        $all  = [];
        $page = 0;

        do {
            $params = http_build_query([
                'scope'   => $scope,
                'dsoType' => 'item',
                'page'    => $page,
                'size'    => 100,
            ], '', '&', PHP_QUERY_RFC3986);

            $resp = wp_remote_get(
                'https://ela.kpi.ua/server/api/discover/search/objects?' . $params,
                ['timeout' => 30, 'sslverify' => false, 'headers' => [
                    'Accept'     => 'application/json',
                    'User-Agent' => 'Mozilla/5.0 (kpi-shelf WP plugin)',
                ]]
            );

            if (is_wp_error($resp) || wp_remote_retrieve_response_code($resp) !== 200) break;

            $body        = json_decode(wp_remote_retrieve_body($resp), true);
            $objects     = $body['_embedded']['searchResult']['_embedded']['objects'] ?? [];
            $total_pages = (int)($body['_embedded']['searchResult']['page']['totalPages'] ?? 1);

            foreach ($objects as $obj) {
                $item = $obj['_embedded']['indexableObject'] ?? null;
                if (!$item || $item['type'] !== 'item') continue;

                $meta     = $item['metadata'] ?? [];
                $date     = $meta['dc.date.issued'][0]['value'] ?? '';

                $all[] = [
                    'uuid'    => $item['uuid'] ?? '',
                    'url'     => 'https://ela.kpi.ua/handle/' . ($item['handle'] ?? ''),
                    'title'   => $meta['dc.title'][0]['value'] ?? '',
                    'authors' => array_column($meta['dc.contributor.author'] ?? [], 'value'),
                    'year'    => substr($date, 0, 4),
                    'type'    => $meta['dc.type'][0]['value'] ?? '',
                ];
            }

            $page++;
        } while ($page < $total_pages);

        usort($all, fn($a, $b) => strcmp($b['year'], $a['year']));
        set_transient($cache_key, $all, DAY_IN_SECONDS);
        return rest_ensure_response($all);

    } catch (Throwable $e) {
        return new WP_Error('php_error', $e->getMessage(), ['status' => 500]);
    }
}


add_action('wp_enqueue_scripts', function () {
    wp_register_style('kpi-shelf-style', plugins_url('kpi-shelf.css', __FILE__), [], '1.1');
    wp_register_script('kpi-shelf-script', plugins_url('kpi-shelf.js', __FILE__), [], '1.1', true);
});

add_shortcode('kpi_author_works', function ($atts) {
    $atts = shortcode_atts(['author' => ''], $atts);
    wp_enqueue_style('kpi-shelf-style');
    wp_enqueue_script('kpi-shelf-script');
    wp_localize_script('kpi-shelf-script', 'kpiShelfConfig', [
        'apiUrl' => rest_url('kpi/v1/shelf-works'),
        'author' => esc_attr($atts['author']),
    ]);
    return '<div id="kpi-shelf-app"><div id="kpi-shelf-status">Завантажуємо...</div><div id="kpi-shelf-grid"></div></div>';
});

add_shortcode('kpi_shelf_collection', function ($atts) {
    $atts = shortcode_atts(['scope' => ''], $atts);
    if (!$atts['scope']) return '';
    wp_enqueue_style('kpi-shelf-style');
    wp_enqueue_script('kpi-shelf-script');
    wp_localize_script('kpi-shelf-script', 'kpiShelfConfig', [
        'apiUrl' => rest_url('kpi/v1/shelf-collection'),
        'scope'  => esc_attr($atts['scope']),
    ]);
    return '<div id="kpi-shelf-app"><div id="kpi-shelf-status">Завантажуємо...</div><div id="kpi-shelf-grid"></div></div>';
});
