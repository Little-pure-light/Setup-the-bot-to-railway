"""
🌌 語義記憶上傳器 mini
功能：上傳 .txt 對話記錄 → 生成摘要 → 上傳 IPFS → 記錄到 Google Sheets
"""

import streamlit as st
import os
import tempfile
import hashlib
from summarizer import generate_summary
from ipfs_tools import upload_to_ipfs
from record_store import save_record


def check_env_variables():
    """檢查必要的環境變數是否已設定"""
    required_vars = {
        "PINATA_JWT": "Pinata JWT Token",
        "SERVICE_ACCOUNT_JSON": "Google 服務帳號 JSON",
        "SPREADSHEET_ID": "Google Sheets ID"
    }
    
    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"- {var} ({description})")
    
    return missing_vars


def main():
    # 設定頁面標題和圖示
    st.set_page_config(
        page_title="🌌 語義記憶上傳器 mini",
        page_icon="🌌",
        layout="centered"
    )
    
    # 主標題
    st.title("🌌 語義記憶上傳器 mini")
    st.markdown("將你的對話記錄上傳到 IPFS，並自動記錄到 Google Sheets")
    
    # 檢查環境變數
    missing_vars = check_env_variables()
    
    if missing_vars:
        st.error("⚠️ 缺少必要的環境變數設定")
        st.markdown("請先在 Replit Secrets 中設定以下變數：")
        for var in missing_vars:
            st.markdown(var)
        st.info("💡 請參閱「使用說明書.md」了解如何設定環境變數")
        return
    
    # 檔案上傳器
    st.markdown("---")
    st.subheader("📤 上傳對話記錄")
    uploaded_file = st.file_uploader(
        "選擇一個 .txt 檔案",
        type=['txt'],
        help="請上傳包含對話記錄的 .txt 文字檔"
    )
    
    # 上傳按鈕
    if uploaded_file is not None:
        st.success(f"✅ 已選擇檔案：{uploaded_file.name}")
        
        # 讀取檔案 bytes（每次運行都需要讀取，因為 Streamlit 會重置 uploaded_file）
        try:
            file_bytes = uploaded_file.read()
            content = file_bytes.decode('utf-8')
            filename = uploaded_file.name
            
            # 計算內容 hash 作為唯一識別鍵
            content_hash = hashlib.sha256(file_bytes).hexdigest()
            
            # 儲存到 session_state（用 hash 確保內容唯一性）
            st.session_state.file_content = content
            st.session_state.file_name = filename
            st.session_state.content_hash = content_hash
            
        except Exception as e:
            st.error(f"❌ 無法讀取檔案：{str(e)}")
            st.info("💡 請確保檔案是 UTF-8 編碼的文字檔")
            return
        
        # 顯示檔案內容預覽
        with st.expander("📄 查看檔案內容預覽"):
            preview = content[:500]
            if len(content) > 500:
                preview += "\n\n... （還有更多內容）"
            st.text(preview)
        
        # 上傳按鈕
        if st.button("🚀 上傳記憶到 IPFS", type="primary", use_container_width=True):
            try:
                # 建立進度指示器
                with st.spinner("🔄 處理中，請稍候..."):
                    # 1. 使用快取的檔案內容
                    st.info("📖 正在處理檔案內容...")
                    
                    # 2. 生成摘要
                    st.info("🧠 正在生成中文摘要...")
                    summary = generate_summary(content)
                    
                    # 3. 儲存到臨時檔案並上傳到 IPFS
                    st.info("📦 正在上傳到 Pinata IPFS...")
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as tmp_file:
                        tmp_file.write(content)
                        tmp_file_path = tmp_file.name
                    
                    try:
                        upload_result = upload_to_ipfs(tmp_file_path)
                        cid = upload_result["cid"]
                        gateway_url = upload_result["gateway"]
                    finally:
                        # 清理臨時檔案
                        if os.path.exists(tmp_file_path):
                            os.unlink(tmp_file_path)
                    
                    # 4. 寫入 Google Sheets
                    st.info("💾 正在記錄到 Google Sheets...")
                    record = {
                        "filename": filename,
                        "summary": summary,
                        "cid": cid,
                        "gateway": gateway_url
                    }
                    save_record(record)
                
                # 顯示成功訊息
                st.success("🎉 上傳成功！")
                
                # 顯示結果
                st.markdown("---")
                st.subheader("✨ 上傳結果")
                
                # 摘要
                st.markdown("**📝 中文摘要：**")
                st.info(summary)
                
                # CID
                st.markdown("**📦 IPFS CID：**")
                st.code(cid, language=None)
                
                # Gateway URL（可點擊）
                st.markdown("**🌐 Gateway 連結：**")
                st.markdown(f"[點擊這裡查看檔案]({gateway_url})")
                
                # Google Sheets 提示
                st.success("💾 記錄已成功寫入 Google Sheets！")
                
            except Exception as e:
                st.error(f"❌ 錯誤：{str(e)}")
                st.info("💡 請檢查環境變數設定是否正確，或參閱使用說明書")
    
    else:
        st.info("👆 請先選擇一個 .txt 檔案")
    
    # 頁尾說明
    st.markdown("---")
    st.caption("💡 需要幫助？請參閱「使用說明書.md」")


if __name__ == "__main__":
    main()
