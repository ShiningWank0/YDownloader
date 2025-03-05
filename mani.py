import flet as ft
import os
import sys
import json
import re
import shutil
import requests
import winreg
import socket
from yt_dlp import YoutubeDL
from pathlib import Path
from datetime import datetime
from PIL import Image
import threading
import time
import uuid
import traceback
import tempfile
# TraceBackを使用することで、エラー原因の詳細が表示されるようにできる(全ての関数に実装していく予定)
# 実行ファイル化した後を想定して、エラーログなどをファイルに出力するようにする

"""
Nuitkaを使用したFletデスクトップアプリのパック
https://github.com/flet-dev/flet/discussions/1314
Fletについて
https://qiita.com/NasuPanda/items/48849d7f925784d6b6a0
Pythonのexe化について
https://zenn.dev/kitagawadisk/articles/aead46336ce3b7
Flet構築参考サイト
https://zenn.dev/gogotealove/articles/8a90a2a0519c2d
https://zenn.dev/pineconcert/articles/408aee32d1868b
https://flet-controls-gallery.fly.dev/layout
https://gallery.flet.dev/icons-browser/
https://flet.dev/docs/controls/progressbar/
yt-dlpのバージョンアップにexe化後にパッチを当てるなどして対応する方法について知りたい
"""

def get_download_folder():
    # Windowsの場合、レジストリから取得
    if sys.platform == "win32":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            )
            # DownloadsフォルダのGUID: {374DE290-123F-4565-9164-39C4925E467B}
            downloads, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            return downloads
        except Exception:
            # 万が一取得できなかった場合は、ホームディレクトリにDownloadsを結合
            return str(Path.home() / "Downloads")
    
    # macOSの場合
    elif sys.platform == "darwin":
        return str(Path.home() / "Downloads")
    
    # Linuxなどのその他のOSの場合
    else:
        xdg_config = Path.home() / ".config" / "user-dirs.dirs"
        if xdg_config.exists():
            try:
                with open(xdg_config, "r", encoding="utf-8") as f:
                    for line in f:
                        if "XDG_DOWNLOAD_DIR" in line:
                            # 例: XDG_DOWNLOAD_DIR="$HOME/Downloads"
                            parts = line.strip().split("=")
                            if len(parts) == 2:
                                path = parts[1].strip().strip('"')
                                # $HOME変数を実際のホームディレクトリパスに置換
                                return path.replace("$HOME", str(Path.home()))
            except Exception:
                pass
        # 設定がなければホームディレクトリ直下のDownloadsを返す
        return str(Path.home() / "Downloads")

