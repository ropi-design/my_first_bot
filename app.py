import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent,
    TextMessage,
    TextSendMessage,
    LocationMessage,
    PostbackEvent,
    TemplateSendMessage,
    ButtonsTemplate,
    CarouselTemplate,
    CarouselColumn,
    MessageAction,
    URIAction,
)
from dotenv import load_dotenv

load_dotenv(override=True)


app = Flask(__name__)

line_bot_api = LineBotApi(os.environ["ACCESS_TOKEN"])
handler = WebhookHandler(os.environ["CHANNEL_SECRET"])

# ユーザーセッション管理用の辞書
# キー: ユーザーID, 値: 選択された日付
user_sessions = {}


def scrape_walkerplus(latitude, longitude, date_str):
    """
    ウォーカープラスからイベント情報をスクレイピングする関数

    Args:
        latitude (float): 緯度
        longitude (float): 経度
        date_str (str): 日付文字列（"YYYY-MM-DD"形式）

    Returns:
        list: イベント情報の辞書のリスト
              例: [{'title': '...', 'image_url': '...', 'link_url': '...'}, ...]

    Note:
        スクレイピング対象のサイト構造は変更される可能性があります。
        サイトの構造が変更された場合は、この関数の更新が必要です。
    """
    try:
        # ウォーカープラスの検索URLを組み立て
        # 注意: 実際のURL構造は調査が必要です
        base_url = "https://www.walkerplus.com/event/"

        # 日付を適切な形式に変換（例: 2024-01-01 → 20240101）
        date_formatted = date_str.replace("-", "")

        # 検索クエリパラメータを構築
        params = {
            "date": date_formatted,
            "lat": latitude,
            "lng": longitude,
            "radius": 10,  # 半径10km以内
            "sort": "date",  # 日付順
        }

        # ヘッダーを設定（ボットとして認識されないように）
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        # リクエストを送信
        response = requests.get(base_url, params=params, headers=headers, timeout=10)
        response.raise_for_status()

        # HTMLを解析
        soup = BeautifulSoup(response.content, "html.parser")

        # イベント情報を抽出
        events = []

        # 注意: 以下のセレクタは実際のサイト構造に合わせて調整が必要です
        # イベントのリスト要素を探す
        # （例: .event-item, .event-list li など）
        event_elements = (
            soup.find_all("div", class_="event-item")
            or soup.find_all("li", class_="event-list-item")
            or soup.find_all("article", class_="event")
        )

        for event_element in event_elements[:5]:  # 最大5件まで
            try:
                # イベント名を抽出
                title_element = (
                    event_element.find("h3") or event_element.find("h2") or event_element.find(".event-title")
                )
                title = title_element.get_text(strip=True) if title_element else "タイトル不明"

                # イベント画像のURLを抽出
                img_element = event_element.find("img")
                image_url = ""
                if img_element:
                    image_url = img_element.get("src") or img_element.get("data-src")
                    if image_url and not image_url.startswith("http"):
                        image_url = "https://www.walkerplus.com" + image_url

                # イベント詳細ページのURLを抽出
                link_element = event_element.find("a")
                link_url = ""
                if link_element:
                    link_url = link_element.get("href")
                    if link_url and not link_url.startswith("http"):
                        link_url = "https://www.walkerplus.com" + link_url

                # 有効な情報がある場合のみ追加
                if title and link_url:
                    events.append({"title": title, "image_url": image_url, "link_url": link_url})

            except Exception as e:
                # 個別のイベント処理でエラーが発生した場合はスキップ
                print(f"イベント情報抽出エラー: {e}")
                continue

        return events

    except requests.RequestException as e:
        print(f"リクエストエラー: {e}")
        return []
    except Exception as e:
        print(f"スクレイピングエラー: {e}")
        return []


@app.route("/")
def index():
    return "You call index()"


