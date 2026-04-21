import asyncio
import discord
from telegram import Bot as TelegramBot
from telegram.error import TelegramError
import aiohttp
from io import BytesIO
from typing import Optional, Union
import traceback

from config import Config
from logger import setup_logger

# Setup logger
logger = setup_logger("DiscordTelegramBot", Config.LOG_LEVEL)

class DiscordTelegramReposter:
    """Advanced Discord to Telegram reposter bot"""
    
    def __init__(self):
        self.discord_client = None
        self.telegram_bot = None
        self.session = None
        
    async def initialize(self):
        """Initialize both bots and session"""
        # Create aiohttp session for file downloads
        self.session = aiohttp.ClientSession()
        
        # Initialize Telegram bot
        self.telegram_bot = TelegramBot(Config.TELEGRAM_TOKEN)
        
        # Initialize Discord bot with required intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.attachments = True
        
        self.discord_client = discord.Client(intents=intents)
        
        # Setup event handlers
        @self.discord_client.event
        async def on_ready():
            await self.on_discord_ready()
        
        @self.discord_client.event
        async def on_message(message):
            await self.on_discord_message(message)
        
        @self.discord_client.event
        async def on_error(event, *args, **kwargs):
            logger.error(f"Discord error in {event}: {traceback.format_exc()}")
    
    async def on_discord_ready(self):
        """Handle Discord bot ready event"""
        logger.info(f"✅ Discord bot connected as {self.discord_client.user}")
        logger.info(f"📡 Monitoring channel ID: {Config.DISCORD_CHANNEL_ID}")
        
        # Verify channel exists
        channel = self.discord_client.get_channel(Config.DISCORD_CHANNEL_ID)
        if channel:
            logger.info(f"📢 Monitoring: #{channel.name} in {channel.guild.name}")
        else:
            logger.error(f"❌ Channel {Config.DISCORD_CHANNEL_ID} not found!")
    
    async def download_file(self, url: str) -> Optional[BytesIO]:
        """Download file from URL"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    if len(data) <= Config.MAX_FILE_SIZE:
                        return BytesIO(data)
                    else:
                        logger.warning(f"File too large: {len(data)} bytes")
                        return None
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return None
    
    async def send_to_telegram(self, content: str, file_data: Optional[BytesIO] = None, 
                               filename: str = "file", is_image: bool = False):
        """Send message or file to Telegram channel"""
        try:
            if file_data:
                if is_image:
                    # Send as photo
                    await self.telegram_bot.send_photo(
                        chat_id=Config.TELEGRAM_CHANNEL_ID,
                        photo=file_data,
                        caption=content[:1024] if content else None,  # Telegram caption limit
                        read_timeout=30,
                        write_timeout=30
                    )
                else:
                    # Send as document
                    await self.telegram_bot.send_document(
                        chat_id=Config.TELEGRAM_CHANNEL_ID,
                        document=file_data,
                        filename=filename,
                        caption=content[:1024] if content else None,
                        read_timeout=30,
                        write_timeout=30
                    )
            else:
                # Send text only, split if too long
                if len(content) > 4096:
                    for i in range(0, len(content), 4096):
                        await self.telegram_bot.send_message(
                            chat_id=Config.TELEGRAM_CHANNEL_ID,
                            text=content[i:i+4096],
                            read_timeout=30
                        )
                else:
                    await self.telegram_bot.send_message(
                        chat_id=Config.TELEGRAM_CHANNEL_ID,
                        text=content,
                        read_timeout=30
                    )
            
            logger.info(f"✅ Message sent to Telegram")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Telegram error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return False
    
    async def process_attachments(self, attachments: list) -> list:
        """Process Discord attachments and prepare for Telegram"""
        results = []
        
        for attachment in attachments:
            logger.info(f"📎 Processing attachment: {attachment.filename}")
            
            # Download file
            file_data = await self.download_file(attachment.url)
            if not file_data:
                continue
            
            # Check if it's an image
            is_image = attachment.content_type and attachment.content_type.startswith('image/')
            
            results.append({
                'data': file_data,
                'filename': attachment.filename,
                'is_image': is_image
            })
        
        return results
    
    async def format_discord_message(self, message: discord.Message) -> str:
        """Format Discord message for Telegram with rich content"""
        parts = []
        
        # Author info
        author_name = message.author.display_name
        if message.author.bot:
            author_name += " [BOT]"
        
        parts.append(f"**{author_name}**")
        parts.append(f"📅 {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Message content
        if message.content:
            parts.append(f"\n{message.content}")
        
        # Reply reference
        if message.reference and message.reference.resolved:
            replied_msg = message.reference.resolved
            parts.append(f"\n↪️ **Replying to:** {replied_msg.author.display_name}")
            if replied_msg.content:
                preview = replied_msg.content[:100] + "..." if len(replied_msg.content) > 100 else replied_msg.content
                parts.append(f"   {preview}")
        
        # Embeds
        if message.embeds:
            for embed in message.embeds:
                parts.append(f"\n📦 **Embed:**")
                if embed.title:
                    parts.append(f"**{embed.title}**")
                if embed.description:
                    parts.append(embed.description)
                if embed.url:
                    parts.append(f"🔗 {embed.url}")
        
        # Stickers
        if message.stickers:
            parts.append(f"\n🎨 **Stickers:** {', '.join([s.name for s in message.stickers])}")
        
        # Join with newlines
        return "\n".join(parts)
    
    async def on_discord_message(self, message: discord.Message):
        """Handle Discord messages and repost to Telegram"""
        
        # Ignore bot's own messages
        if message.author == self.discord_client.user:
            return
        
        # Check if message is from monitored channel
        if message.channel.id != Config.DISCORD_CHANNEL_ID:
            return
        
        logger.info(f"📨 New message from {message.author} in #{message.channel.name}")
        
        try:
            # Format message content
            formatted_content = await self.format_discord_message(message)
            
            # Add source footer
            footer = f"\n\n---\n🔄 Reposted from Discord | #{message.channel.name}"
            if len(formatted_content + footer) < 4096:
                formatted_content += footer
            
            # Process attachments
            attachments_data = await self.process_attachments(message.attachments)
            
            # Send to Telegram
            if attachments_data:
                # Send text first if present
                if formatted_content:
                    await self.send_to_telegram(formatted_content)
                
                # Send each attachment
                for attachment in attachments_data:
                    await self.send_to_telegram(
                        content=f"📎 {attachment['filename']}",
                        file_data=attachment['data'],
                        filename=attachment['filename'],
                        is_image=attachment['is_image']
                    )
            else:
                # Send only text
                await self.send_to_telegram(formatted_content)
                
        except Exception as e:
            logger.error(f"❌ Failed to process message: {e}")
            logger.error(traceback.format_exc())
    
    async def health_check(self):
        """Periodic health check"""
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            try:
                # Check Discord connection
                if not self.discord_client.is_closed():
                    logger.debug("✅ Discord connection OK")
                
                # Check Telegram connection
                await self.telegram_bot.get_me()
                logger.debug("✅ Telegram connection OK")
                
            except Exception as e:
                logger.error(f"⚠️ Health check failed: {e}")
    
    async def start(self):
        """Start the bot"""
        try:
            # Validate configuration
            Config.validate()
            logger.info("✅ Configuration validated")
            
            # Initialize components
            await self.initialize()
            
            # Start health check
            asyncio.create_task(self.health_check())
            
            # Start Discord bot
            async with self.discord_client:
                await self.discord_client.start(Config.DISCORD_TOKEN)
                
        except Exception as e:
            logger.error(f"❌ Failed to start bot: {e}")
            raise
        finally:
            if self.session:
                await self.session.close()
    
    async def stop(self):
        """Gracefully stop the bot"""
        logger.info("🛑 Shutting down bot...")
        if self.discord_client:
            await self.discord_client.close()
        if self.session:
            await self.session.close()
        logger.info("✅ Bot stopped")

async def main():
    """Main entry point"""
    bot = DiscordTelegramReposter()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        await bot.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        await bot.stop()
        raise

if __name__ == "__main__":
    asyncio.run(main())