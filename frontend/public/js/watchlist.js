// 批量选择
const selectAllCheckbox = document.getElementById('select-all');
if (selectAllCheckbox) {
    selectAllCheckbox.addEventListener('change', function() {
        document.querySelectorAll('.row-checkbox').forEach(cb => {
            cb.checked = selectAllCheckbox.checked;
            cb.style.opacity = selectAllCheckbox.checked ? '1' : '';
        });
    });
}

// 行复选框
function handleRowCheckbox(checkbox) {
    checkbox.style.opacity = checkbox.checked ? '1' : '';
}

// 添加股票
function showAddModal() {
    const code = prompt('请输入股票代码（6位数字）：');
    if (!code) return;
    if (!/^\d{6}$/.test(code)) {
        alert('股票代码必须是6位数字');
        return;
    }
    fetch('/watchlist', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({stock_code: code})
    })
    .then(r => {
        if (r.ok) {
            window.location.reload();
        } else {
            r.json().then(d => alert(d.detail || '添加失败'));
        }
    });
}

// 编辑股票
function editStock(code) {
    const cost = prompt('请输入成本价：');
    const shares = prompt('请输入持股数：');
    const payload = {};
    if (cost !== null && cost !== '') payload.cost_price = cost;
    if (shares !== null && shares !== '') payload.shares = parseInt(shares);
    if (Object.keys(payload).length === 0) return;

    fetch(`/watchlist/${code}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
    })
    .then(r => {
        if (r.ok) {
            window.location.reload();
        } else {
            r.json().then(d => alert(d.detail || '编辑失败'));
        }
    });
}

// 删除股票
function deleteStock(code) {
    if (!confirm(`确定删除 ${code} 吗？`)) return;
    fetch(`/watchlist/${code}`, {method: 'DELETE'})
    .then(r => {
        if (r.ok || r.status === 204) {
            window.location.reload();
        } else {
            r.json().then(d => alert(d.detail || '删除失败'));
        }
    });
}

// CSV 导入
function handleCsvImport(input) {
    const file = input.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    fetch('/watchlist/import', {
        method: 'POST',
        body: formData
    })
    .then(r => r.json())
    .then(data => {
        let msg = `导入完成：成功 ${data.success_count} 条`;
        if (data.failure_count > 0) {
            msg += `，失败 ${data.failure_count} 条\n`;
            msg += data.failures.map(f => `第${f.line}行 ${f.code}: ${f.reason}`).join('\n');
        }
        alert(msg);
        window.location.reload();
    })
    .catch(e => alert('导入失败: ' + e.message));
    input.value = '';
}

// 新建分组
function showCreateGroupModal() {
    const name = prompt('请输入分组名称：');
    if (!name) return;
    fetch('/groups', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({name})
    })
    .then(r => {
        if (r.ok) {
            window.location.reload();
        } else {
            r.json().then(d => alert(d.detail || '创建失败'));
        }
    });
}
