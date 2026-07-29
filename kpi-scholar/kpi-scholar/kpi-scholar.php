<?php
/**
 * Plugin Name: KPI Scholar
 * Description: Список публікацій автора з ORCID + Crossref
 * Version: 1.2
 */

if (!defined('ABSPATH')) exit;

add_action('wp_enqueue_scripts', function () {
    wp_register_style('kpi-scholar-style', plugins_url('kpi-scholar.css', __FILE__), [], '1.2');
    wp_register_script('kpi-scholar-script', plugins_url('kpi-scholar.js', __FILE__), [], '1.2', true);
});

// ── Шорткод [kpi_scholar orcid="0000-0002-9851-7109"] ────────────────────
add_shortcode('kpi_scholar', function ($atts) {
    $atts = shortcode_atts(['orcid' => '', 'mailto' => get_option('admin_email')], $atts);
    if (!$atts['orcid']) return '';

    wp_enqueue_style('kpi-scholar-style');
    wp_enqueue_script('kpi-scholar-script');
    wp_localize_script('kpi-scholar-script', 'kpiScholarConfig', [
        'orcid'  => esc_attr($atts['orcid']),
        'mailto' => esc_attr($atts['mailto']),
    ]);

    return '<div id="kpi-scholar-app">
        <div id="kpi-scholar-status">Завантажуємо...</div>
        <div id="kpi-scholar-grid"></div>
    </div>';
});
