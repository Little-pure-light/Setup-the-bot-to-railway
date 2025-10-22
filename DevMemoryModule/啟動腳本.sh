#!/bin/bash
# 🚀 開發者記憶助手 - 一鍵啟動腳本

echo "🧠 啟動 XiaoChenGuang 開發者記憶助手..."
echo ""

# 檢查環境變數
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

# 啟動 Streamlit
echo "🚀 啟動 Streamlit 介面..."
echo "📍 訪問地址：http://0.0.0.0:5000"
echo ""

streamlit run DevMemoryModule/DevMemory_Streamlit_UI.py \
    --server.port 5000 \
    --server.address 0.0.0.0 \
    --server.headless true
