"""
💾 Google Sheets 記錄儲存工具
功能：將上傳記錄寫入 Google Sheets
需要：SERVICE_ACCOUNT_JSON 和 SPREADSHEET_ID 環境變數
"""

import os
import json
from datetime import datetime
from typing import Dict
import gspread
from google.oauth2.service_account import Credentials


def save_record(record: Dict[str, str]) -> bool:
    """
    將記錄儲存到 Google Sheets
    
    參數:
        record: 包含以下欄位的字典
            - filename: 檔案名稱
            - summary: 摘要內容
            - cid: IPFS CID
            - gateway: Gateway URL
    
    回傳:
        True 表示成功，失敗會拋出異常
    
    錯誤:
        如果環境變數缺失或 Google Sheets API 錯誤，會拋出 RuntimeError
    """
    # 從環境變數取得設定
    service_account_json = os.getenv("SERVICE_ACCOUNT_JSON")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")
    
    # 檢查必要的環境變數
    if not service_account_json:
        raise RuntimeError("❌ 錯誤：缺少 SERVICE_ACCOUNT_JSON 環境變數。請先設定 Google 服務帳號 JSON。")
    
    if not spreadsheet_id:
        raise RuntimeError("❌ 錯誤：缺少 SPREADSHEET_ID 環境變數。請先設定 Google Sheets ID。")
    
    try:
        # 解析服務帳號 JSON
        try:
            service_account_info = json.loads(service_account_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"❌ 錯誤：SERVICE_ACCOUNT_JSON 格式不正確：{str(e)}")
        
        # 設定 Google Sheets API 權限範圍
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # 建立憑證
        credentials = Credentials.from_service_account_info(
            service_account_info,
            scopes=scopes
        )
        
        # 連接 Google Sheets
        client = gspread.authorize(credentials)
        
        print(f"📊 正在連接 Google Sheets...")
        
        # 開啟試算表
        try:
            spreadsheet = client.open_by_key(spreadsheet_id)
        except gspread.exceptions.SpreadsheetNotFound:
            raise RuntimeError(f"❌ 錯誤：找不到 Google Sheets（ID: {spreadsheet_id}）。請檢查：\n"
                             "1. Spreadsheet ID 是否正確\n"
                             "2. 是否已將試算表共用給服務帳號的 email")
        
        # 取得第一個工作表（或建立新的）
        try:
            worksheet = spreadsheet.sheet1
        except Exception:
            worksheet = spreadsheet.add_worksheet(title="記憶上傳記錄", rows=1000, cols=5)
        
        # 檢查是否有標題列
        try:
            first_row = worksheet.row_values(1)
            if not first_row or first_row[0] != "時間戳記":
                # 建立標題列
                headers = ["時間戳記", "檔案名稱", "摘要", "CID", "Gateway URL"]
                worksheet.insert_row(headers, 1)
        except Exception:
            # 如果工作表是空的，建立標題列
            headers = ["時間戳記", "檔案名稱", "摘要", "CID", "Gateway URL"]
            worksheet.insert_row(headers, 1)
        
        # 準備要寫入的資料
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row_data = [
            timestamp,
            record.get("filename", ""),
            record.get("summary", ""),
            record.get("cid", ""),
            record.get("gateway", "")
        ]
        
        # 寫入新的一列（在第二列插入，標題列之後）
        worksheet.insert_row(row_data, 2)
        
        print(f"✅ 成功寫入 Google Sheets！")
        
        return True
    
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise
        raise RuntimeError(f"❌ Google Sheets 錯誤：{str(e)}")


if __name__ == "__main__":
    # 簡單測試（需要先設定環境變數）
    print("💾 Google Sheets 記錄儲存工具測試")
    print("提示：請先在 Secrets 中設定 SERVICE_ACCOUNT_JSON 和 SPREADSHEET_ID")
