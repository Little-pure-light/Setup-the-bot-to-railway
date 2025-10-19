# 反思模組 (Reflection Module)

## 📝 模組說明

反思模組負責 AI 的自我覺察與改進，採用「反推果因法則」進行分析。

## 🎯 主要功能

### 1. 自我反思
- 分析每次回應的品質
- 識別回應中的不足之處
- 生成改進建議

### 2. 因果分析
- 追溯回應問題的根本原因
- 提供至少 3 個可能的改進方向

### 3. 反饋循環
- 將反思結果傳遞給行為調節模組
- 形成持續改進的閉環

## 🔧 配置選項

- `reflection_prompt_template`: 反思提示詞模板
- `min_confidence_threshold`: 最低信心閾值
- `auto_reflect_enabled`: 是否自動執行反思

## 📡 使用範例

```python
data = {
    "user_message": "什麼是 AI？",
    "assistant_message": "AI 是人工智慧。",
    "emotion_analysis": {...}
}
result = await reflection_module.process(data)
```
