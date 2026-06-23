/**
 * AI 简报卡片交互
 * - 手动刷新：POST /api/briefing/generate，成功后轮询 /api/briefing/latest
 * - 查看完整简报：弹窗展示大盘、异动 TOP5、AI 解读
 * - A-share 红涨绿跌语义
 */

export const POLL_INTERVAL_MS = 5000;
export const MAX_POLL_MS = 60000;
export const COOLDOWN_SECONDS = 30;

/**
 * 渲染简报卡片内容，返回 HTML 字符串。
 * @param {object} briefing
 * @returns {string}
 */
export function renderCardContent(briefing) {
    const indicesHtml = briefing.market_indices
        ? Object.entries(briefing.market_indices).map(function ([name, data]) {
              const current = data.current || 0;
              const change = data.change_pct || 0;
              const colorClass = change > 0 ? 'text-market-up' : change < 0 ? 'text-market-down' : 'text-on-surface-variant';
              const sign = change > 0 ? '+' : '';
              return '<div class="flex flex-col">' +
                  '<span class="font-label-caps text-label-caps text-on-surface-variant">' + name + '</span>' +
                  '<span class="font-data-table text-data-table ' + colorClass + '">' + current.toFixed(2) + ' <span class="text-xs">(' + sign + change.toFixed(2) + '%)</span></span>' +
                  '</div>';
          }).join('')
        : '';

    const moversHtml = (briefing.top_movers || []).slice(0, 5).map(function (m) {
        const pct = m.change_percent || 0;
        const colorClass = pct > 0 ? 'text-market-up' : pct < 0 ? 'text-market-down' : 'text-on-surface-variant';
        const sign = pct > 0 ? '+' : '';
        return '<div class="flex justify-between items-center py-2 border-b border-outline-variant/30 last:border-0">' +
            '<div class="flex flex-col">' +
            '<span class="font-body-md text-body-md text-on-surface">' + m.stock_name + '</span>' +
            '<span class="font-data-table text-data-table text-on-surface-variant">' + m.stock_code + '</span>' +
            '</div>' +
            '<span class="font-data-table text-data-table ' + colorClass + '">' + sign + pct.toFixed(2) + '%</span>' +
            '</div>';
    }).join('');

    const insightsHtml = (briefing.insights || []).slice(0, 2).map(function (insight) {
        return '<div class="bg-surface-raised p-3 rounded border border-outline-variant/50 border-l-4 border-l-primary-container">' +
            '<p class="font-body-md text-body-md text-on-surface-variant">' + insight + '</p>' +
            '</div>';
    }).join('');

    const degradedBanner = briefing.is_degraded
        ? '<div class="bg-error/10 border border-error rounded p-3 flex items-center gap-2">' +
          '<span class="material-symbols-outlined text-error">error</span>' +
          '<span class="font-body-md text-body-md text-error">' + (briefing.degraded_reason || '简报已降级，展示模板数据') + '</span>' +
          '</div>'
        : '';

    return '<div class="space-y-4">' +
        (indicesHtml ? '<div class="grid grid-cols-3 gap-2 bg-surface-raised/30 p-3 rounded border border-outline-variant/30">' + indicesHtml + '</div>' : '') +
        (moversHtml ? '<div class="bg-surface-raised/30 p-3 rounded border border-outline-variant/30">' +
            '<h3 class="font-label-caps text-label-caps text-on-surface-variant mb-2">异动 TOP5</h3>' +
            '<div class="space-y-1">' + moversHtml + '</div>' +
            '</div>' : '') +
        (insightsHtml ? '<div class="space-y-2">' + insightsHtml + '</div>' : '') +
        degradedBanner +
        '</div>';
}

/**
 * 渲染简报弹窗内容，返回 HTML 字符串。
 * @param {object} briefing
 * @returns {string}
 */
