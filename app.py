import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_gspread_client():
    """
    初始化並返回 gspread client
    使用 Replit 的 SERVICE_ACCOUNT_JSON 環境變數進行認證
    """
    try:
        service_account_info = json.loads(os.environ.get('SERVICE_ACCOUNT_JSON', '{}'))
        if not service_account_info:
            raise ValueError("SERVICE_ACCOUNT_JSON 未設定")
        
        creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        print(f"認證錯誤: {str(e)}")
        raise

def get_spreadsheet_id():
    """
    取得 Google Spreadsheet ID
    從環境變數中讀取
    """
    spreadsheet_id = os.environ.get('SPREADSHEET_ID')
    if not spreadsheet_id:
        raise ValueError("請在環境變數中設定 SPREADSHEET_ID")
    return spreadsheet_id

@app.route('/health')
def health():
    """
    健康檢查端點（用於部署健康檢查）
    """
    return jsonify({'status': 'healthy', 'service': 'semantic-memory-system'}), 200

@app.route('/')
def index():
    """
    首頁：顯示當前使用的記錄本，提供建立新對話或延續已有對話的選項
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
                worksheet.append_row(['時間戳記', '使用者訊息', 'AI 回應'])
                
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
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        client = get_gspread_client()
        spreadsheet_id = get_spreadsheet_id()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        worksheet.append_row([timestamp, user_message, ai_response])
        
        return jsonify({
            'status': 'success',
            'message': '對話已成功記錄',
            'timestamp': timestamp
        }), 200
    
    except gspread.exceptions.WorksheetNotFound:
        current_sheet = session.get('sheet_name', 'unknown')
        return jsonify({
            'status': 'error',
            'message': f'找不到工作表 "{current_sheet}"'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'記錄失敗：{str(e)}'
        }), 500

@app.route('/get_history', methods=['GET'])
def get_history():
    """
    查詢對話歷史紀錄
    參數：
      - sheet_name: 工作表名稱
      - limit: 返回最近幾筆紀錄（預設 5）
    """
    try:
        sheet_name = request.args.get('sheet_name')
        
        try:
            limit = int(request.args.get('limit', 5))
            if limit <= 0:
                return jsonify({
                    'status': 'error',
                    'message': 'limit 參數必須為正整數'
                }), 400
        except ValueError:
            return jsonify({
                'status': 'error',
                'message': 'limit 參數必須為有效的整數'
            }), 400
        
        if not sheet_name:
            return jsonify({
                'status': 'error',
                'message': '缺少必要參數：sheet_name'
            }), 400
        
        client = get_gspread_client()
        spreadsheet_id = get_spreadsheet_id()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        all_records = worksheet.get_all_records()
        
        recent_records = all_records[-limit:] if len(all_records) > limit else all_records
        
        history = []
        for record in recent_records:
            history.append({
                'timestamp': record.get('時間戳記', ''),
                'user_message': record.get('使用者訊息', ''),
                'ai_response': record.get('AI 回應', '')
            })
        
        return jsonify({
            'status': 'success',
            'sheet_name': sheet_name,
            'total_records': len(all_records),
            'returned_records': len(history),
            'history': history
        }), 200
    
    except gspread.exceptions.WorksheetNotFound:
        requested_sheet = request.args.get('sheet_name', 'unknown')
        return jsonify({
            'status': 'error',
            'message': f'找不到工作表 "{requested_sheet}"'
        }), 404
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'查詢失敗：{str(e)}'
        }), 500

@app.route('/summarize', methods=['POST'])
def summarize():
    """
    【預留功能】摘要對話內容
    當工作表超過 50 筆對話時，可呼叫此 API 產生摘要
    未來可整合 OpenAI/Claude API 或儲存至 IPFS
    """
    try:
        sheet_name = request.args.get('sheet_name') or session.get('sheet_name')
        if not sheet_name:
            return jsonify({
                'status': 'error',
                'message': '缺少必要參數：sheet_name'
            }), 400
        
        client = get_gspread_client()
        spreadsheet_id = get_spreadsheet_id()
        spreadsheet = client.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        all_records = worksheet.get_all_records()
        
        if len(all_records) < 50:
            return jsonify({
                'status': 'info',
                'message': f'對話筆數不足 50 筆（目前 {len(all_records)} 筆），無需摘要'
            }), 200
        
        return jsonify({
            'status': 'success',
            'message': '摘要功能尚未實作，此為預留端點',
            'total_records': len(all_records),
            'note': '未來可整合 GPT/Claude API 進行摘要，並儲存至 IPFS 或其他儲存方案'
        }), 200
    
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'摘要失敗：{str(e)}'
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
