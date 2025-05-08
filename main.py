import os
import json
import discord
from discord import app_commands
import requests
import asyncio
from datetime import datetime, timedelta
import pytz

intents = discord.Intents.default()

class WebMonitorClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.config_path = "config.json"
        self.watched_urls = {}
        self.previous_content = {}
        self.notification_channels = {}
        self.monitoring_tasks = {}
        self.monitoring_enabled = {}
        self.monitoring_intervals = {}
        self.timezone_jst = pytz.timezone('Asia/Tokyo')

    async def setup_hook(self):
        await self.tree.sync()
        print("Slash commands synced.")
        self.load_config()
        for guild_id, urls in self.watched_urls.items():
            if self.notification_channels.get(guild_id) and urls and self.monitoring_intervals.get(guild_id, 5) > 0:
                self.start_monitoring_task(guild_id)
            elif not urls:
                print(f"サーバー {guild_id} に監視URLが設定されていません。")
            elif not self.notification_channels.get(guild_id):
                print(f"サーバー {guild_id} に通知チャンネルが設定されていません。")
            elif self.monitoring_intervals.get(guild_id, 0) <= 0:
                print(f"サーバー {guild_id} の監視間隔が不正です。")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    def load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
                self.watched_urls = self.config.get("watched_urls", {})
                self.previous_content = self.config.get("previous_content", {})
                self.notification_channels = self.config.get("notification_channels", {})
                self.monitoring_enabled = {guild_id: True for guild_id in self.watched_urls}
                self.monitoring_intervals = self.config.get("monitoring_intervals", {})
        except (FileNotFoundError, json.JSONDecodeError):
            self.config = {"watched_urls": {}, "previous_content": {}, "notification_channels": {}, "monitoring_intervals": {}}
            self.save_config()
            self.monitoring_enabled = {}
            self.monitoring_intervals = {}

    def save_config(self):
        self.config["watched_urls"] = self.watched_urls
        self.config["previous_content"] = self.previous_content
        self.config["notification_channels"] = self.notification_channels
        self.config["monitoring_intervals"] = self.monitoring_intervals
        with open(self.config_path, "w") as f:
            json.dump(self.config, f, indent=4)

    async def fetch_webpage_content(self, url):
        try:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                )
            }
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"ウェブページの取得に失敗しました ({url}): {e}")
            return None

    async def compare_content(self, current_content, url):
        if url not in self.previous_content:
            self.previous_content[url] = current_content
            self.save_config()
            return False
        if self.previous_content[url] != current_content:
            self.previous_content[url] = current_content
            self.save_config()
            return True
        return False

    async def monitor_website(self, guild_id):
        if not self.monitoring_enabled.get(guild_id, False):
            return

        urls = self.watched_urls.get(guild_id, [])
        notification_channel_id = self.notification_channels.get(guild_id)
        if not urls or not notification_channel_id:
            return

        channel = self.get_channel(notification_channel_id)
        if not channel:
            return

        for url in urls:
            content = await self.fetch_webpage_content(url)
            if content and await self.compare_content(content, url):
                now_jst = datetime.now(self.timezone_jst).strftime('%H:%M')
                print(f"サーバー {guild_id}: '{url}' に変更がありました ({now_jst} JST)。")
                await channel.send(f"⚠️ **{url}** に変更が検出されました ({now_jst} JST)。")

    async def start_server_monitoring(self, guild_id):
        interval = self.monitoring_intervals.get(guild_id, 5)
        if interval <= 0:
            print(f"サーバー {guild_id}: 監視間隔が不正です。")
            self.monitoring_enabled[guild_id] = False
            return

        print(f"サーバー {guild_id}: 監視タスクを開始します (間隔: {interval} 分)。")
        # 起動後すぐに一度監視を実行
        await self.monitor_website(guild_id)

        while self.monitoring_enabled.get(guild_id, False):
            now = datetime.now(self.timezone_jst)
            
            # 次の実行時刻を計算（現在時刻から最も近い interval 分の倍数の0秒時）
            next_minute = (now.minute // interval + 1) * interval
            if next_minute >= 60:
                next_minute = 0
                next_hour = now.hour + 1
            else:
                next_hour = now.hour
            
            next_run = now.replace(hour=next_hour, minute=next_minute, second=0, microsecond=0)
            
            # 待機時間を計算
            wait_seconds = (next_run - now).total_seconds()
            
            print(
                f"サーバー {guild_id}: 次回監視は "
                f"{next_run.strftime('%H:%M:%S')} (あと約 {int(wait_seconds)} 秒)"
            )
            
            # 待機
            await asyncio.sleep(wait_seconds)
            
            # 待機後に監視を実行
            await self.monitor_website(guild_id)

    def start_monitoring_task(self, guild_id):
        if guild_id not in self.monitoring_tasks or self.monitoring_tasks[guild_id].done():
            self.monitoring_enabled[guild_id] = True
            self.monitoring_intervals.setdefault(guild_id, 5)
            print(f"サーバー {guild_id} の監視タスクを開始しました (間隔: {self.monitoring_intervals[guild_id]}分)。")
            self.monitoring_tasks[guild_id] = asyncio.create_task(self.start_server_monitoring(guild_id))
            return True
        else:
            print(f"サーバー {guild_id} の監視タスクはすでに実行中です。")
            return False

    def stop_monitoring_task(self, guild_id):
        if guild_id in self.monitoring_tasks and not self.monitoring_tasks[guild_id].done():
            self.monitoring_enabled[guild_id] = False
            self.monitoring_tasks[guild_id].cancel()
            print(f"サーバー {guild_id} の監視タスクの停止を試みました。")
            return True
        else:
            print(f"サーバー {guild_id} の監視タスクは実行されていません。")
            return False


client = WebMonitorClient()


# --- 以下、コマンド定義部は元コードをそのまま流用 ---
@client.tree.command(
    name="add_watch_url",
    description="このサーバーで監視するWebページのURLを追加します"
)
async def add_watch_url(interaction: discord.Interaction, url: str):
    guild_id = str(interaction.guild.id)
    client.load_config()
    if guild_id not in client.watched_urls:
        client.watched_urls[guild_id] = []
    if url not in client.watched_urls[guild_id]:
        client.watched_urls[guild_id].append(url)
        content = await client.fetch_webpage_content(url)
        if content:
            client.previous_content[url] = content
            client.save_config()
            await interaction.response.send_message(
                f"このサーバーの監視URLに **{url}** を追加し、初期コンテンツを保存しました。"
            )
            if client.notification_channels.get(guild_id) and client.monitoring_intervals.get(guild_id, 5) > 0:
                client.start_monitoring_task(guild_id)
            elif not client.notification_channels.get(guild_id):
                await interaction.followup.send(
                    "通知チャンネルが設定されていません。"
                    "`/set_notification_channel` コマンドで設定してください。",
                    ephemeral=True
                )
            elif client.monitoring_intervals.get(guild_id, 0) <= 0:
                await interaction.followup.send(
                    "監視間隔が設定されていません。"
                    "`/set_interval` コマンドで設定してください。",
                    ephemeral=True
                )
        else:
            await interaction.response.send_message(
                f"**{url}** の初期コンテンツの取得に失敗しました。"
                "URLは追加されましたが、監視されない可能性が高いです。"
            )
    else:
        await interaction.response.send_message(
            f"**{url}** はすでにこのサーバーの監視リストに登録されています。",
            ephemeral=True
        )

@client.tree.command(
    name="remove_watch_url",
    description="このサーバーの監視リストからWebページのURLを削除します"
)
async def remove_watch_url(interaction: discord.Interaction, url: str):
    guild_id = str(interaction.guild.id)
    client.load_config()
    if guild_id in client.watched_urls and url in client.watched_urls[guild_id]:
        client.watched_urls[guild_id].remove(url)
        if url in client.previous_content:
            del client.previous_content[url]
        client.save_config()
        await interaction.response.send_message(
            f"このサーバーの監視リストから **{url}** を削除しました。"
        )
        if not client.watched_urls[guild_id] and client.monitoring_tasks.get(guild_id):
            client.stop_monitoring_task(guild_id)
            await interaction.followup.send(
                "監視リストが空になったため、監視を停止しました。",
                ephemeral=True
            )
    else:
        await interaction.response.send_message(
            f"**{url}** はこのサーバーの監視リストに登録されていません。",
            ephemeral=True
        )

@client.tree.command(
    name="list_watch_urls",
    description="このサーバーで監視しているWebページのURLを表示します"
)
async def list_watch_urls(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    client.load_config()
    urls = client.watched_urls.get(guild_id, [])
    if urls:
        await interaction.response.send_message(
            f"このサーバーで監視中のURL:\n- {'\n- '.join(urls)}"
        )
    else:
        await interaction.response.send_message("このサーバーでは何も監視していません。")

@client.tree.command(
    name="set_notification_channel",
    description="このチャンネルをBotメッセージ送信先に設定します。"
)
async def set_notification_channel(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    client.load_config()
    client.notification_channels[guild_id] = interaction.channel_id
    client.save_config()
    await interaction.response.send_message(
        f"更新通知チャンネルを **{interaction.channel.mention}** に設定しました。"
    )
    if client.watched_urls.get(guild_id) and client.monitoring_intervals.get(guild_id, 5) > 0:
        client.start_monitoring_task(guild_id)
    else:
        await interaction.followup.send(
            "監視URLまたは監視間隔が設定されていません。"
            "`/add_watch_url` および `/set_notification_channel` コマンドで設定してください。",
            ephemeral=True
        )

@client.tree.command(
    name="set_interval",
    description="このサーバーでの監視間隔をN分に設定します"
)
async def set_interval(interaction: discord.Interaction, interval: int):
    guild_id = str(interaction.guild.id)
    if interval <= 0:
        await interaction.response.send_message(
            "監視間隔は1以上の整数で指定してください。", ephemeral=True
        )
        return
    client.load_config()
    client.monitoring_intervals[guild_id] = interval
    client.save_config()
    await interaction.response.send_message(
        f"このサーバーの監視間隔を **{interval}** 分に設定しました。"
    )
    print(f"サーバー {guild_id}: 監視間隔を {interval} 分に設定しました。")
    if client.watched_urls.get(guild_id) and client.notification_channels.get(guild_id):
        client.start_monitoring_task(guild_id)
    else:
        await interaction.followup.send(
            "監視URLまたは通知チャンネルが設定されていません。"
            "`/add_watch_url` および `/set_notification_channel` コマンドで設定してください。",
            ephemeral=True
        )

@client.tree.command(
    name="stop_monitoring",
    description="このサーバーでのWebサイトの監視機能を停止します"
)
async def stop_monitoring(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    stopped = client.stop_monitoring_task(guild_id)
    if stopped:
        await interaction.response.send_message("このサーバーでのWebサイトの監視機能を停止しました。")
    else:
        await interaction.response.send_message(
            "このサーバーでは監視機能はすでに停止しています。", ephemeral=True
        )

@client.tree.command(
    name="start_monitoring",
    description="このサーバーでのWebサイトの監視機能を再開します"
)
async def start_monitoring(interaction: discord.Interaction):
    guild_id = str(interaction.guild.id)
    started = client.start_monitoring_task(guild_id)
    if started:
        interval = client.monitoring_intervals.get(guild_id, 5)
        print(f"サーバー {guild_id}: 監視を再開しました (間隔: {interval}分)。")
        await interaction.response.send_message(
            f"このサーバーでのWebサイトの監視機能を再開します (間隔: {interval}分)。"
        )
    else:
        await interaction.response.send_message(
            "このサーバーでは監視機能はすでに実行中です。", ephemeral=True
        )

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("環境変数 DISCORD_TOKEN が設定されていません")
    client.run(token)