export function renderModalContent(briefing) {
    const indicesRows = briefing.market_indices
        ? Object.entries(briefing.market_indices).map(function ([name, data]) {
              const current = data.current || 0;
              const change = data.change_pct || 0;
              const colorClass = change > 0 ? 'text-market-up' : change < 0 ? 'text-market-down' : 'text-on-surface-variant';
              const sign = change > 0 ? '+' : '';
              return '<tr class="border-b border-outline-variant/30">' +
                  '<td class="py-2 font-body-md text-on-surface">' + name + '</td>' +
                  '<td class="py-2 font-data-table text-right ' + colorClass + '">' + current.toFixed(2) + '</td>' +
                  '<td class="py-2 font-data-table text-right ' + colorClass + '">' + sign + change.toFixed(2) + '%</td>' +
                  '</tr>';
          }).join('')
        : '';

    const moversRows = (briefing.top_movers || []).map(function (m) {
        const pct = m.change_percent || 0;
        const colorClass = pct > 0 ? 'text-market-up' : pct < 0 ? 'text-market-down' : 'text-on-surface-variant';
        const sign = pct > 0 ? '+' : '';
        return '<tr class="border-b border-outline-variant/30">' +
            '<td class="py-2 font-body-md text-on-surface">' + m.stock_name + '</td>' +
            '<td class="py-2 font-data-table text-on-surface-variant">' + m.stock_code + '</td>' +
            '<td class="py-2 font-data-table">' + (m.move_type || '-') + '</td>' +
            '<td class="py-2 font-data-table text-right ' + colorClass + '">' + sign + pct.toFixed(2) + '%</td>' +
            '</tr>';
    }).join('');

    const insightsList = (briefing.insights || []).map(function (insight) {
        return '<li class="font-body-md text-body-md text-on-surface-variant">' + insight + '</li>';
    }).join('');

    return '<div class="space-y-6">' +
        (indicesRows ? '<div><h3 class="font-headline-md text-headline-md text-primary-fixed mb-2">大盘指数</h3>' +
            '<table class="w-full"><thead><tr class="text-left font-label-caps text-label-caps text-on-surface-variant">' +
            '<th class="py-2">指数</th><th class="py-2 text-right">点位</th><th class="py-2 text-right">涨跌幅</th>' +
            '</tr></thead><tbody>' + indicesRows + '</tbody></table></div>' : '') +
        (moversRows ? '<div><h3 class="font-headline-md text-headline-md text-primary-fixed mb-2">异动 TOP5</h3>' +
            '<table class="w-full"><thead><tr class="text-left font-label-caps text-label-caps text-on-surface-variant">' +
            '<th class="py-2">名称</th><th class="py-2">代码</th><th class="py-2">类型</th><th class="py-2 text-right">涨跌幅</th>' +
            '</tr></thead><tbody>' + moversRows + '</tbody></table></div>' : '') +
        (insightsList ? '<div><h3 class="font-headline-md text-headline-md text-primary-fixed mb-2">AI 解读</h3>' +
            '<ul class="list-disc list-inside space-y-2">' + insightsList + '</ul></div>' : '') +
        '</div>';
}

/**
 * 创建简报控制器，封装 DOM 操作与 fetch 交互。
 * @param {object} options
 * @returns {object}
 */
