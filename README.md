# UpdateDetection

***[インストールリンク](https://discord.com/oauth2/authorize?client_id=1368495921796747315&permissions=84992&integration_type=0&scope=bot+applications.commands)***

## Slash コマンド一覧

| コマンド名 | 引数 | 説明 |
|------------|------|------|
| `/add_watch_url` | `url` | 指定した URL を監視リストに追加します。 |
| `/remove_watch_url` | `url` | 監視リストから URL を削除します。 |
| `/list_watch_urls` | なし | 現在監視中の URL を一覧表示します。 |
| `/set_notification_channel` | なし | コマンドを実行したチャンネルを通知チャンネルとして登録します。 |
| `/set_interval` | `interval` (分) | 監視間隔を N 分に設定します (1 以上)。 |
| `/start_monitoring` | なし | Web サイトの監視を再開します。 |
| `/stop_monitoring` | なし | Web サイトの監視を停止します。 |

---

## 使用例

1. Bot をサーバーに招待し、任意のテキストチャンネルで以下を実行してください。
2. 通知チャンネルを登録:
   ```
   /set_notification_channel
   ```
3. 監視間隔を 3 分に設定:
   ```
   /set_interval interval 3
   ```
4. 監視したい URL を追加:
   ```
   /add_watch_url https://example.com
   ```
5. 監視を停止・再開したい場合:
   ```
   /stop_monitoring
   /start_monitoring
   ```

---

## 仕組み

- `config.json` に各サーバー (Guild) ごとの監視 URL・前回取得コンテンツ・通知チャンネル・監視間隔を保存します。
- 監視タスクは `interval` 分の倍数かつ 0 秒のタイミングで実行され、ページ内容が変化した場合にのみ通知を送信します。
- 通知には JST (Asia/Tokyo) の時刻が付与されます。