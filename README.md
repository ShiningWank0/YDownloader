# YDownloader

[![GitHub Actions](https://github.com/your-repo/YDownloader/actions/workflows/build.yml/badge.svg)](https://github.com/your-repo/YDownloader/actions)

YDownloader is a GUI-based downloader application built with Flet, designed for easy video downloading via URLs. The app seamlessly integrates with yt-dlp, ensuring that updates can be applied with minimal changes.

YDownloaderは、Fletを用いたGUIベースのダウンローダーアプリです。URLを入力するだけで簡単に動画をダウンロードできます。yt-dlpとの統合をスムーズにし、最小限の変更でアップデートが可能です。

## 🌟 Features | 特徴

### 🌍 English
- **Intuitive GUI:** Enter a video URL in the search bar and press the search icon or `Enter` to load the video.
- **Multiline Input:** Use `Shift + Enter` to insert a new line in the search bar.
- **Easy yt-dlp Updates:** Place `yt-dlp` inside the `external` folder. This allows applying patches to update yt-dlp without modifying the main application.
- **Automated Builds:** Installers and patches are generated automatically using **GitHub Actions**, ensuring smooth updates.

### 🇯🇵 日本語
- **直感的なGUI:** 検索欄にダウンロードしたい動画のURLを入力し、検索アイコンまたは `Enter` を押すと動画の読み込みが行われます。
- **複数行入力対応:** `Shift + Enter` を押すことで検索欄内で改行できます。
- **簡単なyt-dlpの更新:** `external` フォルダーに `yt-dlp` を配置することで、パッチを適用するだけで最新版に更新できる仕組みになっています。
- **自動ビルド:** **GitHub Actions** を使用してインストーラーやパッチを自動生成し、スムーズなアップデートを提供します。

## 📥 Installation | インストール方法

<details>
  <summary>English</summary>

1. **Download the installer** from [Releases](https://github.com/your-repo/YDownloader/releases).
2. Run the installer and follow the on-screen instructions.
3. Start the application and enter a URL to begin downloading.
4. Place `yt-dlp` inside the `external` folder to keep it updated easily.

</details>

<details>
  <summary>日本語</summary>

1. **インストーラーをダウンロード** [Releases](https://github.com/your-repo/YDownloader/releases) からダウンロードしてください。
2. インストーラーを実行し、画面の指示に従ってインストールしてください。
3. アプリを起動し、URLを入力してダウンロードを開始します。
4. `external` フォルダーに `yt-dlp` を配置すると、簡単に更新できます。

</details>

## 🛠 Development | 開発

<details>
  <summary>English</summary>

### Requirements
- Python 3.9+
- Flet
- yt-dlp

### Setup
```sh
git clone https://github.com/your-repo/YDownloader.git
cd YDownloader
pip install -r requirements.txt
python main.py
