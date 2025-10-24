#!/bin/bash
# 🚀 XiaoChenGuang 開發者記憶助手 V2 - 一鍵啟動腳本

echo "========================================="
echo "🧠 XiaoChenGuang 開發者記憶助手 V2"
echo "========================================="
echo ""

# 檢查環境變數
echo "🔍 檢查環境變數..."

if [ -z "$SUPABASE_URL" ]; then
    echo "❌ 錯誤：缺少 SUPABASE_URL 環境變數"
    echo "💡 請在 Replit Secrets 中設定"
    exit 1
fi

if [ -z "$SUPABASE_ANON_KEY" ]; then
    echo "❌ 錯誤：缺少 SUPABASE_ANON_KEY 環境變數"
    echo "💡 請在 Replit Secrets 中設定"
    exit 1
fi

if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ 錯誤：缺少 OPENAI_API_KEY 環境變數"
    echo "💡 請在 Replit Secrets 中設定"
    exit 1
fi

echo "✅ 環境變數檢查通過"
echo ""

# 檢查套件安裝
echo "🔍 檢查套件安裝..."
python3 -c "import streamlit, supabase, openai, dotenv" 2>/dev/null

if [ $? -ne 0 ]; then
    echo "⚠️ 套件未完全安裝，正在安裝..."
    pip install streamlit supabase openai python-dotenv
    echo "✅ 套件安裝完成"
else
    echo "✅ 套件已安裝"
fi

echo ""

# 啟動 Streamlit
echo "========================================="
echo "🚀 啟動 Streamlit 介面..."
echo "========================================="
echo "📍 訪問地址：http://0.0.0.0:5000"
echo "💡 使用 Ctrl+C 停止服務"
echo ""

streamlit run DevMemoryModule/DevMemory_Streamlit_UI_V2.py \
    --server.port 5000 \
    --server.address 0.0.0.0 \
    --server.headless true
