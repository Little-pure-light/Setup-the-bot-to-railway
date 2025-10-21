import os
import json
from flask import Flask, request, session, render_template, jsonify
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_gspread_client():
    """
    建立與 Google Sheets 的連線
    從環境變數讀取服務帳號資訊
    """
    try:
        service_account_json = os.environ.get('SERVICE_ACCOUNT_JSON')
        if not service_account_json:
            raise ValueError("環境變數中找不到 SERVICE_ACCOUNT_JSON，請先設定此變數")
        
        service_account_info = json.loads(service_account_json)
        creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        return gspread.authorize(creds)
    except json.JSONDecodeError:
        raise ValueError("SERVICE_ACCOUNT_JSON 格式錯誤，請確認是有效的 JSON 格式")
    except Exception as e:
        raise Exception(f"連線 Google Sheets 失敗：{str(e)}")

def get_spreadsheet_id():
    """
    從環境變數取得試算表 ID
    """
    spreadsheet_id = os.environ.get('SPREADSHEET_ID')
    if not spreadsheet_id:
        raise ValueError("環境變數中找不到 SPREADSHEET_ID，請先設定此變數")
    return spreadsheet_id

@app.route('/health')
def health():
    """
    健康檢查端點
    """
    return jsonify({'status': 'healthy', 'service': 'semantic-memory-system'}), 200

@app.route('/')
def index():
    """
    首頁：顯示當前使用的記錄本
    """
    current_sheet = session.get('sheet_name', None)
    return render_template('index.html', current_sheet=current_sheet)

@app.route('/start', methods=['GET'])
def start_conversation():
    """
    啟動對話模式
    參數：
      - mode: 'new' (建立新對話) 或 'resume' (延續已有對話)
      - sheet_name: 工作表名稱
    """
    try:
        mode = request.args.get('mode')
        sheet_name = request.args.get('sheet_name')

        if not mode or not sheet_name:
            return render_template('error.html', 
                                 error_message='缺少必要參數：mode 和 sheet_name'), 400

        client = get_gspread_client()
        spreadsheet_id = get_spreadsheet_id()
        spreadsheet = client.open_by_key(spreadsheet_id)

        if mode == 'new':
            try:
                existing_sheets = [ws.title for ws in spreadsheet.worksheets()]
                if sheet_name in existing_sheets:
                    return render_template('error.html', 
                                         error_message=f'工作表 "{sheet_name}" 已存在，請使用其他名稱或選擇「延續對話」'), 400

                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=3)
                headers = [['時間戳記', '使用者訊息', 'AI 回應']]
                worksheet.update(values=headers, range_name='A1:C1')
                
                session['sheet_name'] = sheet_name
                return render_template('success.html', 
                                     message=f'成功建立新對話：{sheet_name}',
                                     sheet_name=sheet_name)
            except Exception as e:
                return render_template('error.html', 
                                     error_message=f'建立工作表失敗：{str(e)}'), 500

        elif mode == 'resume':
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
                headers = worksheet.row_values(1)
                
                if not headers or len(headers) < 3:
                    header_values = [['時間戳記', '使用者訊息', 'AI 回應']]
                    worksheet.update(values=header_values, range_name='A1:C1')
                
                session['sheet_name'] = sheet_name
                return render_template('success.html', 
                                     message=f'成功載入對話：{sheet_name}',
                                     sheet_name=sheet_name)
            except gspread.exceptions.WorksheetNotFound:
                return render_template('error.html', 
                                     error_message=f'找不到工作表 "{sheet_name}"，請確認名稱是否正確'), 404
            except Exception as e:
                return render_template('error.html', 
                                     error_message=f'載入工作表失敗：{str(e)}'), 500
        else:
            return render_template('error.html', 
                                 error_message='無效的 mode 參數，請使用 "new" 或 "resume"'), 400

    except Exception as e:
        return render_template('error.html', 
                             error_message=f'系統錯誤：{str(e)}'), 500

