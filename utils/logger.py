import logging
import os
import discord
from discord.ext import commands

logger = logging.getLogger("EigenBot")

def setup_logging():
    log_level_str = os.getenv("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)

    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler(os.path.join("logs", "bot.log"), encoding="utf-8")
    stream_handler = logging.StreamHandler()

    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    logger.info("Logging system configured successfully.")

def log_command_usage(ctx_or_interaction, command_type: str, success: bool, error: Exception = None):
    """Formats and logs command usage consistently."""
    try:
        if isinstance(ctx_or_interaction, commands.Context):
            user_id = ctx_or_interaction.author.id
            username = ctx_or_interaction.author.name
            if ctx_or_interaction.command:
                command_name = ctx_or_interaction.command.qualified_name
            else:
                command_name = "Unknown"
        elif isinstance(ctx_or_interaction, discord.Interaction):
            user_id = ctx_or_interaction.user.id
            username = ctx_or_interaction.user.name
            if ctx_or_interaction.command:
                command_name = ctx_or_interaction.command.qualified_name
            elif ctx_or_interaction.data:
                command_name = ctx_or_interaction.data.get("name", "Unknown")
            else:
                command_name = "Unknown"
        else:
            return

        status = "SUCCESS" if success else f"FAILED ({type(error).__name__}: {error})"
        message = (
            f"[{command_type}] User: {username} ({user_id}) | "
            f"Command: {command_name} | Status: {status}"
        )

        if success:
            logger.info(message)
        else:
            logger.error(message)
    except Exception as log_err:
        logger.error(f"Failed to write command log: {log_err}")