class DefaultSettingsLoader:
    """
    設定ローダー
    
    設定項目:
    -retry_chance: リトライ回数(整数)
    -show_progress: プログレス表示の有無(True/False)
    -content_type: "movie"または"music"
    -movie_quality: 動画ダウンロード時のformat文字列
    -movie_format: 動画ダウンロード時のファイル形式
    -music_quality: 音楽ダウンロード時のformat文字列
    -music_format: 音楽ダウンロード時のファイル形式
    -base_dir: 保存先ディレクトリ(指定があれば、それに従うが、指定がない場合、各OSのダウンロードフォルダーになる)
    -temp_dir: 一時ファイル保存場所(ユーザー操作なしを想定)。基本的には、スクリプトファイルがあるディレクトリの下
    -page_theme: アプリ全体のテーマ("LIGHT"または"DARK")
    """
    
    def __init__(self):
        # print("DefaultSettingsLoaderの__init__開始") # デバッグ用
        
        # このスクリプトが存在するディレクトリの絶対パスを取得
        self.SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
        # config.jsonへのパスを作成
        self.CONFIG_PATH = os.path.join(self.SCRIPT_DIR, "config", "config.json")
        # 一時ファイル保存場所
        self.TEMP_DIR = os.path.join(self.SCRIPT_DIR, ".temp")
        # なければ作成
        os.makedirs(self.TEMP_DIR, exist_ok=True)
        
        self.download_folder = get_download_folder()
        # 許可される設定キー定義(コード編集なしでの変更禁止)
        self.ALLOWED_KEYS = frozenset({
            "retry_chance", 
            "show_progress",
            "content_type",
            "movie_quality",
            "movie_format",
            "music_quality",
            "music_format",
            "base_dir",
            "temp_dir",
            "page_theme"
        })
        
        # デバッグ用
        # print("ALLOWED_KEYS読み込み完了")
        
        # ファイルが存在しない時はエラー
        if not os.path.exists(self.CONFIG_PATH):
            raise FileNotFoundError(f"設定ファイル '{self.CONFIG_PATH}' が見つかりません。")
        
        # JSONファイルを読み込み
        with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
            self._config_data = json.load(f)
        
        # JSON内のキーが許可されるキーと完全一致しているかチェック
        if set(self._config_data.keys()) != self.ALLOWED_KEYS:
            raise ValueError(
                f"設定ファイル内のキーが正しくありません。"
                f"許可されるキー: {self.ALLOWED_KEYS}, 現在のキー: {set(self._config_data.keys())}"
            )
        # ALLOWED_KEYSの各キーに対して非公開インスタンス変数を自動生成
        for key in self.ALLOWED_KEYS:
            if key == "base_dir" and not self._config_data[key]:
                setattr(self, f"_{key}", self.download_folder)
            elif key == "temp_dir" and not self._config_data[key]:
                setattr(self, f"_{key}", self.TEMP_DIR)
            else:
                setattr(self, f"_{key}", self._config_data[key])
        
        # デバッグ用
        # print(self._config_data)
    
    def update_setting(self, key, value):
        """
        設定値を変更するメソッド(クラス内からのみ使用)
        変更後は、config.jsonファイルも更新する。
        """
        if key not in self.ALLOWED_KEYS:
            raise ValueError(f"設定 '{key}' は存在しません。")
        
        try:
            # メモリ上の値を更新
            setattr(self, f"_{key}", value)
            self._config_data[key] = value
            
            # config.jsonファイルを更新
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config_data, f, ensure_ascii=False, indent=2)
        except Exception as ex:
            # 更新に失敗した場合は元の値に戻す
            if hasattr(self, f"_{key}"):
                original_value = getattr(self, f"_{key}")
                setattr(self, f"_{key}", original_value)
                self._config_data[key] = original_value
            raise ValueError(f"設定の更新に失敗しました: {ex}")
    
    def __getattr__(self, key):
        """外部からのアクセス用(_を付けた非公開変数を参照)"""
        if key in self.ALLOWED_KEYS:
            return getattr(self, f"_{key}")
        raise AttributeError(f"'{type(self).__name__}' オブジェクトに属性 '{key}' は存在しません。")
    
    def __setattr__(self, key, value):
        """外部からの直接変更を禁止"""
        # ここでgetattrを使用すると再帰エラーが発生する
        if "_config_data" in self.__dict__ and key in self.ALLOWED_KEYS:
            raise AttributeError(f"'{key}' は直接変更できません。'update_setting()'を使用してください。")
        super().__setattr__(key, value) # 通常の動作

