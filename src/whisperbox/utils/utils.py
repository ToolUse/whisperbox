import os
import yaml
from pathlib import Path
from typing import Dict, Any, Union
import platform
import subprocess
from datetime import datetime

# Application name - this will be used for the app directory
APP_NAME = "WhisperBox"


def get_app_dir() -> Path:
    """Get the application directory in the user's Documents folder."""
    documents_dir = Path.home() / "Documents"
    return documents_dir / APP_NAME


def get_config_path() -> Path:
    """Get the path to the config file."""
    return get_app_dir() / "config.yaml"


def get_data_dir() -> Path:
    """Get the meetings directory path."""
    return get_app_dir() / "data"


def get_models_dir() -> Path:
    """Get the models directory path."""
    return get_app_dir() / "models"


def get_profiles_dir() -> Path:
    """Get the profiles directory path."""
    return get_app_dir() / "profiles"


def create_session_dir() -> Path:
    """Create a new directory for a meeting session.

    Returns:
        Path: Path to the created session directory
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    session_dir = get_data_dir() / timestamp
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def is_first_run() -> bool:
    """Check if this is the first time the app is being run."""
    return not get_config_path().exists()


def create_app_directory_structure() -> None:
    """Create the application directory structure."""
    # Create main app directory in Documents
    app_dir = get_app_dir()
    app_dir.mkdir(exist_ok=True, parents=True)

    # Create main subdirectories
    get_data_dir().mkdir(exist_ok=True)
    get_models_dir().mkdir(exist_ok=True)
    get_profiles_dir().mkdir(exist_ok=True)


def save_config(config: Dict[str, Any], include_api_keys: bool = False) -> None:
    """Save configuration to YAML file."""
    config_path = get_config_path()
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    
    # Create a copy to avoid modifying the original
    safe_config = config.copy()
    
    # Add debug logging right before writing
    
    with open(config_path, 'w') as f:
        yaml.safe_dump(safe_config, f, default_flow_style=False)


def load_config() -> Dict[str, Any]:
    """Load configuration from the config file."""
    config_path = get_config_path()
    if config_path.exists():
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def reveal_in_file_manager(path: Union[str, Path]):
    """Reveal the file in the system's file manager (Finder/Explorer/etc)."""
    path = str(path)

    if platform.system() == "Darwin":  # macOS
        # Use AppleScript to reveal in Finder
        subprocess.run(
            [
                "osascript",
                "-e",
                f'tell application "Finder" to reveal POSIX file "{path}"',
            ]
        )
        subprocess.run(["osascript", "-e", 'tell application "Finder" to activate'])
    elif platform.system() == "Windows":
        # Windows Explorer's select functionality
        subprocess.run(["explorer", "/select,", path])
    else:  # Linux
        # Most file managers support showing containing folder
        folder_path = os.path.dirname(path)
        try:
            subprocess.run(["xdg-open", folder_path])
        except FileNotFoundError:
            # Fallback for systems without xdg-open
            subprocess.run(["gio", "open", folder_path])


def get_transcript_path(audio_file_path: str | None) -> str | None:
    """Get the path to the transcript.md file in the same directory as the audio file.

    Args:
        audio_file_path (str | None): Path to the audio file (e.g. recording.wav)

    Returns:
        str | None: Path to the transcript.md file as string, or None if audio_file_path is None
    """
    if not audio_file_path:
        return None

    audio_path = Path(audio_file_path)
    transcript_path = audio_path.parent / "transcript.md"

    if not transcript_path.exists():
        # Import log here to avoid circular import
        from ..utils.logger import log
        log.warning(f"Transcript file not found at: {transcript_path}")

    return str(transcript_path)
