import os
import tempfile
from typing import Dict, Any, Optional
from ..utils.utils import (
    get_config_path,
    get_models_dir,
    save_config,
    load_config,
    get_data_dir,
)

DEFAULT_CONFIG = {
    "ai": {"default_provider": "ollama", "default_model": "llama3.2"},
    "api": {
        "openai": None,
        "anthropic": None,
        "groq": None,
    },
    "audio": {
        "format": "wav",
        "channels": 2,
        "sample_rate": 48000,
        "chunk_size": 1024,
        "capture_system_audio": True,
        "devices": {
            "microphone": {
                "name": None,
                "index": None,
                "channels": None,
                "sample_rate": None,
                "input_latency": None,
                "is_default": None
            },
            "system": {
                "name": None,
                "index": None,
                "channels": None,
                "sample_rate": None
            }
        }
    },
    "output": {
        "default_profile": "meeting_summary",
        "data_directory": str(get_data_dir()),
        "timestamp_format": "%Y-%m-%d_%H-%M-%S",
        "save_audio": True,
        "file_format": "md",
    },
    "transcription": {
        "whisper": {
            "models_path": str(get_models_dir()),
            "base_url": "https://huggingface.co/Mozilla/whisperfile/resolve/main/",
            "gpu_enabled": True,
            "use_cloud_fallback": True,
            "cloud_model": "whisper-1",
        }
    },
    "system": {
        "temp_directory": os.path.join(tempfile.gettempdir(), "whisperbox"),
        "debug_mode": False
    },
}


class Config:
    def __init__(self):
        """Initialize configuration from YAML file."""
        self._config_path = get_config_path()
        self._config = self._load_config()

    def _load_config(self):
        """Load configuration from file or create default."""
        if os.path.exists(self._config_path):
            return load_config()
        return DEFAULT_CONFIG.copy()

    def reload(self):
        """Reload configuration from file."""
        self._config = self._load_config()

    def get_with_retry(self, *keys, max_attempts=3):
        """Get a config value with retries if None is found.
        
        Args:
            *keys: The keys to traverse in the config dict
            max_attempts: Maximum number of reload attempts
        """
        value = self._config
        for key in keys:
            if not isinstance(value, dict):
                return None
            value = value.get(key)
            if value is None:
                # If we hit a None, try reloading
                for _ in range(max_attempts):
                    self.reload()
                    # Try getting the value again
                    temp_value = self._config
                    for k in keys:
                        if not isinstance(temp_value, dict):
                            break
                        temp_value = temp_value.get(k)
                        if temp_value is None:
                            break
                    if temp_value is not None:
                        return temp_value
                # If we still got None after all attempts, use default
                temp_value = DEFAULT_CONFIG
                for k in keys:
                    if not isinstance(temp_value, dict):
                        return None
                    temp_value = temp_value.get(k)
                return temp_value
        return value

    def save(self, include_api_keys: bool = False) -> None:
        """Save current configuration to file.
        
        Args:
            include_api_keys (bool): If True, API keys will be saved to the config file.
                                   Use with caution as this saves sensitive data.
        """
        # Create a copy of config
        safe_config = self._config.copy()
        
        # Only remove API keys if we're not explicitly including them
        if not include_api_keys and "api" in safe_config:
            del safe_config["api"]  # Never save API keys to file unless explicitly requested
            
        save_config(safe_config)

    def get_api_key(self, service: str) -> Optional[str]:
        """Get API key for the specified service.
        First checks config file, then falls back to environment variables.

        Args:
            service (str): Service name (openai, anthropic, groq)

        Returns:
            Optional[str]: API key if found, None otherwise
        """
        # First try to get from config
        if api_key := self._config.get("api", {}).get(service):
            return api_key
            
        # Fall back to environment variables
        env_var_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "groq": "GROQ_API_KEY",
        }
        
        if env_var := env_var_map.get(service):
            return os.getenv(env_var)
        return None

    def set_api_key(self, service: str, key: str) -> None:
        """Set API key for the specified service.

        Args:
            service (str): Service name (openai, anthropic, groq)
            key (str): API key value
        """
        if "api" not in self._config:
            self._config["api"] = {}
        self._config["api"][service] = key
        self.save()

    @property
    def api(self):
        """Access API settings."""
        return ConfigSection(self._config.get("api", {}))

    @property
    def ai(self):
        """Access AI settings."""
        return ConfigSection(self._config.get("ai", {}))

    @property
    def audio(self):
        """Access audio recording settings."""
        return ConfigSection(self._config.get("audio", {}))

    @property
    def transcription(self):
        """Access transcription settings."""
        return ConfigSection(self._config.get("transcription", {}))

    @property
    def output(self):
        """Access output settings."""
        return ConfigSection(self._config.get("output", {}))

    @property
    def display(self):
        """Access display settings."""
        return ConfigSection(self._config.get("display", {}))

    @property
    def system(self):
        """Access system settings."""
        return ConfigSection(self._config.get("system", {}))

    @property
    def commands(self):
        """Access command settings."""
        return ConfigSection(self._config.get("commands", {}))

    @property
    def config(self):
        """Get the raw config dictionary."""
        return self._config


class ConfigSection:
    """Helper class to provide dot notation access to config sections."""

    def __init__(self, section_dict: Dict[str, Any]):
        self._section = section_dict

    def __getattr__(self, key: str) -> Any:
        if key not in self._section:
            return None
        value = self._section[key]
        if isinstance(value, dict):
            return ConfigSection(value)
        return value

    def __getitem__(self, key: str) -> Any:
        """Support dictionary-style access."""
        return self._section[key]

    def __contains__(self, key: str) -> bool:
        """Support 'in' operator."""
        return key in self._section

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value with a default."""
        return self._section.get(key, default)

    def items(self):
        """Make the config section iterable like a dict."""
        return self._section.items()


# Create a global config instance
config = Config()