class Download:
    def __init__(self, settings):
        self.save_dir = settings.base_dir
        self.retries = settings.retry_chance
        self.show_progress = settings.show_progress
        self.content_type = settings.content_type
        os.makedirs(self.save_dir, exist_ok=True)
    
    def _sanitize_filename(self, s):
        """ファイル名として安全な文字列に変換する"""
        return re.sub(r'[\\/*?:"<>|]', "_", s)
    
    def _progress_hook(self, status):
        """
        yt-dlpの進捗状況を表示するためのフック関数
        """
        if self.show_progress:
            if status.get('status') == 'downloading':
                downloaded = status.get('downloaded_bytes', 0)
                total = status.get('total_bytes') or status.get('total_bytes_estimate') or 0
                print(f"Downloading... {downloaded} / {total} bytes", end='\r')
            elif status.get('status') == 'finished':
                print("\nDownload finished.")
    
    def _check_network(self, host="8.8.8.8", port=53, timeout=3):
        """
        指定したホストとポートへの接続が可能かどうかチェックして、端末のネットワーク接続が正常かどうか検査する
        デフォルトでは、GoogleのDNSサーバー(8.8.8.8)の53番ポートを使用。
        """
        try:
            socket.setdefaulttimeout(timeout)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
            return True
        except socket.error:
            return False
    
    def _check_content_type(self, content_type=None, url=None):
        """
        ダウンロードしたいコンテンツタイプに応じて、ダウンロード関数を適宜実施する関数
        
        :param content_type: movieかmusicを指定。指定がない時はデフォルト値に従う
        :param url: ダウンロードするコンテンツのURL。指定がない時、AttirbuteErrorを起こす
        """
        if not content_type:
            content_type = self.content_type
        if not url:
            raise AttributeError("引数urlの値が不正です。")
        if content_type == "movie":
            self.download_movie(url=url)
        elif content_type == "music":
            self.download_music(url=url)
        else:
            raise AttributeError("引数content_typeの値が不正です。")
    
    def download_overview(self, url=False, max_comments=50, process_callback=None):
        """
        動画の概要情報（説明文、上位コメント等）をJSON形式で取得し、一時ファイルとして保存する。
        取得後、process_callbackによりLLMでの情報抽出処理を行い、その完了後にファイルを削除する。
        
        :param url: ダウンロードしたいコンテンツのURL(Falseの場合はエラー)
        :param max_comments: 保存する上位コメントの最大件数(デフォルト: 50)
        :param process_callback: JSONデータを引数に取り、情報抽出処理を行うコールバック関数
        """
        if not url:
            raise Exception("Error: url is not defined")
        
        ydl_opts = {
            "skip_download": True, # 動画本体はダウンロードしない
            "getcomments": True, # コメント情報を取得(サイトやyt-dlpのバージョンに依存)
            "outtmpl": os.path.join(self.save_dir, "%(title)s.%(id)s.json"),
            "progress_hooks": [self._progress_hook] if self.show_progress else [],
        }
        
        attempt = 0
        while attempt < self.retries:
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                # コメントが取得できた場合は、上位 max_comments 件に絞る
                if "comments" in info and isinstance(info["comments"], list):
                    info["comments"] = info["comments"][:max_comments]
                
                # シンプルなファイル名を生成(例: tmp_動画タイトル_動画ID.json)
                save_title = self._sanitize_filename(info.get("title", "video"))
                video_id = info.get("id", "unknown")
                filename = f"tmp_{save_title}_{video_id}.json"
                output_filename = os.path.join(self.save_dir, filename)
                
                # JSONとして保存
                with open(output_filename, "w", encoding="utf-8") as f:
                    json.dump(info, f, ensure_ascii=False, indent=2)
                print(f"Metadata saved to: {output_filename}")
                
                # コールバック関数が指定されていれば呼び出し、その後ファイルを削除
                if process_callback:
                    process_callback(info)
                    os.remove(output_filename)
                    print(f"Metadata file {output_filename} deleted after processing.")
                
                return info
            except Exception as ex:
                attempt += 1
                print(f"Attempt {attempt} failed: {ex}")
                if attempt >= self.retries:
                    print("Max retry limit reached. Aborting metadata download.")
                    raise
    
    def download_movie(self, url=False):
        """
        指定されたURLの動画をダウンロードする。
        settings.content_typeが "movie" の場合、実行される。
        動画品質は、settings.movie_qualityをもとに選択される。
        ファイル形式は、settings.movie_formatをもとに選択される。
        
        :param url: ダウンロード対象のコンテンツURL(Falseの場合はエラー)
        """
        if not url:
            raise Exception("Error: url is not defined")
        
        # URLをリストに変換(既にリストの場合はそのまま)
        # こうすることで、インスタンス作成数を減らせるし、将来的なバージョンアップにも対応しやすい
        urls = [url] if isinstance(url, str) else url
        
        quality_format = settings.movie_quality
        movie_format = settings.movie_format
        
        ydl_opts = {
            "format": quality_format,
            "outtmpl": os.path.join(self.save_dir, "%(title)s.%(ext)s"),
            "merge_output_format": movie_format,
            "postprocessors": [{ 
                "key": "FFmpegVideoRemuxer",
                "preferedformat": movie_format,
            }],
            "progress_hooks": [self._progress_hook] if self.show_progress else [],
        }
        
        attempt = 0
        while attempt < self.retries:
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(urls) # リストとして渡す
                print(f"Movie download completed in format: {movie_format}")
                break
            except Exception as ex:
                if not self._check_network():
                    print("A network error occurred. Please check your connection and try again.")
                    raise
                attempt += 1
                print(f"Attempt {attempt} failed: {ex}")
                if attempt >= self.retries:
                    print("Max retry limit reached. Aborting movie download.")
                    raise
    
    def download_music(self, url=False):
        """
        指定されたURLの音楽をダウンロードする。
        settings.content_typeが "music" の場合、実行される。
        音楽品質は、settings.music_qualityをもとに選択される。
        ファイル形式は、settings.music_formatをもとに選択される。
        
        :param url: ダウンロード対象のコンテンツURL(Falseの場合はエラー)
        """
        if not url:
            raise Exception("Error: url is not defined")
        
        # URLをリストに変換(既にリストの場合はそのまま)
        # こうすることで、インスタンス作成数を減らせるし、将来的なバージョンアップにも対応しやすい
        urls = [url] if isinstance(url, str) else url
        
        quality_format = settings.music_quality
        music_format = settings.music_format
        
        ydl_opts = {
            "format": quality_format,
            "outtmpl": os.path.join(self.save_dir, "%(title)s.%(ext)s"),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": music_format,
                "preferredquality": "192", # ビットレート(今後設定ファイルから制御可能にする)
            }],
            "progress_hooks": [self._progress_hook] if self.show_progress else [],
        }
        
        attempt = 0
        while attempt < self.retries:
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(urls)
                print(f"Music download completed in format: {music_format}")
                break
            except Exception as ex:
                if not self._check_network():
                    print("A network error occurred. Please check your connection and try again.")
                    raise
                attempt += 1
                print(f"Attempt {attempt} failed: {ex}")
                if attempt >= self.retries:
                    print("Max retry limit reached. Aborting music download.")
                    raise

