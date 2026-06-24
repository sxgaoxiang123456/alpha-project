# API Contract: F8 自然语言设预警

**Feature**: specs/010-natural-language-alert  
**Date**: 2026-06-17

---

## 1. 自然语言创建预警

### Endpoint

```
POST /api/alerts/natural-language
```

### Request

**Headers**:

| Header | Value | Required |
|---|---|---|
| `Content-Type` | `application/json` | Yes |

**Body**:

```json
{
  "query": "茅台跌破 1500 提醒我",
  "selected_stock_code": null
}
```

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `query` | str | 是 | - | 用户输入的自然语言，最大 200 字符 |
| `selected_stock_code` | str | 否 | null | 歧义候选确认后前端携带的指定股票代码 |

### Response

**Success (200 OK)**

```json
{
  "success": true,
  "message": "预警已创建：贵州茅台 价格 < 1500",
  "rule": {
    "stock_code": "600519",
    "stock_name": "贵州茅台",
    "condition_type": "price_below",
    "threshold": 1500
  },
  "candidates": null
}
```

**Ambiguous Stock Name (200 OK with success=false)**

```json
{
  "success": false,
  "message": "请从候选列表中选择具体股票",
  "rule": null,
  "candidates": [
    {
      "stock_code": "600036",
      "stock_name": "招商银行",
      "sector": "银行",
      "market_cap": 8500.5,
      "match_score": 0.92
    },
    {
      "stock_code": "601166",
      "stock_name": "兴业银行",
      "sector": "银行",
      "market_cap": 3200.0,
      "match_score": 0.85
    }
  ]
}
```

**Low Confidence / Parse Failure (200 OK with success=false)**

```json
{
  "success": false,
  "message": "未能理解，请用『股票名+条件』格式重试，或前往预警页面手动配置",
  "rule": null,
  "candidates": null
}
```

**Unsupported Condition (200 OK with success=false)**

```json
{
  "success": false,
  "message": "暂不支持成交量条件，请使用价格或涨跌幅条件",
  "rule": null,
  "candidates": null
}
```

**Invalid Input (422 Unprocessable Entity)**

```json
{
  "detail": [
    {
      "loc": ["body", "query"],
      "msg": "输入不能超过 200 个字符",
      "type": "value_error"
    }
  ]
}
```

**Rule Limit Reached (200 OK with success=false)**

```json
{
  "success": false,
  "message": "预警规则已达上限，请先删除其他规则",
  "rule": null,
  "candidates": null
}
```

**Duplicate Rule (200 OK with success=false)**

```json
{
  "success": false,
  "message": "该预警规则已存在，请勿重复创建",
  "rule": null,
  "candidates": null
}
```

---

## 2. 候选确认后重新提交

### Endpoint

```
POST /api/alerts/natural-language
```

### Request

```json
{
  "query": "银行跌破 10 元提醒我",
  "selected_stock_code": "600036"
}
```

### Response

与首次提交成功响应相同：

```json
{
  "success": true,
  "message": "预警已创建：招商银行 价格 < 10",
  "rule": {
    "stock_code": "600036",
    "stock_name": "招商银行",
    "condition_type": "price_below",
    "threshold": 10
  },
  "candidates": null
}
```

---

## 3. 前端组件契约

### 输入框组件

组件文件：`frontend/src/templates/components/nl_alert_input.html`

**Props / 配置**：

| 属性 | 类型 | 说明 |
|---|---|---|
| `placeholder` | str | 占位文案，默认「例如：茅台跌破 1500 提醒我」 |
| `submit_url` | str | 提交 endpoint，默认 `/api/alerts/natural-language` |

**行为**：

1. 用户输入 query 后按 Enter 或点击确认按钮
2. 前端调用 `POST /api/alerts/natural-language`
3. 根据响应状态处理：
   - `success=true`：显示成功提示 `message`
   - `success=false` 且 `candidates` 非空：渲染候选列表，用户点击后自动携带 `selected_stock_code` 重提交
   - `success=false` 且 `candidates` 为空：显示错误提示 `message`

### 候选弹窗

当 `candidates` 返回时，以下拉/弹窗形式展示：

| 展示字段 | 说明 |
|---|---|
| `stock_name` | 股票名称 |
| `stock_code` | 股票代码 |
| `sector` | 所属行业 |

点击候选项后，前端自动将 `selected_stock_code` 填入请求体并重新提交，无需用户再次输入。

---

## 4. 错误码与提示映射

| 场景 | HTTP Status | `success` | `message` |
|---|---|---|---|
| 成功创建 | 200 | true | 预警已创建：{stock_name} {condition_display} {threshold} |
| 股票名称歧义 | 200 | false | 请从候选列表中选择具体股票 |
| 解析置信度低 | 200 | false | 未能理解，请用『股票名+条件』格式重试，或前往预警页面手动配置 |
| 不支持条件 | 200 | false | 暂不支持{condition}条件，请使用价格或涨跌幅条件 |
| 空输入 | 422 | - | 请输入预警条件 |
| 超长输入 | 422 | - | 输入过长，请用一句话描述 |
| 多股票 | 200 | false | 一次仅支持一只股票 |
| 组合条件 | 200 | false | 暂不支持组合条件 |
| 股票代码不存在 | 200 | false | 股票代码不存在，请检查输入 |
| 阈值非数字 | 200 | false | 未能识别阈值，请用数字表示价格或涨跌幅 |
| 规则数量上限 | 200 | false | 预警规则已达上限，请先删除其他规则 |
| 重复规则 | 200 | false | 该预警规则已存在，请勿重复创建 |
| 股票无法匹配 | 200 | false | 未能找到匹配股票，请检查股票名称或代码 |

---

## 5. 条件类型与文案映射

| condition_type | 用户文案示例 | 系统提示文案 |
|---|---|---|
| `price_above` | 涨到 / 突破 / 高于 | {name} 价格 > {threshold} |
| `price_below` | 跌破 / 跌到 / 低于 | {name} 价格 < {threshold} |
| `change_pct_above` | 涨幅超过 / 涨超 | {name} 涨跌幅 > {threshold}% |
| `change_pct_below` | 跌幅超过 / 跌超 | {name} 涨跌幅 < {threshold}% |

注意：`change_pct_below` 的阈值按带符号百分比点数存储（如「跌幅超过 3%」→ threshold=-3.0）。