@app.route("/callback", methods=["POST"])
def callback():
    """Messaging APIからの呼び出し関数"""
    # LINEがリクエストの改ざんを防ぐために付与する署名を取得
    signature = request.headers["X-Line-Signature"]
    # リクエストの内容をテキストで取得
    body = request.get_data(as_text=True)
    # ログに出力
    app.logger.info("Request body: " + body)

    try:
        # signature と body を比較することで、リクエストがLINEから送信されたものであることを検証
        handler.handle(body, signature)
    except InvalidSignatureError:
        # クライアントからのリクエストに誤りがあったことを示すエラーを返す
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """テキストメッセージの処理"""
    text = event.message.text

    if text == "イベント検索":
        # 日付選択を促すメッセージとボタンを返信
        reply_message = TemplateSendMessage(
            alt_text="日付を選択してください",
            template=ButtonsTemplate(
                title="イベント検索",
                text="イベントの日付を選択してください",
                actions=[
                    MessageAction(label="今日", text="今日のイベント"),
                    MessageAction(label="明日", text="明日のイベント"),
                    MessageAction(label="今週末", text="今週末のイベント"),
                ],
            ),
        )
        line_bot_api.reply_message(event.reply_token, reply_message)
    elif text in ["今日のイベント", "明日のイベント", "今週末のイベント"]:
        # 日付を設定して位置情報送信を促す
        from datetime import datetime, timedelta

        today = datetime.now()
        if text == "今日のイベント":
            selected_date = today.strftime("%Y-%m-%d")
        elif text == "明日のイベント":
            selected_date = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        else:  # 今週末のイベント
            days_until_weekend = 5 - today.weekday()  # 金曜日までの日数
            if days_until_weekend <= 0:
                days_until_weekend += 7
            selected_date = (today + timedelta(days=days_until_weekend)).strftime("%Y-%m-%d")

        # ユーザーセッションに日付を保存
        user_sessions[event.source.user_id] = selected_date

        reply_message = TemplateSendMessage(
            alt_text="位置情報を送信してください",
            template=ButtonsTemplate(
                title="日付が選択されました",
                text=f"選択された日付: {selected_date}\n次に位置情報を送信してください。",
                actions=[MessageAction(label="位置情報を送信", text="位置情報を送信します")],
            ),
        )
        line_bot_api.reply_message(event.reply_token, reply_message)
    else:
        # オウム返し
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text))


@handler.add(MessageEvent, message=LocationMessage)
def handle_location_message(event):
    """位置情報メッセージの処理"""
    user_id = event.source.user_id

    # ユーザーセッションから日付を取得
    if user_id not in user_sessions:
        reply_message = TextSendMessage(
            text="日付が選択されていません。\n「イベント検索」から再度お試しください。"
        )
        line_bot_api.reply_message(event.reply_token, reply_message)
        return

    selected_date = user_sessions[user_id]
    latitude = event.message.latitude
    longitude = event.message.longitude

    # スクレイピング実行
    events = scrape_walkerplus(latitude, longitude, selected_date)

    if events:
        # イベントが見つかった場合、カルーセルメッセージを作成
        carousel_columns = []
        for event in events:
            column = CarouselColumn(
                title=event["title"][:40],  # タイトルは40文字まで
                text=f"日付: {selected_date}",
                actions=[URIAction(label="詳細を見る", uri=event["link_url"])],
            )
            carousel_columns.append(column)

        reply_message = TemplateSendMessage(
            alt_text=f"{len(events)}件のイベントが見つかりました",
            template=CarouselTemplate(columns=carousel_columns),
        )
    else:
        # イベントが見つからなかった場合
        reply_message = TextSendMessage(
            text=f"{selected_date}の{latitude}, {longitude}周辺でイベントが見つかりませんでした。\n別の日付や場所をお試しください。"
        )

    # セッションをクリア
    del user_sessions[user_id]

    line_bot_api.reply_message(event.reply_token, reply_message)


@handler.add(PostbackEvent)
def handle_postback(event):
    """ポストバックイベントの処理"""
    # 現在は使用していませんが、将来の拡張のために残しておきます
    pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