class YDownloader:
    def __init__(self, settings, downloader):
        # 設定やグローバル変数相当の初期化
        self.base_dir = settings.base_dir
        self.retries = settings.retry_chance
        self.temp_dir = settings.temp_dir
        self.pre_url_list = []
        self.pre_total_urls = 0
        self.pre_current_urls = 0
        self.cards = {}
        self.added_urls = []
        self.condition_pre = threading.Condition()
        self.downloader = downloader
    
    def preview_video_info(self, url):
        """
        指定URLの動画情報を取得し、一時ディレクトリにJSONとして保存する。
        GUIでの表示用に動画のサムネイル画像、タイトル、投稿日時を取得して、一時ファイルとして保存する。
        アプリが正常終了する時に、一時ファイルはそのフォルダーごと削除する。
        アプリが異常終了したときは、すぐに復帰できるように、一時ファイルは削除しない。
        
        :param url: 動画のURL
        """
        if not url:
            raise Exception("Error: url is not defined")
        
        ydl_opts = {
            "skip_download": True, # 動画本体はダウンロードしない
            "quiet": True, # 進捗状況を表示しない
        }
        attempt = 0
        while attempt < self.retries:
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    # ユニークなIDを生成
                    unique_id = str(uuid.uuid4().hex)
                    # 動画情報を取得
                    info = ydl.extract_info(url, download=False)
                    # タイトルを取得して安全なファイル名に変換
                    title = info.get("title", "Unknown Title")
                    safe_title = re.sub(r'[\\/*?:"<>|]', "_", title)
                    # 動画の投稿者名を取得
                    uploader = info.get("uploader", "Unknown Uploader")
                    # 動画の概要欄情報の取得
                    overview = info.get("description", None)
                    # サムネイル画像の保存
                    thumbnail_path = None
                    try:
                        thumbnail_url = info.get("thumbnail")
                        if thumbnail_url:
                            thumb_filename = f"{unique_id}_thumb.jpg"
                            thumbnail_path = os.path.join(self.temp_dir, thumb_filename)
                            response = requests.get(thumbnail_url)
                            with open(thumbnail_path, "wb") as f:
                                f.write(response.content)
                    except Exception as ex:
                        print(f"Error: {ex}")
                    # 投稿日時のフォーマット
                    upload_date = info.get("upload_date", "Unknown Date")
                    if upload_date and upload_date != "Unknown Date":
                        upload_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y年%m月%d日")
                    # 保存する情報を整理
                    preview_info = {
                        "id": unique_id,
                        "title": safe_title,
                        "upload_date": upload_date,
                        "uploader": uploader,
                        "overview": overview,
                        "thumbnail_path": thumbnail_path,
                        "url": url,
                    }
                    # JSON形式で保存
                    info_filename = f"{unique_id}.json"
                    info_path = os.path.join(self.temp_dir, info_filename)
                    with open(info_path, "w", encoding="utf-8") as f:
                        json.dump(preview_info, f, ensure_ascii=False, indent=2)
                    return info_path
            except Exception as ex:
                if not self.downloader._check_network():
                    print("A network error occurred. Please check your connection and try again.")
                    raise
                attempt += 1
                print(f"Attempt {attempt} failed: {ex}")
                if attempt >= self.retries:
                    print(f"動画情報の取得に失敗しました: {ex}")
                    return None
    
    def cleanup_temp_files(self):
        """
        一時ディレクトリと一時ファイルを削除する。(正常終了時用)
        """
        if os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                print("一時ファイルを削除しました")
            except Exception as ex:
                print(f"一時ファイルの削除に失敗しました: {ex}")
    
    def compute_perfect_size(self, page: ft.Page, thumb_width, thumb_height, key):
        """
        ページのウィンドウサイズから16:9枠内に収まるフレームサイズを計算し、
        サムネイル画像サイズ(又は、画像がない場合はプレースホルダー(灰色画像を生成して保存))を返す。
        """
        if not key:
            raise AttributeError(f"keyの値が不明です。")
        frame_width = int(page.window.width / 4)
        frame_height = int(frame_width * 9 / 16)
        if thumb_width == 0 or thumb_height == 0:
            # サムネイル画像がない場合は、プレースホルダー画像を生成する
            img = Image.new("RGB", (1280, 720), (128, 128, 128))
            thumbnail_path = os.path.join(self.temp_dir, f"{key}_thumb.jpg")
            img.save(thumbnail_path, format="JPEG", quality=95) # JPG形式で保存
            return {
                "src": thumbnail_path, 
                "width": frame_width,
                "height": frame_height
            }
        else:
            if int(thumb_height) > int(thumb_width * 9 / 16):
                background_width = int(thumb_height * 16 / 9)
                background_height = int(thumb_height)
            else:
                background_width = int(thumb_width)
                background_height = int(thumb_width * 9 / 16)
            offset_x = int((background_width - thumb_width) / 2)
            offset_y = int((background_height - thumb_height) / 2)
            return {
                "width": background_width,
                "height": background_height,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "frame_width": frame_width,
                "frame_height": frame_height
            }
    
    # 動画読み込み後のカード追加用関数
    def add_video_card(self, page: ft.Page):
        """
        URLリストからURLを取り出し、動画情報を取得してカードを生成し、ページに追加する。
        ※無限ループ内でスレッドとして実行する
        """
        while True:
            with self.condition_pre:
                while not self.pre_url_list:
                    self.pre_total_urls = 0
                    self.pre_current_urls = 0
                    self.condition_pre.wait()
                url = self.pre_url_list.pop(0) # pop(0)で先頭のURLを取得してリストから削除
            try:
                self.pre_current_urls += 1
                json_path = self.preview_video_info(url=url)
                # デバッグ用
                # print(f"Generated JSON path: {json_path}")
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # デバッグ用
                # print(f"data: {data}")
                # 各Cardに追加されるkey
                key = data.get("id", "Unknown ID")
                if key == "Unknown ID":
                    raise ValueError("IDが不明です。")
                video_title = ft.TextField(
                    label="タイトル",
                    value=data.get("title"),
                    adaptive=True
                )
                video_overview = ft.TextField(
                    label="概要",
                    value=data.get("overview") if data.get("overview") else "概要欄情報が見つかりませんでした。",
                    multiline=True,
                    max_lines=2, # カードの高さが画像に合わせて自動調整されるようにして、さらにmax_linesをアダプティブに変更されるようにしたい
                    expand=True,
                )
                video_date = ft.Text(
                    value=data.get("upload_date"),
                )
                video_uploader = ft.TextField(
                    label="投稿者",
                    value=data.get("uploader"),
                    adaptive=True,
                )
                video_upload_info = ft.Column(
                    controls=[
                        video_uploader, # この部分はcenter表示のまま
                        ft.Container(
                            content=ft.Row(
                                controls=[video_date],
                            ),
                        ),
                    ],
                )
                thumbnail_img_src = data.get("thumbnail_path")
                if not thumbnail_img_src:
                    # サムネイルがない場合は、compute_perfect_sizeでプレースホルダー画像を生成
                    placeholder = self.compute_perfect_size(page, 0, 0, key)
                    video_thumbnail_img = ft.Image(
                        src=placeholder["src"],
                        width=placeholder["width"],
                        height=placeholder["height"],
                        fit=ft.ImageFit.CONTAIN,
                        border_radius=ft.border_radius.all(10),
                    )
                else:
                    # 画像を読み込み、16:9の枠内に収まるように中央配置した背景画像を作成
                    with Image.open(thumbnail_img_src) as img:
                        img_width, img_height = img.size
                        perfect_img_size = self.compute_perfect_size(page, img_width, img_height, key)
                        # 灰色の背景画像作成
                        # リサイズはなし
                        background = Image.new("RGB", (perfect_img_size["width"], perfect_img_size["height"]), (128, 128, 128))
                        background.paste(img, (perfect_img_size["offset_x"], perfect_img_size["offset_y"]))
                        # サムネイル画像配置枠
                        frame_width = perfect_img_size["frame_width"]
                        frame_height = perfect_img_size["frame_height"]
                        # .temp内の一時ファイルに保存
                        with tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir, suffix=".jpg") as temp_file:
                            temp_path = temp_file.name
                            background.save(temp_path, format="JPEG", quality=95) # JPG形式で保存
                    # 元のファイルをバックアップ
                    backup_path = thumbnail_img_src + ".bak"
                    os.rename(thumbnail_img_src, backup_path)
                    # 一時ファイルを元のファイルに置き換え
                    os.rename(temp_path, thumbnail_img_src)
                    # バックアップ削除(上書きが成功した場合)
                    os.remove(backup_path)
                    video_thumbnail_img = ft.Image(
                        src=thumbnail_img_src,
                        width=frame_width,
                        height=frame_height,
                        fit=ft.ImageFit.CONTAIN,
                        border_radius=ft.border_radius.all(10),
                    )
                delete_icon = ft.IconButton(icon=ft.icons.DELETE_FOREVER_ROUNDED)
                download_icon = ft.IconButton(icon=ft.icons.DOWNLOAD)
                about_info = ft.Column(
                    controls=[
                        video_title,
                        ft.Row(
                            controls=[
                                video_overview,
                                video_upload_info
                            ]
                        )
                    ],
                    expand=True,
                )
                video_card = ft.Card(
                    key=key,
                    content=ft.Container(
                        content=ft.Row(
                            controls=[
                                video_thumbnail_img,
                                about_info,
                                ft.Column(
                                    controls=[
                                        download_icon,
                                        delete_icon
                                    ],
                                    alignment=ft.alignment.center,
                                ),
                            ],
                            alignment=ft.alignment.center,
                        ),
                    ),
                    margin=0,
                )
                self.cards[key] = video_card
                page.add(video_card)
                page.update()
            except Exception as ex:
                print(f"Error adding video card: {ex}")
            time.sleep(0.5) # 連続処理の負荷を軽減
    
    def handle_url_submit(self, e, tf, page):
        """
        テキストフィールドからURLを取得し、
        URL(存在確認と重複確認のチェックを抜けたもののみ)を追加し、条件変数を通知する
        """
        try:
            urls = tf.value.split("\n")
            if not urls:
                return
            tf.value = "" # add_video_cardは実行に時間がかかるため、先にクリアしておく
            page.update()
            # 正常な値かどうかを確認&重複確認
            valid_urls = [s for s in map(str.strip, urls) if s and s not in self.pre_url_list and s not in self.added_urls]
            if valid_urls: # 追加するURLがある場合の処理
                with self.condition_pre:
                    self.pre_total_urls += len(valid_urls) # 追加するURLの数を追加
                    self.pre_url_list.extend(valid_urls) # URLをリスト末尾に追加
                    self.condition_pre.notify() # 待機中のスレッドを起こす
        except Exception as ex:
            print(f"Error in handle_url_submit: {ex}")
            traceback.print_exc()
    
    def handle_window_resize(self, e, page):
        """
        ウィンドウサイズが変更された時に実行される関数
        """
        # 画面幅が変更された時の処理
        updated_width = int(page.window.width / 4)
        updated_height = int(updated_width * 9 / 16)
        for key, card in self.cards.items():
            row = card.content.content
            thumbnail_img = row.controls[0]
            thumbnail_img.width = updated_width
            thumbnail_img.height = updated_height
            page.update()
    
    def download_video_by_key(self, e, key):
        """
        ダウンロードボタンが押されたカードの動画をダウンロードするコールバック関数
        """
        try:
            target_card = self.cards[key]
            target_row = target_card.content.content
            target_about_info = target_row.controls[1]
            target_title = target_about_info.controls[0]
            target_upload_info = target_about_info.controls[1].controls[1]
            target_uploader = target_upload_info.controls[0]
            json_path = os.path.join(self.temp_dir, f"{key}.json")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            target_url = data.get("url", None)
            if not target_url:
                raise AttributeError(f"JSONファイルにおけるURLの値が不正です。")
        except Exception as ex:
            raise ex
    
    def toggle_theme(self, e, page):
        """Fletのページテーマを変更する"""
        try:
            if page.theme_mode == ft.ThemeMode.LIGHT:
                page.theme_mode = ft.ThemeMode.DARK
            else:
                page.theme_mode = ft.ThemeMode.LIGHT
            page.update()
        except AttributeError as ex:
            print(f"Error in toggle_theme: {ex}")
            traceback.print_exc()
    
    def main(self, page: ft.Page):
        """
        Fletのページを構築するメインメソッド
        """
        page.title = "YDownloader"
        page.scroll = "adaptive"
        # ウィンドウのリサイズイベントを監視する(リサイズが完了したタイミングで実行されるようにする)
        page.on_resized = lambda e: self.handle_window_resize(e, page)
        # プログレスバーの作成
        progress_bar = ft.ProgressBar(value=0, visible=False) # visible=Trueで表示
        progress_container = ft.Container(
            content=progress_bar,
            height=10,
            padding=ft.padding.all(5),
        )
        # フォントの読み込み
        font_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "fonts", "ZenOldMincho")
        page.fonts = {
            "ZenOldMincho-Black": os.path.join(font_dir, "ZenOldMincho-Black.ttf"),
            "ZenOldMincho-Bold": os.path.join(font_dir, "ZenOldMincho-Bold.ttf"),
            "ZenOldMincho-SemiBold": os.path.join(font_dir, "ZenOldMincho-SemiBold.ttf"),
            "ZenOldMincho-Medium": os.path.join(font_dir, "ZenOldMincho-Medium.ttf"),
            "ZenOldMincho-Regular": os.path.join(font_dir, "ZenOldMincho-Regular.ttf")
        } # 上の方が字が太い
        # アプリ全体のデフォルトフォントとして、"ZenOldMincho-Regular"を設定(ユーザーが変えられるようにする)
        page.theme = ft.Theme(font_family="ZenOldMincho-SemiBold")
        
        t = ft.Text(
            value="YDownloader",
            size=30,
        )
        tt = ft.Container(
            content=t,
            alignment=ft.alignment.center
        )
        
        # 設定ボタン(歯車アイコン)
        # 押すと設定ページに遷移できるようにする
        setting_button = ft.IconButton(icon=ft.icons.SETTINGS_ROUNDED)
        # stackを使用して、歯車アイコンを他のレイアウトに影響を与えることなく右上に配置する
        stack = ft.Stack(
            controls=[
                tt, # 下層のレイアウト
                setting_button, # このボタンが上に重ねられる
            ],
            alignment=ft.alignment.top_right
        )
        
        tf = ft.TextField(
            label="URL",
            value="",
            expand=True, # こうすることで、虫眼鏡アイコンとの配置が最適なものになる
            adaptive=True, # iOS向けに適切なデザインになる
            autofocus=True, # 最初にURL入力欄がフォーカスされる
            multiline=True, # 複数行入力可能にする
            max_lines=2,
            shift_enter=True, # Shift+Enterで改行できるようにする
            on_submit=lambda e: self.handle_url_submit(e, tf, page), # Enter(Shiftなし)で送信する処理
        )
        # 検索アイコンのボタン
        sb = ft.IconButton(
            icon=ft.icons.SEARCH_ROUNDED,
            on_click=lambda e: self.handle_url_submit(e, tf, page)
        )
        
        # RadioGroupを作成(保存形式をMovieとMusicで選択(デフォルトを変えるのではなく、あくまでその動画単体の保存方法変更))
        rg = ft.RadioGroup(
            value=settings.content_type,
            content=ft.Row([
                ft.Radio(value="movie", label="Movie"),
                ft.Radio(value="music", label="Music"),
            ]), # RowをColumnにすると縦になる
        )
        
        # テーマ切り替えボタン
        toggle_button = ft.ElevatedButton("テーマを切り替える", on_click=lambda e: self.toggle_theme(e, page))
        
        # デフォルトのページテーマを読み込む
        page.theme_mode = settings.page_theme
        
        page.add(
            stack,
            ft.Card(
                content=ft.Container(
                    content=ft.Row(
                        controls=[
                            tf, sb
                        ], spacing=20,
                    ), padding=10,
                ), margin=5,
            ),
            # rg,
            # toggle_button,
        )
        
        # URL監視スレッドの起動
        processing_thread = threading.Thread(
            target=self.add_video_card,
            args=(page,),
            daemon=True
        )
        processing_thread.start()

if __name__ == "__main__":
    settings = DefaultSettingsLoader()
    downloader = Download(settings)
    app = YDownloader(settings, downloader)
    ft.app(target=app.main)