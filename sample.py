import os
import json
import discord
from discord import app_commands

# Intents 設定：メッセージ内容取得を有効化
intents = discord.Intents.default()
intents.message_content = True  # on_message で内容を扱うため必須

class EchoClient(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)  # slash コマンド管理ツリー :contentReference[oaicite:2]{index=2}
        self.config_path = "config.json"

    async def setup_hook(self):
        # 起動時に全ギルド／グローバルコマンドを Discord に同期
        await self.tree.sync()
        print("Slash commands synced.")

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message: discord.Message):
        # Bot 自身のメッセージは無視
        if message.author.id == self.user.id:
            return

        # 保存済みのおうむ返しチャンネルをロード
        try:
            with open(self.config_path, "r") as f:
                cfg = json.load(f)
                target_id = cfg.get("echo_channel_id")
        except FileNotFoundError:
            target_id = None

        # 設定チャンネルだけでおうむ返し
        if target_id and message.channel.id == target_id:
            await message.channel.send(message.content)

# クライアント生成
client = EchoClient()

# 引数なし：実行元チャンネルをそのまま設定
@client.tree.command(
    name="set_echo_channel",
    description="このチャンネルをBotメッセージ送信チャンネルに設定します"
)
async def set_echo_channel(interaction: discord.Interaction):
    channel = interaction.channel  # 実行されたチャンネルを取得 :contentReference[oaicite:3]{index=3}
    # 永続化
    with open(client.config_path, "w") as f:
        json.dump({"echo_channel_id": channel.id}, f)
    # 設定完了メッセージ（実行者の画面のみ表示）
    await interaction.response.send_message(
        f"Botメッセージ送信チャンネルを **{channel.mention}** に設定しました", 
        ephemeral=True
    )

if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("環境変数 DISCORD_TOKEN が設定されていません")
    client.run(token)
