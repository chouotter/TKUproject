import os
from io import BytesIO
import boto3
import requests
from openai import OpenAI
from telegram import Update
from flask import Flask, request
from thingspeak import Thingspeak
import telegram
# local test
# from dotenv import load_dotenv

# # 讀取 .env 檔案
# load_dotenv()

# 使用者權限清單
AUTH_USER_LIST = os.environ.get('AUTH_USER_LIST', '')
# Telegram Token
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
# OPEN AI Key
OPEN_AI_KEY = os.environ.get('OPEN_AI_KEY', '')
# AWS ACCESS KEY
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
# Server Domain
SERVICE_DOMAIN = os.environ.get('SERVICE_DOMAIN', '')
# 建立 bot 應用
app = Flask(__name__)
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# 重新設定 Telegram Bot 以使用 Webhook
bot_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
webhook_url = f"https://{SERVICE_DOMAIN}/webhook"  # 這是你伺服器的 Webhook URL（替換為你的 URL）

# 設置 Webhook
requests.post(bot_url, data={'url': webhook_url})

ts = Thingspeak()

# AWS Rekognition setup
rekognition_client = boto3.client(
    'rekognition',
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name='ap-northeast-1'
)


def handle_message(update: Update) -> None:
    print("===Request Start===")
    print("update msg: ", update)
    chat_id = update.message.chat.id
    user_message = update.message.text

    user_id = str(update.message.from_user.id)  # 唯一的uid
    auth_user_list = AUTH_USER_LIST.split(',')  # list
    print(f"AUTH_USER_LIST:[{auth_user_list}]")
    print(f"user_id:[{user_id}]")
    if user_id in auth_user_list:
        if update.message.photo:
            # 取得照片檔案 ID
            chat_id = update.message.chat_id
            file_id = update.message.photo[-1].file_id
            print(f"file_id:[{file_id}]")
            # **改用 HTTP API 獲取檔案 URL（避免使用 get_file 的 await）**
            file_info_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getFile?file_id={file_id}"
            response = requests.get(file_info_url)
            file_info = response.json()

            if not file_info.get("ok"):
                response_text = "獲取圖片 URL 失敗，請稍後再試。"
                send_message(chat_id, response_text)
                return "Error", 400

            file_path = file_info["result"]["file_path"]
            file_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
            # 下載圖片
            image_bytes = BytesIO()
            image_response = requests.get(file_url)
            if image_response.status_code == 200:
                image_bytes.write(image_response.content)
                image_bytes.seek(0)
            else:
                response_text = "下載圖片失敗，請稍後再試。"
                send_message(chat_id, response_text)
                return "Error", 400
            # AWS Rekognition 進行影像辨識
            rekognition_response = rekognition_client.detect_labels(
                Image={'Bytes': image_bytes.getvalue()},
                MaxLabels=10
            )

            # 篩選信心度高於 98% 的標籤
            labels = [label['Name'] for label in rekognition_response['Labels'] if label['Confidence'] >= 98]
            response_text = '圖片中的物體包括：' + ', '.join(labels) if labels else '未辨識出物體'
            print(f"response_text:[{response_text}]")
            # 回覆使用者
            send_message(chat_id, response_text)
        else:
            # Handle text messages
            if user_message.startswith("圖表:") or user_message.startswith("圖表："):
                try:
                    message = user_message[3:]
                    channel_id = message.split(',')[0]
                    print(f"thingspeak_channel_id:[{channel_id}]")
                    key = message.split(',')[1]
                    print(f"thingspeak_channel_key:[{key}]")
                    tw_time_list, bpm_list = ts.get_data_from_thingspeak(channel_id, key)
                    chart_name = ts.gen_chart(tw_time_list, bpm_list, user_id)
                    print(f"thingspeak_chart_name:[{chart_name}]")
                    # with open(chart_name, "rb") as image_file:
                    #     update.message.reply_photo(photo=InputFile(image_file))
                    send_photo(chat_id, chart_name)
                    print("回覆使用者ThingSpeak圖表")
                    os.remove(chart_name)
                except Exception as e:
                    print(str(e))
                    response_text = "格式錯誤或是輸入錯誤"
                    send_message(chat_id, response_text)
            elif user_message.lower().startswith("ai:") or user_message.lower().startswith("ai："):
                user_msg = user_message[3:]  # Extract string after the colon
                try:
                    client = OpenAI(api_key=OPEN_AI_KEY)
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "如果回答問題盡可能用簡潔的話回復"
                            },
                            {
                                "role": "user",
                                "content": user_msg,
                            },
                        ],
                    )
                    response_text = response.choices[0].message.content
                    print(f"response_text:[{response_text}]")
                    print("回覆使用者Chat GPT回應")
                except Exception as e:
                    print(e)
                    response_text = ""
                send_message(chat_id, response_text)
            elif user_message.startswith("建議:") or user_message.startswith("建議："):
                try:
                    message = user_message[3:]
                    channel_id = message.split(',')[0]
                    key = message.split(',')[1]
                    print(f"thingspeak_channel_id:[{channel_id}]")
                    print(f"thingspeak_channel_key:[{key}]")

                    # 取得資料
                    tw_time_list, bpm_list = ts.get_data_from_thingspeak(channel_id, key)

                    # 整理最近 N 筆資料
                    N = 10
                    recent_data = list(zip(tw_time_list[-N:], bpm_list[-N:]))
                    data_str = "\n".join([f"{t} - {bpm} bpm" for t, bpm in recent_data])
                    print(f"近{N}筆心跳紀錄:[{data_str}]")
                    prompt = f"""以下是使用者最近的心跳紀錄，請根據這些資料，提供一段健康建議與觀察：

            {data_str}

            請注意，如果有異常請提醒，但請以友善與簡潔的語氣回覆。
            """

                    client = OpenAI(api_key=OPEN_AI_KEY)
                    response = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {
                                "role": "system",
                                "content": "你是一位專業健康顧問，擅長解釋健康紀錄並提供簡單實用的建議。"
                            },
                            {
                                "role": "user",
                                "content": prompt,
                            },
                        ],
                    )
                    response_text = response.choices[0].message.content
                    print(f"建議回覆內容:[{response_text}]")
                except Exception as e:
                    print(e)
                    response_text = "無法讀取資料或格式錯誤，請確認輸入格式為：建議:channel_id,read_key"
                
                send_message(chat_id, response_text)
            else:
                response_text = user_message  # Echo bot
                send_message(chat_id, response_text)
    else:
        response_text = "使用者沒有權限"
        send_message(chat_id, response_text)
    print("===Request End===")
    return


def send_message(chat_id, text):
    url = f'{bot_url}/sendMessage'
    payload = {'chat_id': chat_id, 'text': text}
    requests.post(url, json=payload)


def send_photo(chat_id, chart_name):
    url = f'{bot_url}/sendPhoto'
    with open(chart_name, "rb") as photo:
        files = {"photo": photo}
        data = {"chat_id": chat_id, "caption": "Here is your photo!"}
        requests.post(url, data=data, files=files)


# Webhook 路由
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    update = Update.de_json(data, bot)
    handle_message(update)  # 處理訊息
    return 'OK', 200


# 啟動 Flask 伺服器（Web）來接收 Webhook
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
