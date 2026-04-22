import asyncio
import discord
from telegram import Bot as TelegramBot
from telegram.error import TelegramError
import aiohttp
from io import BytesIO
import traceback
import re
from typing import Optional
import mimetypes

from config import Config
from logger import setup_logger

# Setup logger
logger = setup_logger("DiscordTelegramBot", Config.LOG_LEVEL)

class DiscordTelegramReposter:
    """Advanced Discord to Telegram reposter bot - Full File Support"""
    
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
        """Download any file from URL"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    if len(data) <= Config.MAX_FILE_SIZE:
                        logger.info(f"✅ Downloaded file: {len(data)} bytes")
                        return BytesIO(data)
                    else:
                        logger.warning(f"File too large: {len(data)} bytes (Max: {Config.MAX_FILE_SIZE})")
                        return None
                else:
                    logger.warning(f"Failed to download file, HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Failed to download file: {e}")
            return None
    
    def get_file_type(self, filename: str, content_type: str = None) -> str:
        """Determine file type for better handling"""
        filename_lower = filename.lower()
        
        # Video files
        video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v', '.3gp']
        if any(filename_lower.endswith(ext) for ext in video_extensions):
            return 'video'
        
        # Audio files
        audio_extensions = ['.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac', '.wma']
        if any(filename_lower.endswith(ext) for ext in audio_extensions):
            return 'audio'
        
        # Image files
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.ico', '.svg']
        if any(filename_lower.endswith(ext) for ext in image_extensions):
            return 'image'
        
        # Document files
        document_extensions = ['.pdf', '.doc', '.docx', '.txt', '.rtf', '.odt']
        if any(filename_lower.endswith(ext) for ext in document_extensions):
            return 'document'
        
        # Archive files
        archive_extensions = ['.zip', '.rar', '.7z', '.tar', '.gz', '.bz2']
        if any(filename_lower.endswith(ext) for ext in archive_extensions):
            return 'archive'
        
        # Executable files
        executable_extensions = ['.exe', '.msi', '.bat', '.sh', '.app', '.deb', '.rpm']
        if any(filename_lower.endswith(ext) for ext in executable_extensions):
            return 'executable'
        
        # APK files
        if filename_lower.endswith('.apk'):
            return 'apk'
        
        # Default
        return 'other'
    
    async def send_file_to_telegram(self, file_data: BytesIO, filename: str, 
                                   content_type: str = None, caption: str = None):
        """Send any file to Telegram with appropriate method"""
        try:
            # Reset file pointer to beginning
            file_data.seek(0)
            
            file_type = self.get_file_type(filename, content_type)
            logger.info(f"📤 Sending {file_type} file: {filename}")
            
            # For videos - use send_video
            if file_type == 'video':
                await self.telegram_bot.send_video(
                    chat_id=Config.TELEGRAM_CHANNEL_ID,
                    video=file_data,
                    caption=caption[:1024] if caption else None,
                    filename=filename,
                    supports_streaming=True,
                    read_timeout=60,
                    write_timeout=60
                )
            
            # For audio - use send_audio
            elif file_type == 'audio':
                await self.telegram_bot.send_audio(
                    chat_id=Config.TELEGRAM_CHANNEL_ID,
                    audio=file_data,
                    caption=caption[:1024] if caption else None,
                    filename=filename,
                    read_timeout=60,
                    write_timeout=60
                )
            
            # For images - use send_photo
            elif file_type == 'image':
                await self.telegram_bot.send_photo(
                    chat_id=Config.TELEGRAM_CHANNEL_ID,
                    photo=file_data,
                    caption=caption[:1024] if caption else None,
                    read_timeout=60,
                    write_timeout=60
                )
            
            # For documents (PDF, DOC, TXT, APK, EXE, ZIP, etc.) - use send_document
            else:
                await self.telegram_bot.send_document(
                    chat_id=Config.TELEGRAM_CHANNEL_ID,
                    document=file_data,
                    filename=filename,
                    caption=caption[:1024] if caption else None,
                    read_timeout=60,
                    write_timeout=60
                )
            
            logger.info(f"✅ File sent to Telegram: {filename}")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Telegram error for {filename}: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error for {filename}: {e}")
            return False
    
    async def send_text_to_telegram(self, text: str):
        """Send text message to Telegram"""
        try:
            # Split if too long
            if len(text) > 4096:
                for i in range(0, len(text), 4096):
                    await self.telegram_bot.send_message(
                        chat_id=Config.TELEGRAM_CHANNEL_ID,
                        text=text[i:i+4096],
                        read_timeout=30
                    )
                logger.info(f"✅ Long text sent to Telegram ({len(text)} chars)")
            else:
                await self.telegram_bot.send_message(
                    chat_id=Config.TELEGRAM_CHANNEL_ID,
                    text=text,
                    read_timeout=30
                )
                logger.info(f"✅ Text sent to Telegram")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Telegram error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
            return False
    
    async def process_attachments(self, attachments) -> list:
        """Process all Discord attachments"""
        results = []
        
        for attachment in attachments:
            logger.info(f"📎 Processing: {attachment.filename} ({attachment.size} bytes)")
            
            # Download file
            file_data = await self.download_file(attachment.url)
            if file_data:
                results.append({
                    'data': file_data,
                    'filename': attachment.filename,
                    'content_type': attachment.content_type
                })
            else:
                logger.warning(f"❌ Failed to process {attachment.filename}")
        
        return results
    
    async def on_discord_message(self, message):
        """Handle Discord messages and repost to Telegram - FULL FILE SUPPORT"""
        
        # Ignore bot's own messages
        if message.author == self.discord_client.user:
            return
        
        # Check if message is from monitored channel
        if message.channel.id != Config.DISCORD_CHANNEL_ID:
            return
        
        logger.info(f"📨 New message from {message.author.display_name}")
        
        try:
            # Get the message content exactly as is (no extra formatting)
            message_text = message.content.strip() if message.content else ""
            
            # Process ALL attachments (videos, images, files, etc.)
            attachments_data = await self.process_attachments(message.attachments)
            
            # Case 1: Message has files/attachments
            if attachments_data:
                # Send first file with message text as caption
                for i, attachment in enumerate(attachments_data):
                    if i == 0 and message_text:
                        # First file - send with caption
                        await self.send_file_to_telegram(
                            file_data=attachment['data'],
                            filename=attachment['filename'],
                            content_type=attachment['content_type'],
                            caption=message_text
                        )
                    else:
                        # Additional files - send without caption (or with file name)
                        await self.send_file_to_telegram(
                            file_data=attachment['data'],
                            filename=attachment['filename'],
                            content_type=attachment['content_type'],
                            caption=None
                        )
            
            # Case 2: No files, just text
            elif message_text:
                await self.send_text_to_telegram(message_text)
            
            # Case 3: Empty message (shouldn't happen)
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
                if self.discord_client and not self.discord_client.is_closed():
                    logger.debug("✅ Discord connection OK")
                
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
