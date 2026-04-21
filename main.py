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
        intents.message_content = True  # Required to read message content
        # Note: There's NO 'attachments' intent - attachments are automatically 
        # included when message_content intent is enabled
        
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
            logger.error(f"❌ Channel {Config.DISCORD_CHANNEL_ID} not found! Make sure the bot has access to this channel.")
    
    async def download_file(self, url: str) -> Optional[BytesIO]:
        """Download file from URL"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    if len(data) <= Config.MAX_FILE_SIZE:
                        logger.info(f"✅ Downloaded file: {len(data)} bytes")
                        return BytesIO(data)
                    else:
                        logger.warning(f"File too large: {len(data)} bytes (max: {Config.MAX_FILE_SIZE})")
                        return None
                else:
                    logger.warning(f"Failed to download file, HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return None
    
    async def send_to_telegram(self, content: str, file_data: Optional[BytesIO] = None, 
                               filename: str = "file", is_image: bool = False):
        """Send message or file to Telegram channel"""
        try:
            if file_data:
                # Reset file pointer to beginning
                file_data.seek(0)
                
                if is_image:
                    # Send as photo
                    await self.telegram_bot.send_photo(
                        chat_id=Config.TELEGRAM_CHANNEL_ID,
                        photo=file_data,
                        caption=content[:1024] if content else None,  # Telegram caption limit
                        read_timeout=30,
                        write_timeout=30
                    )
                    logger.info(f"✅ Image sent to Telegram: {filename}")
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
                    logger.info(f"✅ File sent to Telegram: {filename}")
            else:
                # Send text only, split if too long
                if len(content) > 4096:
                    for i in range(0, len(content), 4096):
                        await self.telegram_bot.send_message(
                            chat_id=Config.TELEGRAM_CHANNEL_ID,
                            text=content[i:i+4096],
                            read_timeout=30
                        )
                    logger.info(f"✅ Long message sent to Telegram ({len(content)} chars)")
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
            logger.info(f"📎 Processing attachment: {attachment.filename} ({attachment.size} bytes)")
            
            # Download file
            file_data = await self.download_file(attachment.url)
            if not file_data:
                continue
            
            # Check if it's an image (by content type or extension)
            is_image = False
            if attachment.content_type:
                is_image = attachment.content_type.startswith('image/')
            else:
                # Check by extension
                image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
                is_image = any(attachment.filename.lower().endswith(ext) for ext in image_extensions)
            
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
            author_name += " 🤖"
        
        parts.append(f"**👤 {author_name}**")
        parts.append(f"📅 {message.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Message content
        if message.content:
            parts.append(f"\n💬 {message.content}")
        
        # Reply reference
        if message.reference and message.reference.resolved:
            replied_msg = message.reference.resolved
            parts.append(f"\n↪️ **Replying to:** {replied_msg.author.display_name}")
            if replied_msg.content:
                preview = replied_msg.content[:100] + "..." if len(replied_msg.content) > 100 else replied_msg.content
                parts.append(f"   💭 {preview}")
        
        # Embeds
        if message.embeds:
            for i, embed in enumerate(message.embeds):
                parts.append(f"\n📦 **Embed {i+1}:**")
                if embed.title:
                    parts.append(f"**{embed.title}**")
                if embed.description:
                    parts.append(embed.description[:500])  # Limit embed description
                if embed.url:
                    parts.append(f"🔗 {embed.url}")
                if embed.footer:
                    parts.append(f"📝 {embed.footer.text}")
        
        # Stickers
        if message.stickers:
            sticker_names = [f"🎨 {s.name}" for s in message.stickers]
            parts.append(f"\n{', '.join(sticker_names)}")
        
        # Join with newlines
        result = "\n".join(parts)
        
        # Add source footer (if there's room)
        footer = f"\n\n---\n🔄 Reposted from Discord | #{message.channel.name}"
        if len(result + footer) < 4096:
            result += footer
        
        return result
    
    async def on_discord_message(self, message: discord.Message):
        """Handle Discord messages and repost to Telegram"""
        
        # Ignore bot's own messages
        if message.author == self.discord_client.user:
            return
        
        # Check if message is from monitored channel
        if message.channel.id != Config.DISCORD_CHANNEL_ID:
            return
        
        logger.info(f"📨 New message from {message.author.display_name} in #{message.channel.name}")
        
        try:
            # Format message content
            formatted_content = await self.format_discord_message(message)
            
            # Process attachments
            attachments_data = await self.process_attachments(message.attachments)
            
            # Send to Telegram
            if attachments_data:
                # Send text first if present and not empty
                if formatted_content and formatted_content.strip():
                    await self.send_to_telegram(formatted_content)
                
                # Send each attachment
                for attachment in attachments_data:
                    await self.send_to_telegram(
                        content=f"📎 **{attachment['filename']}**",
                        file_data=attachment['data'],
                        filename=attachment['filename'],
                        is_image=attachment['is_image']
                    )
            else:
                # Send only text if present
                if formatted_content and formatted_content.strip():
                    await self.send_to_telegram(formatted_content)
                else:
                    logger.warning("Empty message, nothing to send")
                
        except Exception as e:
            logger.error(f"❌ Failed to process message: {e}")
            logger.error(traceback.format_exc())
    
    async def health_check(self):
        """Periodic health check"""
        while True:
            await asyncio.sleep(300)  # Every 5 minutes
            try:
                # Check Discord connection
                if self.discord_client and not self.discord_client.is_closed():
                    logger.debug("✅ Discord connection OK")
                else:
                    logger.warning("⚠️ Discord connection issue")
                
                # Check Telegram connection
                if self.telegram_bot:
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
