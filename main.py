import asyncio
import discord
from telegram import Bot as TelegramBot
from telegram.error import TelegramError
import aiohttp
from io import BytesIO
import traceback
import re
from typing import Optional  # ← This was missing!

from config import Config
from logger import setup_logger

# Setup logger
logger = setup_logger("DiscordTelegramBot", Config.LOG_LEVEL)

class DiscordTelegramReposter:
    """Advanced Discord to Telegram reposter bot - Clean Version"""
    
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
    
    async def download_image(self, url: str) -> Optional[BytesIO]:
        """Download image from URL"""
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.read()
                    if len(data) <= Config.MAX_FILE_SIZE:
                        logger.info(f"✅ Downloaded image: {len(data)} bytes")
                        return BytesIO(data)
                    else:
                        logger.warning(f"Image too large: {len(data)} bytes")
                        return None
                else:
                    logger.warning(f"Failed to download image, HTTP {response.status}")
                    return None
        except Exception as e:
            logger.error(f"Failed to download image: {e}")
            return None
    
    async def send_image_to_telegram(self, image_data: BytesIO, caption: str = None):
        """Send image to Telegram with caption"""
        try:
            # Reset file pointer to beginning
            image_data.seek(0)
            
            # Send photo with caption (if any)
            await self.telegram_bot.send_photo(
                chat_id=Config.TELEGRAM_CHANNEL_ID,
                photo=image_data,
                caption=caption[:1024] if caption else None,  # Telegram caption limit
                read_timeout=30,
                write_timeout=30
            )
            logger.info(f"✅ Image sent to Telegram with caption: {caption[:50] if caption else 'No caption'}")
            return True
            
        except TelegramError as e:
            logger.error(f"❌ Telegram error: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Unexpected error: {e}")
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
    
    async def process_image_attachments(self, attachments) -> list:
        """Process Discord image attachments"""
        results = []
        
        for attachment in attachments:
            # Check if it's an image
            is_image = False
            if attachment.content_type:
                is_image = attachment.content_type.startswith('image/')
            else:
                # Check by extension
                image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']
                is_image = any(attachment.filename.lower().endswith(ext) for ext in image_extensions)
            
            if is_image:
                logger.info(f"📸 Found image: {attachment.filename}")
                image_data = await self.download_image(attachment.url)
                if image_data:
                    results.append(image_data)
        
        return results
    
    async def on_discord_message(self, message):
        """Handle Discord messages and repost to Telegram - CLEAN VERSION"""
        
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
            
            # Process image attachments
            image_files = await self.process_image_attachments(message.attachments)
            
            # Case 1: Message has images
            if image_files:
                # For each image, send with the message text as caption
                for i, image_data in enumerate(image_files):
                    # Send first image with full caption
                    if i == 0 and message_text:
                        await self.send_image_to_telegram(image_data, message_text)
                    else:
                        # Additional images without caption
                        await self.send_image_to_telegram(image_data, None)
            
            # Case 2: No images, just text
            elif message_text:
                await self.send_text_to_telegram(message_text)
            
            # Case 3: No content and no images
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
