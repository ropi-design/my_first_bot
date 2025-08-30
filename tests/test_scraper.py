import unittest
from unittest.mock import patch, Mock
import requests
from bs4 import BeautifulSoup


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


class TestScrapeWalkerplus(unittest.TestCase):
    """scrape_walkerplus関数のテストクラス"""

    def setUp(self):
        """テスト前の準備"""
        self.latitude = 35.6762  # 東京の緯度
        self.longitude = 139.6503  # 東京の経度
        self.date_str = "2024-01-15"

    @patch("tests.test_scraper.requests.get")
    def test_scrape_walkerplus_with_events(self, mock_get):
        """イベント情報が2件含まれるHTMLを渡した際のテスト"""
        # モックの設定
        mock_response = Mock()
        mock_response.content = self._get_sample_html_with_events()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # 関数を実行
        result = scrape_walkerplus(self.latitude, self.longitude, self.date_str)

        # 結果の検証
        self.assertEqual(len(result), 2)

        # 1件目のイベント情報を検証
        first_event = result[0]
        self.assertEqual(first_event["title"], "春の桜まつり")
        self.assertEqual(first_event["image_url"], "https://www.walkerplus.com/images/event1.jpg")
        self.assertEqual(first_event["link_url"], "https://www.walkerplus.com/event/spring-sakura")

        # 2件目のイベント情報を検証
        second_event = result[1]
        self.assertEqual(second_event["title"], "アート展覧会")
        self.assertEqual(second_event["image_url"], "https://www.walkerplus.com/images/event2.jpg")
        self.assertEqual(second_event["link_url"], "https://www.walkerplus.com/event/art-exhibition")

        # requests.getが正しく呼ばれたことを確認
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[0][0], "https://www.walkerplus.com/event/")

        # パラメータの確認
        expected_params = {"date": "20240115", "lat": 35.6762, "lng": 139.6503, "radius": 10, "sort": "date"}
        self.assertEqual(call_args[1]["params"], expected_params)

    @patch("tests.test_scraper.requests.get")
    def test_scrape_walkerplus_without_events(self, mock_get):
        """イベント情報が含まれないHTMLを渡した際のテスト"""
        # モックの設定
        mock_response = Mock()
        mock_response.content = self._get_sample_html_without_events()
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # 関数を実行
        result = scrape_walkerplus(self.latitude, self.longitude, self.date_str)

        # 結果の検証
        self.assertEqual(len(result), 0)
        self.assertEqual(result, [])

        # requests.getが正しく呼ばれたことを確認
        mock_get.assert_called_once()

    def _get_sample_html_with_events(self):
        """イベント情報が2件含まれるサンプルHTML"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>ウォーカープラス イベント</title></head>
        <body>
            <div class="event-list">
                <div class="event-item">
                    <h3>春の桜まつり</h3>
                    <img src="/images/event1.jpg" alt="桜まつり">
                    <a href="/event/spring-sakura">詳細を見る</a>
                </div>
                <div class="event-item">
                    <h3>アート展覧会</h3>
                    <img src="/images/event2.jpg" alt="アート展覧会">
                    <a href="/event/art-exhibition">詳細を見る</a>
                </div>
            </div>
        </body>
        </html>
        """.encode(
            "utf-8"
        )

    def _get_sample_html_without_events(self):
        """イベント情報が含まれないサンプルHTML"""
        return """
        <!DOCTYPE html>
        <html>
        <head><title>ウォーカープラス イベント</title></head>
        <body>
            <div class="event-list">
                <p>該当するイベントが見つかりませんでした。</p>
            </div>
        </body>
        </html>
        """.encode(
            "utf-8"
        )


if __name__ == "__main__":
    unittest.main()
