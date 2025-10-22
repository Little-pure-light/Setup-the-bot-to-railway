"""
🧠 中文摘要生成器
功能：從對話記錄中提取簡短摘要
方法：取前 2-3 行非空內容組成摘要
"""

def generate_summary(text: str, max_length: int = 120) -> str:
    """
    生成中文摘要
    
    參數:
        text: 要生成摘要的文字內容
        max_length: 摘要最大字數（預設 120 字）
    
    回傳:
        生成的摘要文字
    """
    if not text or not text.strip():
        return "（空白內容）"
    
    # 將文字按行分割，過濾掉空行
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    if not lines:
        return "（無有效內容）"
    
    # 取前 2-3 行作為摘要
    summary_lines = lines[:3]
    summary = ' '.join(summary_lines)
    
    # 如果超過字數限制，截斷並加上省略號
    if len(summary) > max_length:
        summary = summary[:max_length] + "..."
    
    return summary


if __name__ == "__main__":
    # 簡單測試
    test_text = """這是一段測試對話。
AI: 你好呀！今天過得如何？
Human: 還不錯，謝謝你的關心。
AI: 很高興聽到這個消息！"""
    
    result = generate_summary(test_text)
    print(f"摘要結果：{result}")