export function createBriefingController(options) {
    const {
        generateBtn,
        statusEl,
        modal,
        modalBody,
        container,
        footer,
        pollIntervalMs = POLL_INTERVAL_MS,
        maxPollMs = MAX_POLL_MS,
        cooldownSeconds = COOLDOWN_SECONDS,
    } = options;

    let pollTimer = null;
    let pollStartTime = 0;
    let cooldownTimer = null;

    function setStatus(text, type) {
        if (!statusEl) return;
        statusEl.textContent = text;
        statusEl.className = 'font-body-md text-body-md min-h-[20px] ' + (type === 'error' ? 'text-error' : type === 'success' ? 'text-market-down' : 'text-on-surface-variant');
    }

    function setCooldown(seconds) {
        if (!generateBtn) return;
        generateBtn.disabled = true;
        let remaining = seconds;
        const updateText = function () {
            if (statusEl) statusEl.textContent = '冷却中 (' + remaining + 's)';
        };
        updateText();
        cooldownTimer = setInterval(function () {
            remaining -= 1;
            updateText();
            if (remaining <= 0) {
                clearInterval(cooldownTimer);
                cooldownTimer = null;
                generateBtn.disabled = false;
                setStatus('');
            }
        }, 1000);
    }

    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    function updateCard(briefing) {
        if (!container || !briefing) return;

        container.innerHTML = renderCardContent(briefing);

        if (footer) {
            footer.classList.remove('hidden');
        }

        updateModal(briefing);
    }

    function updateModal(briefing) {
        if (!modalBody || !briefing) return;
        modalBody.innerHTML = renderModalContent(briefing);
    }

    function fetchLatest() {
        fetch('/api/briefing/latest')
            .then(function (response) {
                if (response.status === 404) return null;
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function (data) {
                if (!data) return;
                updateCard(data);
                setStatus('简报已更新', 'success');
                setCooldown(cooldownSeconds);
                stopPolling();
            })
            .catch(function (err) {
                console.warn('[Briefing] 轮询失败:', err);
            });
    }

    function startPolling() {
        stopPolling();
        pollStartTime = Date.now();
        pollTimer = setInterval(function () {
            fetchLatest();
            if (Date.now() - pollStartTime > maxPollMs) {
                stopPolling();
                setStatus('轮询超时，请稍后手动刷新', 'error');
                if (generateBtn) generateBtn.disabled = false;
            }
        }, pollIntervalMs);
    }

    function onGenerate() {
        if (!generateBtn) return;
        generateBtn.disabled = true;
        setStatus('正在触发简报生成...');

        fetch('/api/briefing/generate', { method: 'POST' })
            .then(function (response) {
                if (response.status === 429) {
                    setCooldown(cooldownSeconds);
                    throw new Error('cooldown');
                }
                if (response.status === 422) {
                    setStatus('今日非交易日，暂无简报', 'error');
                    generateBtn.disabled = false;
                    throw new Error('non-trading');
                }
                if (!response.ok) throw new Error('HTTP ' + response.status);
                setStatus('已触发，轮询最新简报中...');
                startPolling();
            })
            .catch(function (err) {
                if (err.message === 'cooldown' || err.message === 'non-trading') return;
                console.error('[Briefing] 触发失败:', err);
                setStatus('触发失败，请稍后重试', 'error');
                generateBtn.disabled = false;
            });
    }

    return {
        setStatus,
        setCooldown,
        stopPolling,
        updateCard,
        updateModal,
        fetchLatest,
        startPolling,
        onGenerate,
    };
}

(function () {
    'use strict';

    const card = document.getElementById('briefing-card');
    if (!card) return;

    const generateBtn = document.getElementById('briefing-generate-btn');
    const statusEl = document.getElementById('briefing-status');
    const modal = document.getElementById('briefing-modal');
    const modalOpenBtn = document.getElementById('briefing-modal-open');
    const modalCloseBtn = document.getElementById('briefing-modal-close');

    const ctrl = createBriefingController({
        generateBtn,
        statusEl,
        modal,
        modalBody: modal ? modal.querySelector('#briefing-modal-body') : null,
        container: document.getElementById('briefing-content'),
        footer: document.getElementById('briefing-footer'),
    });

    if (generateBtn) {
        generateBtn.addEventListener('click', ctrl.onGenerate);
    }

    if (modalOpenBtn && modal) {
        modalOpenBtn.addEventListener('click', function () {
            modal.classList.remove('hidden');
        });
    }

    if (modalCloseBtn && modal) {
        modalCloseBtn.addEventListener('click', function () {
            modal.classList.add('hidden');
        });
    }

    if (modal) {
        modal.addEventListener('click', function (event) {
            if (event.target === modal) modal.classList.add('hidden');
        });
    }

    // 初始化：服务端渲染的简报对象若存在，同步更新弹窗内容
    const initialBriefing = window.__initialBriefing__;
    if (initialBriefing) {
        ctrl.updateModal(initialBriefing);
    }
})();
