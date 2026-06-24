import { describe, expect, it } from 'vitest';
import { renderCardContent, renderModalContent } from '../../public/js/briefing.js';

const sampleBriefing = {
    date: '2026-06-23',
    market_indices: {
        '上证指数': { current: 3123.45, change_pct: 0.85 },
        '深证成指': { current: 9876.54, change_pct: -0.35 },
        '创业板指': { current: 2012.34, change_pct: 0 },
    },
    top_movers: [
        { stock_code: '600519', stock_name: '贵州茅台', move_type: 'price_surge', change_percent: 1.25 },
        { stock_code: '000001', stock_name: '平安银行', move_type: 'price_drop', change_percent: -2.1 },
        { stock_code: '000002', stock_name: '万科A', move_type: 'normal', change_percent: 0 },
    ],
    insights: ['白酒板块领涨', '科技成长股分化'],
    is_degraded: false,
};

const degradedBriefing = {
    ...sampleBriefing,
    is_degraded: true,
    degraded_reason: 'LLM 服务超时',
};

describe('renderCardContent', () => {
    it('renders market indices with A-share red-up green-down semantics', () => {
        const html = renderCardContent(sampleBriefing);

        expect(html).toContain('上证指数');
        expect(html).toContain('3123.45');
        expect(html).toContain('+0.85%');

        // 涨用 text-market-up，跌用 text-market-down，平盘用 text-on-surface-variant
        expect(html).toMatch(/text-market-up[\s\"']/);
        expect(html).toMatch(/text-market-down[\s\"']/);
        expect(html).toMatch(/text-on-surface-variant[\s\"']/);
    });

    it('renders top 5 movers with correct color class', () => {
        const html = renderCardContent(sampleBriefing);

        expect(html).toContain('贵州茅台');
        expect(html).toContain('+1.25%');
        expect(html).toContain('-2.10%');
        expect(html).toContain('异动 TOP5');
    });

    it('renders degraded banner when is_degraded is true', () => {
        const html = renderCardContent(degradedBriefing);

        expect(html).toContain('LLM 服务超时');
        expect(html).toContain('bg-error/10');
    });

    it('does not render degraded banner for normal briefing', () => {
        const html = renderCardContent(sampleBriefing);

        expect(html).not.toContain('bg-error/10');
    });
});

describe('renderModalContent', () => {
    it('renders modal body with indices and movers tables', () => {
        const html = renderModalContent(sampleBriefing);

        expect(html).toContain('大盘指数');
        expect(html).toContain('异动 TOP5');
        expect(html).toContain('AI 解读');
        expect(html).toContain('白酒板块领涨');
    });

    it('uses A-share color semantics in modal rows', () => {
        const html = renderModalContent(sampleBriefing);

        expect(html).toMatch(/text-market-up[\s\"']/);
        expect(html).toMatch(/text-market-down[\s\"']/);
    });
});
