import os
from typing import Dict, Any
from ..utils.utils import create_app_directory_structure, get_config_path, save_config
from ..core.config import DEFAULT_CONFIG, Config
from ..utils.logger import log

class MigrationManager:
    """Manages configuration migrations between versions."""
    
    def __init__(self):
        log.debug("🔍 MigrationManager initialized")

    def check_and_migrate(self) -> Dict[str, Any]:
        """Check for and perform any necessary migrations."""
        log.debug("🔍 Starting migration checks...")
        
        # First ensure app directory exists
        try:
            create_app_directory_structure()
        except Exception as e:
            log.error(f"Failed to create app directory structure: {e}")
            return {"migrations_performed": [], "needs_restart": False}

        # Check if config exists, if not create it
        config_path = get_config_path()
        if not os.path.exists(config_path):
            try:
                # Start with default config
                initial_config = DEFAULT_CONFIG.copy()
                save_config(initial_config)
                log.debug("Created initial config file")
            except Exception as e:
                log.error(f"Failed to create initial config: {e}")
                return {"migrations_performed": [], "needs_restart": False}

        migrations_performed = []
        needs_restart = False

        # Now proceed with migrations
        log.debug("🔍 Checking API configuration...")
        
        # Check for API keys in environment variables
        api_keys = {
            'openai': 'OPENAI_API_KEY',
            'anthropic': 'ANTHROPIC_API_KEY',
            'groq': 'GROQ_API_KEY'
        }
        
        # Create config instance after ensuring file exists
        config = Config()
        
        for provider, env_var in api_keys.items():
            api_key = os.environ.get(env_var)
            log.debug(f"🔍 Checking {provider} API key... (exists in env: {api_key is not None})")
            
            if api_key:
                try:
                    log.debug(f"🔍 Migrating {provider} API key from environment")
                    config.set_api_key(provider, api_key)
                    migrations_performed.append(f"Migrated {provider} API key from environment variable")
                except Exception as e:
                    log.error(f"Failed to migrate {provider} API key: {e}")

        if migrations_performed:
            try:
                log.debug("🔍 Saving updated config with API keys")
                config.save(include_api_keys=True)
            except Exception as e:
                log.error(f"Failed to save config: {e}")
        
        return {
            "migrations_performed": migrations_performed,
            "needs_restart": needs_restart
        }     
    def _migrate_api_config(self) -> bool:
        """Migrate API configuration from environment variables to config file.
        
        Returns:
            bool: True if migration was performed, False otherwise
        """
        needs_save = False
        
        # Check if api section exists, if not add it
        if "api" not in self._config.config:
            log.debug("API section missing from config, adding it")
            self._config.config["api"] = DEFAULT_CONFIG["api"].copy()
            needs_save = True
            
        # Migrate any existing API keys from env vars if they exist
        for service in ["openai", "anthropic", "groq"]:
            env_key = f"{service.upper()}_API_KEY"
            env_value = os.getenv(env_key)
            log.debug(f"Checking {service} API key... (exists in env: {env_value is not None})")
            if env_value and not self._config.config["api"].get(service):
                log.debug(f"Migrating {service} API key from environment")
                self._config.config["api"][service] = env_value
                needs_save = True
        
        if needs_save:
            log.debug("Saving updated config with API keys")
            self._config.save(include_api_keys=True)
            
        return needs_save 
