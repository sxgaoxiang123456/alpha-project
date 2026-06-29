/** NL 预警输入组件逻辑 */

export function initNLAlertInput(component) {
    const input = component.querySelector('.nl-alert-input');
    const submitBtn = component.querySelector('.nl-alert-submit');
    const resultEl = component.querySelector('.nl-alert-result');
    const candidatesEl = component.querySelector('.nl-alert-candidates');
    const submitUrl = component.dataset.submitUrl || '/api/alerts/natural-language';

    function clear() {
        resultEl.classList.add('hidden');
        candidatesEl.classList.add('hidden');
        resultEl.textContent = '';
        candidatesEl.innerHTML = '';
    }

    function showMessage(message, type) {
        resultEl.textContent = message;
        resultEl.classList.remove('hidden', 'text-market-up', 'text-market-down', 'text-error');
        if (type === 'success') {
            resultEl.classList.add('text-market-up');
        } else if (type === 'error') {
            resultEl.classList.add('text-error');
        } else {
            resultEl.classList.add('text-on-surface-variant');
        }
    }

    function showCandidates(candidates, originalQuery) {
        candidatesEl.innerHTML = '';
        candidatesEl.classList.remove('hidden');
        const hint = document.createElement('div');
        hint.className = 'text-on-surface-variant font-body-md text-body-md mb-1';
        hint.textContent = '请选择具体股票：';
        candidatesEl.appendChild(hint);

        candidates.forEach(function (candidate) {
            const btn = document.createElement('button');
            btn.className = 'w-full text-left flex items-center justify-between bg-surface-raised hover:bg-surface-container-high border border-outline-variant rounded px-4 py-2 transition-colors';
            btn.type = 'button';
            const sector = candidate.sector || '未知行业';
            btn.innerHTML = '<span class="font-body-md text-body-md text-on-surface">' + candidate.stock_name + ' <span class="text-on-surface-variant font-data-table text-data-table">' + candidate.stock_code + '</span></span><span class="font-label-caps text-label-caps text-on-surface-variant">' + sector + '</span>';
            btn.addEventListener('click', function () {
                submit(originalQuery, candidate.stock_code);
            });
            candidatesEl.appendChild(btn);
        });
    }

    async function submit(query, selectedStockCode) {
        if (!query.trim()) {
            showMessage('请输入预警条件', 'error');
            return;
        }
        clear();
        submitBtn.disabled = true;
        try {
            const payload = { query: query.trim() };
            if (selectedStockCode) {
                payload.selected_stock_code = selectedStockCode;
            }
            const res = await fetch(submitUrl, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await res.json();
            if (data.success) {
                showMessage(data.message, 'success');
                input.value = '';
            } else if (data.candidates && data.candidates.length) {
                showCandidates(data.candidates, query.trim());
            } else {
                showMessage(data.message, 'error');
            }
        } catch (err) {
            showMessage('网络错误，请稍后重试', 'error');
        } finally {
            submitBtn.disabled = false;
        }
    }

    submitBtn.addEventListener('click', function () {
        submit(input.value, null);
    });

    input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
            submit(input.value, null);
        }
    });
}
