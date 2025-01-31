import os
from typing import Dict, Any
from ..utils.utils import create_app_directory_structure, get_config_path, save_config, load_config
from ..core.config import DEFAULT_CONFIG, Config
from ..utils.logger import log

class MigrationManager:
    """Manages configuration migrations between versions."""
    
    def __init__(self):
        log.debug("🔍 MigrationManager initialized")
        self._config = Config()

    def check_and_migrate(self) -> Dict[str, Any]:
        """Check if migrations are needed and apply them."""
        results = {
            "migrations_performed": [],
            "needs_restart": False
        }
        
        try:
            # Load current config
            config = load_config()
            
            # Add API configuration if missing
            if "api" not in config:
                config["api"] = {
                    "openai": None,
                    "anthropic": None,
                    "groq": None
                }
                results["migrations_performed"].append("Added API configuration structure")
                # Save with API structure preserved
                save_config(config, include_api_keys=True)
                
            # Save final migrated config
            if results["migrations_performed"]:
                log.debug("Saving migrated config...")
                save_config(config, include_api_keys=True)
                
            return results
            
        except Exception as e:
            log.error(f"Error during migration: {e}")
            return results

    def _migrate_whisper_config(self) -> bool:
        """Migrate Whisper configuration to include cloud fallback settings.
        
        Returns:
            bool: True if migration was performed, False otherwise
        """
        needs_save = False
        
        # Check if transcription section exists
        if "transcription" not in self._config.config:
            log.debug("Transcription section missing from config, adding it")
            self._config.config["transcription"] = DEFAULT_CONFIG["transcription"].copy()
            needs_save = True
            return needs_save

        # Check if whisper section exists
        if "whisper" not in self._config.config["transcription"]:
            log.debug("Whisper section missing from config, adding it")
            self._config.config["transcription"]["whisper"] = DEFAULT_CONFIG["transcription"]["whisper"].copy()
            needs_save = True
            return needs_save

        # Check for new cloud settings
        whisper_config = self._config.config["transcription"]["whisper"]
        if "use_cloud_fallback" not in whisper_config:
            log.debug("Adding Whisper cloud fallback setting")
            whisper_config["use_cloud_fallback"] = DEFAULT_CONFIG["transcription"]["whisper"]["use_cloud_fallback"]
            needs_save = True

        if "cloud_model" not in whisper_config:
            log.debug("Adding Whisper cloud model setting")
            whisper_config["cloud_model"] = DEFAULT_CONFIG["transcription"]["whisper"]["cloud_model"]
            needs_save = True
            
        return needs_save

    def _migrate_api_config(self) -> bool:
        """Ensure API configuration structure exists with null values.
        Does not copy environment variables to config.
        
        Returns:
            bool: True if migration was performed, False otherwise
        """
        needs_save = False
        
        # Check if api section exists, if not add it
        if "api" not in self._config.config:
            log.debug("API section missing from config, adding it with null values")
            self._config.config["api"] = {
                "openai": None,
                "anthropic": None,
                "groq": None
            }
            needs_save = True
            return needs_save
            
        # Ensure all expected API fields exist with null values if not present
        for service in ["openai", "anthropic", "groq"]:
            if service not in self._config.config["api"]:
                log.debug(f"Adding null {service} API key field to config")
                self._config.config["api"][service] = None
                needs_save = True
                
        return needs_save 
