import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { initNLAlertInput } from '../../public/js/nl_alert_input.js';

const COMPONENT_HTML = `
  <div class="nl-alert-input-component" data-submit-url="/api/alerts/natural-language">
    <div class="flex gap-3">
      <input type="text" class="nl-alert-input" placeholder="例如：茅台跌破 1500 提醒我" maxlength="200" autocomplete="off">
      <button class="nl-alert-submit" type="button">创建预警</button>
    </div>
    <div class="nl-alert-result hidden"></div>
    <div class="nl-alert-candidates hidden"></div>
  </div>
`;

const server = setupServer();

function getElements(container) {
    const component = container.querySelector('.nl-alert-input-component');
    return {
        component,
        input: component.querySelector('.nl-alert-input'),
        submitBtn: component.querySelector('.nl-alert-submit'),
        resultEl: component.querySelector('.nl-alert-result'),
        candidatesEl: component.querySelector('.nl-alert-candidates'),
    };
}

describe('nl_alert_input L0/L1 + L6 contract mock', () => {
    let container;

    beforeEach(() => {
        server.listen({ onUnhandledRequest: 'error' });
        container = document.createElement('div');
        container.innerHTML = COMPONENT_HTML;
        document.body.appendChild(container);
        initNLAlertInput(container.firstElementChild);
    });

    afterEach(() => {
        server.resetHandlers();
        server.close();
        container.remove();
        vi.restoreAllMocks();
    });

    it('renders input and submit button', () => {
        const { input, submitBtn } = getElements(container);
        expect(input).toBeTruthy();
        expect(submitBtn).toBeTruthy();
        expect(submitBtn.textContent).toContain('创建预警');
    });

    it('shows error when submitting empty query', () => {
        const { submitBtn, resultEl } = getElements(container);
        submitBtn.click();
        expect(resultEl.textContent).toContain('请输入预警条件');
        expect(resultEl.classList.contains('hidden')).toBe(false);
    });

    it('submits query and shows success message', async () => {
        let capturedBody = null;
        server.use(
            http.post('/api/alerts/natural-language', async ({ request }) => {
                capturedBody = await request.json();
                return HttpResponse.json({
                    success: true,
                    message: '预警已创建：贵州茅台 价格 < 1500',
                    rule: { stock_code: '600519', condition_type: 'price_below', threshold: 1500 },
                });
            })
        );

        const { input, submitBtn, resultEl } = getElements(container);
        input.value = '茅台跌破 1500 提醒我';
        submitBtn.click();

        await new Promise(r => setTimeout(r, 100));
        expect(resultEl.textContent).toContain('预警已创建');
        expect(resultEl.classList.contains('text-market-up')).toBe(true);
        expect(input.value).toBe('');
        expect(capturedBody.query).toBe('茅台跌破 1500 提醒我');
    });

    it('renders candidates and submits selected stock code', async () => {
        let selectedCode = null;
        server.use(
            http.post('/api/alerts/natural-language', async ({ request }) => {
                const body = await request.json();
                if (body.selected_stock_code) {
                    selectedCode = body.selected_stock_code;
                    return HttpResponse.json({
                        success: true,
                        message: '预警已创建：兴业银行 价格 < 10',
                        rule: { stock_code: '601166', condition_type: 'price_below', threshold: 10 },
                    });
                }
                return HttpResponse.json({
                    success: false,
                    message: '请从候选列表中选择具体股票',
                    candidates: [
                        { stock_code: '600036', stock_name: '招商银行', sector: '银行' },
                        { stock_code: '601166', stock_name: '兴业银行', sector: '银行' },
                    ],
                });
            })
        );

        const { input, submitBtn, resultEl, candidatesEl } = getElements(container);
        input.value = '银行跌破 10 元提醒我';
        submitBtn.click();

        await new Promise(r => setTimeout(r, 100));
        expect(candidatesEl.classList.contains('hidden')).toBe(false);
        const buttons = candidatesEl.querySelectorAll('button');
        expect(buttons.length).toBe(2);
        expect(candidatesEl.textContent).toContain('招商银行');
        expect(candidatesEl.textContent).toContain('兴业银行');

        buttons[1].click();
        await new Promise(r => setTimeout(r, 100));
        expect(resultEl.textContent).toContain('预警已创建');
        expect(selectedCode).toBe('601166');
    });

    it('shows backend error message', async () => {
        server.use(
            http.post('/api/alerts/natural-language', () => {
                return HttpResponse.json({
                    success: false,
                    message: '该预警规则已存在，请勿重复创建',
                });
            })
        );

        const { input, submitBtn, resultEl } = getElements(container);
        input.value = '茅台跌破 1500 提醒我';
        submitBtn.click();

        await new Promise(r => setTimeout(r, 100));
        expect(resultEl.textContent).toContain('已存在');
        expect(resultEl.classList.contains('text-error')).toBe(true);
    });

    it('shows network error when fetch fails', async () => {
        server.use(
            http.post('/api/alerts/natural-language', () => {
                return HttpResponse.error();
            })
        );

        const { input, submitBtn, resultEl } = getElements(container);
        input.value = '茅台跌破 1500 提醒我';
        submitBtn.click();

        await new Promise(r => setTimeout(r, 100));
        expect(resultEl.textContent).toContain('网络错误');
        expect(resultEl.classList.contains('text-error')).toBe(true);
    });

    it('submits on Enter key', async () => {
        server.use(
            http.post('/api/alerts/natural-language', () => {
                return HttpResponse.json({
                    success: true,
                    message: '预警已创建',
                    rule: { stock_code: '600519', condition_type: 'price_below', threshold: 1500 },
                });
            })
        );

        const { input, resultEl } = getElements(container);
        input.value = '茅台跌破 1500 提醒我';
        input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true }));

        await new Promise(r => setTimeout(r, 100));
        expect(resultEl.textContent).toContain('预警已创建');
    });
});

import axe from 'axe-core';

describe('nl_alert_input a11y', () => {
    let container;

    beforeEach(() => {
        container = document.createElement('div');
        container.innerHTML = COMPONENT_HTML;
        document.body.appendChild(container);
        initNLAlertInput(container.firstElementChild);
    });

    afterEach(() => {
        container.remove();
    });

    it('has no critical axe violations on initial render', async () => {
        const { input, submitBtn } = getElements(container);
        input.setAttribute('aria-label', '自然语言预警输入');
        submitBtn.setAttribute('aria-label', '创建预警');

        const results = await axe.run(container, {
            rules: { 'color-contrast': { enabled: false } },
        });
        const critical = results.violations.filter(v => v.impact === 'critical');
        expect(critical).toHaveLength(0);
    });
});
