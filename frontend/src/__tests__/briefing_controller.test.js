import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { createBriefingController, COOLDOWN_SECONDS } from '../../public/js/briefing.js';

const handlers = [
    http.post('/api/briefing/generate', () => {
        return HttpResponse.json({ status: 'accepted' }, { status: 202 });
    }),
    http.get('/api/briefing/latest', () => {
        return HttpResponse.json({
            date: '2026-06-23',
            market_indices: { '上证指数': { current: 3000, change_pct: 1.2 } },
            top_movers: [{ stock_code: '600000', stock_name: '浦发银行', move_type: 'volume_spike', change_percent: 2.5 }],
            insights: ['大盘向好'],
            is_degraded: false,
        });
    }),
];

const server = setupServer(...handlers);

describe('createBriefingController contract mock', () => {
    let container;
    let statusEl;
    let generateBtn;
    let modalBody;

    beforeEach(() => {
        vi.useFakeTimers({ shouldAdvanceTime: true });
        server.listen({ onUnhandledRequest: 'error' });

        container = document.createElement('div');
        container.id = 'briefing-content';
        statusEl = document.createElement('span');
        statusEl.id = 'briefing-status';
        generateBtn = document.createElement('button');
        generateBtn.id = 'briefing-generate-btn';
        modalBody = document.createElement('div');
        modalBody.id = 'briefing-modal-body';

        document.body.appendChild(container);
        document.body.appendChild(statusEl);
        document.body.appendChild(generateBtn);
        document.body.appendChild(modalBody);
    });

    afterEach(() => {
        server.resetHandlers();
        server.close();
        vi.useRealTimers();
        vi.restoreAllMocks();

        container.remove();
        statusEl.remove();
        generateBtn.remove();
        modalBody.remove();
    });

    it('calls generate endpoint and polls latest endpoint on success', async () => {
        const generateSpy = vi.fn();
        const latestSpy = vi.fn();

        server.use(
            http.post('/api/briefing/generate', (info) => {
                generateSpy(info.request.url);
                return HttpResponse.json({ status: 'accepted' }, { status: 202 });
            }),
            http.get('/api/briefing/latest', (info) => {
                latestSpy(info.request.url);
                return HttpResponse.json({
                    date: '2026-06-23',
                    market_indices: { '上证指数': { current: 3000, change_pct: 1.2 } },
                    top_movers: [{ stock_code: '600000', stock_name: '浦发银行', move_type: 'volume_spike', change_percent: 2.5 }],
                    insights: ['大盘向好'],
                    is_degraded: false,
                });
            })
        );

        const ctrl = createBriefingController({
            generateBtn,
            statusEl,
            container,
            modalBody,
            pollIntervalMs: 1000,
            maxPollMs: 5000,
        });

        ctrl.onGenerate();

        // 同步断言：按钮立即禁用
        expect(generateBtn.disabled).toBe(true);
        expect(statusEl.textContent).toContain('正在触发');

        // 等待 generate fetch resolve
        await vi.advanceTimersByTimeAsync(100);

        expect(generateSpy).toHaveBeenCalledTimes(1);
        expect(statusEl.textContent).toContain('已触发');

        // 等待轮询触发
        await vi.advanceTimersByTimeAsync(1500);

        expect(latestSpy).toHaveBeenCalledTimes(1);
        expect(container.innerHTML).toContain('上证指数');
        expect(container.innerHTML).toContain('大盘向好');
        expect(generateBtn.disabled).toBe(true);
        expect(statusEl.textContent).toMatch(/简报已更新|冷却中/);
    });

    it('handles 429 cooldown from generate endpoint', async () => {
        server.use(
            http.post('/api/briefing/generate', () => {
                return HttpResponse.json({ detail: '冷却中' }, { status: 429 });
            })
        );

        const ctrl = createBriefingController({
            generateBtn,
            statusEl,
            container,
            modalBody,
        });

        ctrl.onGenerate();
        await vi.advanceTimersByTimeAsync(100);

        expect(generateBtn.disabled).toBe(true);
        expect(statusEl.textContent).toContain('冷却中');
    });

    it('handles 422 non-trading day from generate endpoint', async () => {
        server.use(
            http.post('/api/briefing/generate', () => {
                return HttpResponse.json({ detail: '非交易日' }, { status: 422 });
            })
        );

        const ctrl = createBriefingController({
            generateBtn,
            statusEl,
            container,
            modalBody,
        });

        ctrl.onGenerate();
        await vi.advanceTimersByTimeAsync(100);

        expect(generateBtn.disabled).toBe(false);
        expect(statusEl.textContent).toContain('非交易日');
    });
});
