/**
 * Dashboard 自动刷新逻辑
 * - 60 秒轮询 /market_data
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

    const marketContainer = document.getElementById('market-data-container');
    if (!marketContainer) return;

    function fetchMarketData() {
        fetch('/market_data')
            .then(function (response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.text();
            })
            .then(function (html) {
                if (html !== lastContent) {
                    marketContainer.innerHTML = html;
                    lastContent = html;
                }
                checkDegradation();
            })
            .catch(function (err) {
                console.warn('[Dashboard] 刷新失败:', err);
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