@app.route('/log', methods=['POST'])
def log_conversation():
    """
    紀錄對話內容
    參數（JSON body）：
      - user_message: 使用者訊息
      - ai_response: AI 回應
    """
    try:
        sheet_name = session.get('sheet_name')
        if not sheet_name:
            return jsonify({
                'status': 'error',
                'message': '尚未啟動對話，請先選擇或建立對話記錄本'
            }), 400

        data = request.get_json()
        if data is None:
            return jsonify({
                'status': 'error',
                'message': '無效的 JSON 格式，請確保 Content-Type 為 application/json'
            }), 400

        user_message = data.get('user_message', '')
        ai_response = data.get('ai_response', '')

        if not user_message or not ai_response:
            return jsonify({
                'status': 'error',
                'message': '缺少必要參數：user_message 和 ai_response'
            }), 400

        client = get_gspread_client()
        spreadsheet_id = get_spreadsheet_id()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        new_row = [[timestamp, user_message, ai_response]]
        worksheet.append_rows(new_row)

        return jsonify({
            'status': 'success',
            'message': '對話已記錄',
            'sheet_name': sheet_name,
            'timestamp': timestamp
        }), 200

    except gspread.exceptions.WorksheetNotFound:
        sheet_name_err = session.get('sheet_name', '未知')
        return jsonify({
            'status': 'error',
            'message': f'找不到工作表 "{sheet_name_err}"'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'記錄失敗：{str(e)}'
        }), 500

@app.route('/get_history', methods=['GET'])
def get_history():
    """
    查詢歷史記錄
    參數：
      - sheet_name: 工作表名稱（必填）
      - limit: 返回最近幾筆記錄（選填，預設 5）
    """
    sheet_name = request.args.get('sheet_name')
    try:
        if not sheet_name:
            return jsonify({
                'status': 'error',
                'message': '缺少必要參數：sheet_name'
            }), 400

        limit_str = request.args.get('limit', '5')
        try:
            limit = int(limit_str)
            if limit <= 0:
                raise ValueError("limit 必須大於 0")
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'limit 參數必須是正整數'
            }), 400

        client = get_gspread_client()
        spreadsheet_id = get_spreadsheet_id()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        all_records = worksheet.get_all_values()
        
        if len(all_records) <= 1:
            return jsonify({
                'status': 'success',
                'sheet_name': sheet_name,
                'total_records': 0,
                'returned_records': 0,
                'history': []
            }), 200

        records = all_records[1:]
        total_records = len(records)
        recent_records = records[-limit:] if len(records) > limit else records

        history = []
        for record in recent_records:
            if len(record) >= 3:
                history.append({
                    'timestamp': record[0],
                    'user_message': record[1],
                    'ai_response': record[2]
                })

        return jsonify({
            'status': 'success',
            'sheet_name': sheet_name,
            'total_records': total_records,
            'returned_records': len(history),
            'history': history
        }), 200

    except gspread.exceptions.WorksheetNotFound:
        sheet_name_display = sheet_name if sheet_name else '未知'
        return jsonify({
            'status': 'error',
            'message': f'找不到工作表 "{sheet_name_display}"'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'查詢失敗：{str(e)}'
        }), 500

@app.route('/summarize', methods=['POST'])
def summarize():
    """
    摘要功能（預留）
    當對話超過 50 筆時，可呼叫此 API 進行摘要
    """
    sheet_name = request.args.get('sheet_name')
    try:
        if not sheet_name:
            return jsonify({
                'status': 'error',
                'message': '缺少必要參數：sheet_name'
            }), 400

        client = get_gspread_client()
        spreadsheet_id = get_spreadsheet_id()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)

        all_records = worksheet.get_all_values()
        record_count = len(all_records) - 1

        if record_count < 50:
            return jsonify({
                'status': 'info',
                'message': f'目前對話僅 {record_count} 筆，建議超過 50 筆後再進行摘要',
                'record_count': record_count
            }), 200

        return jsonify({
            'status': 'info',
            'message': '摘要功能尚未實作，此為預留端點',
            'record_count': record_count,
            'suggestion': '未來可整合 GPT/Claude API 進行對話摘要'
        }), 200

    except gspread.exceptions.WorksheetNotFound:
        sheet_name_display = sheet_name if sheet_name else '未知'
        return jsonify({
            'status': 'error',
            'message': f'找不到工作表 "{sheet_name_display}"'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'摘要失敗：{str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
