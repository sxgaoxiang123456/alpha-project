/**
 * Dashboard 自动刷新逻辑
 * - 60 秒轮询 /market_data
 * - ETag/304 支持：数据无变化时不更新 DOM
 * - 降级检测后自动暂停
 * - 数据源恢复后自动恢复
 */
(function () {
    'use strict';

    const POLL_INTERVAL_MS = 60000;
    const DEGRADED_SELECTOR = '[data-degraded="true"]';

    let timerId = null;
    let isPaused = false;
    let lastContent = '';
    let lastEtag = '';
    let isFirstLoad = true;

    const marketContainer = document.getElementById('market-data-container');
    if (!marketContainer) return;

    function fetchMarketData() {
        const headers = {};
        if (lastEtag) {
            headers['If-None-Match'] = lastEtag;
        }

        fetch('/market_data', { headers })
            .then(function (response) {
                // 304 无变化 — 不更新 DOM，只记录 ETag
                if (response.status === 304) {
                    const etag = response.headers.get('etag');
                    if (etag) lastEtag = etag;
                    return null;
                }
                if (!response.ok) throw new Error('HTTP ' + response.status);
                const etag = response.headers.get('etag');
                if (etag) lastEtag = etag;
                return response.text();
            })
            .then(function (html) {
                if (html === null) return; // 304，跳过
                if (html !== lastContent) {
                    marketContainer.innerHTML = html;
                    lastContent = html;
                    isFirstLoad = false;
                }
                checkDegradation();
            })
            .catch(function (err) {
                console.warn('[Dashboard] 刷新失败:', err);
                // 首次加载失败时保留骨架屏，不替换为空内容
                if (isFirstLoad) {
                    isFirstLoad = false;
                }
            });
    }

    function checkDegradation() {
        const degraded = document.querySelector(DEGRADED_SELECTOR);
        if (degraded && !isPaused) {
            pausePolling();
        } else if (!degraded && isPaused) {
            resumePolling();
        }
    }

    function startPolling() {
        if (timerId) return;
        timerId = setInterval(fetchMarketData, POLL_INTERVAL_MS);
    }

    function pausePolling() {
        if (timerId) {
            clearInterval(timerId);
            timerId = null;
        }
        isPaused = true;
        console.info('[Dashboard] 数据源降级，暂停自动刷新');
    }

    function resumePolling() {
        if (timerId) return;
        isPaused = false;
        startPolling();
        console.info('[Dashboard] 数据源恢复，恢复自动刷新');
    }

    // 使用 IntersectionObserver：页面不可见时暂停，可见时恢复
    const visibilityObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
            if (entry.isIntersecting && !isPaused) {
                startPolling();
            } else if (!entry.isIntersecting) {
                if (timerId) {
                    clearInterval(timerId);
                    timerId = null;
                }
            }
        });
    });

    visibilityObserver.observe(marketContainer);

    // 页面可见性 API：切换标签页时暂停/恢复
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            if (timerId) {
                clearInterval(timerId);
                timerId = null;
            }
        } else if (!isPaused) {
            startPolling();
            fetchMarketData();
        }
    });

    // 初始启动
    startPolling();
    fetchMarketData();
})();
