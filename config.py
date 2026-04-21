import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Bot configuration"""
    
    # Discord configuration
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    DISCORD_CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID', 0))
    
    # Telegram configuration
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # File handling
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', 20)) * 1024 * 1024  # Convert MB to bytes
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        
        if not cls.DISCORD_TOKEN:
            errors.append("DISCORD_TOKEN is missing")
        if not cls.DISCORD_CHANNEL_ID:
            errors.append("DISCORD_CHANNEL_ID is missing")
        if not cls.TELEGRAM_TOKEN:
            errors.append("TELEGRAM_TOKEN is missing")
        if not cls.TELEGRAM_CHANNEL_ID:
            errors.append("TELEGRAM_CHANNEL_ID is missing")
            
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True