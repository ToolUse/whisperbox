#!/usr/bin/env python
import argparse
import subprocess
import os
import time
import pyaudio
import wave
import traceback
from pydub import AudioSegment
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import box
import select
import sys
from .ai_service import AIService
from urllib.request import urlretrieve
from ..core.config import config, DEFAULT_CONFIG
from ..audio.audio import AudioRecorder, convert_to_wav
from ..utils.logger import log
from ..utils.utils import get_models_dir, get_app_dir
import platform
import ssl

console = Console()

# Get model name from config, with fallback to tiny.en
OLLAMA_MODEL = config.ai.default_model
DEFAULT_WHISPER_MODEL = config.get_with_retry("transcription", "whisper", "model")
WHISPER_BASE_URL = config.transcription.whisper.base_url

ASCII_ART = """
WhisperBox
"""


def check_ffmpeg():
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        log.error("Error: FFmpeg is not installed.")
        log.warning("Please install FFmpeg using:")
        log.info("  brew install ffmpeg")
        return False


def install_whisper_model(model_name, whisperfile_path):
    import ssl
    import certifi
    from urllib.request import urlopen

    full_model_name = f"whisper-{model_name}.llamafile"
    url = f"{WHISPER_BASE_URL}{full_model_name}"
    output_path = os.path.join(whisperfile_path, full_model_name)

    # Create the directory if it doesn't exist
    os.makedirs(whisperfile_path, exist_ok=True)

    log.info(f"Downloading {full_model_name}...")
    log.debug(f"Download URL: {url}")

    # Create a progress bar
    progress = console.status("[bold green]Downloading...", spinner="dots")
    progress.start()

    def download_with_progress(response, output_path):
        # Get file size for progress tracking
        file_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        # Read the content in chunks and write to file
        with open(output_path, 'wb') as f:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                downloaded += len(chunk)
                f.write(chunk)
                
                # Update progress message with percentage
                if file_size:
                    percent = (downloaded / file_size) * 100
                    progress.update(f"[bold green]Downloading... {percent:.1f}%")

    try:
        # First try with SSL verification
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        
        # On macOS, also try to use system certificates
        if platform.system() == 'Darwin':
            try:
                ssl_context.load_verify_locations(cafile='/etc/ssl/cert.pem')
            except Exception as e:
                log.debug(f"Could not load macOS system certificates: {e}")

        # Use urllib.request with the SSL context
        with urlopen(url, context=ssl_context) as response:
            download_with_progress(response, output_path)
            
        progress.stop()
        os.chmod(output_path, 0o755)
        log.success(f"{full_model_name} installed successfully.")
        
    except Exception as e:
        log.warning(f"Secure download failed: {str(e)}")
        log.warning("Attempting download without SSL verification...")
        
        try:
            # Create an unverified context
            ssl_context = ssl._create_unverified_context()
            
            with urlopen(url, context=ssl_context) as response:
                download_with_progress(response, output_path)
                
            progress.stop()
            os.chmod(output_path, 0o755)
            log.success(f"{full_model_name} installed successfully (without SSL verification).")
            log.warning("Note: Download was completed without SSL verification. This is less secure.")
            
        except Exception as e:
            progress.stop()
            log.error(f"Error downloading model: {str(e)}")
            raise


def get_whisper_model_path(model_name, whisperfile_path, verbose):
    """Get the path to the Whisper model, downloading if necessary.
    
    Returns:
        str: Path to the model file if successful, None if failed
    """
    try:
        full_model_name = f"whisper-{model_name}.llamafile"
        # Expand user path if necessary
        whisperfile_path = os.path.expanduser(whisperfile_path)
        model_path = os.path.join(whisperfile_path, full_model_name)

        log.debug(f"Looking for Whisper model at: {model_path}")

        if not os.path.exists(model_path):
            log.warning(f"Whisper model {full_model_name} not found.")
            log.warning(f"Would you like to download it from {WHISPER_BASE_URL}?")

            if input("Download model? (y/n): ").lower() == "y":
                try:
                    install_whisper_model(model_name, whisperfile_path)
                except Exception as e:
                    log.error(f"Failed to download model: {str(e)}")
                    return None
            else:
                log.warning("Model download declined by user")
                return None

        log.debug(f"Found Whisper model at: {model_path}")

        # Check if the file is executable
        if not os.access(model_path, os.X_OK):
            try:
                log.warning("Making model file executable...")
                os.chmod(model_path, 0o755)
            except Exception as e:
                log.error(f"Failed to make model executable: {str(e)}")
                return None

        return model_path

    except Exception as e:
        log.error(f"Error in get_whisper_model_path: {str(e)}")
        log.debug(traceback.format_exc())
        return None


def transcribe_audio(model_name, whisperfile_path, audio_file, verbose):
    """Transcribe audio using local Whisper model with cloud fallback."""
    try:
        if not model_name:
            model_name = config.get_with_retry("transcription", "whisper", "model")
            log.debug(f"Using default model: {model_name}")
            
        if not model_name:
            from ..core.config import DEFAULT_CONFIG
            default_model = DEFAULT_CONFIG["transcription"]["whisper"]["model"]
            log.warning(f"Could not get model from config after retries, using default: {default_model}")
            model_name = default_model
            
        log.debug(f"Final model name for transcription: {model_name}")
        
        # First try local transcription
        try:
            # Check if file exists and is readable first
            if not os.path.exists(audio_file):
                log.error(f"Audio file not found: {audio_file}")
                return None

            model_path = get_whisper_model_path(model_name, whisperfile_path, verbose)
            if not model_path:
                log.warning("Could not get Whisper model path, trying cloud fallback...")
                raise Exception("No valid model path")

            gpu_flag = "--gpu auto" if config.transcription.whisper.gpu_enabled else ""
            command = f"{model_path} -f {audio_file} {gpu_flag}"

            if verbose:
                log.debug(f"Attempting to run command: {command}")

            log.debug("Running transcription command...")

            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            stdout, stderr = process.communicate()

            if process.returncode != 0:
                log.error(f"Command failed with return code {process.returncode}")
                log.error(f"Error output: {stderr}")
                raise Exception("Local transcription failed")

            if not stdout.strip():
                log.warning("Local transcription produced empty output")
                raise Exception("Empty output")

            log.debug("Local transcription output:")
            log.debug(stdout)

            return stdout.strip()

        except Exception as local_error:
            log.warning(f"Local transcription failed: {str(local_error)}")
            
            # Check if cloud fallback is enabled
            if config.transcription.whisper.use_cloud_fallback:
                log.info("Local transcription failed, trying cloud Whisper API...")
                
                # Ask user if they want to try cloud transcription
                if input("Try again with cloud Whisper? (y/n): ").lower() == 'y':
                    # Get OpenAI API key
                    api_key = config.get_api_key("openai")
                    
                    # If no API key, prompt for it
                    if not api_key:
                        log.warning("OpenAI API key not found in config")
                        api_key = input("Enter your OpenAI API key: ").strip()
                        if api_key:
                            # Save the API key to config
                            config.set_api_key("openai", api_key)
                            log.success("API key saved to config")
                        else:
                            log.error("No API key provided")
                            return None
                    
                    try:
                        from openai import OpenAI
                        client = OpenAI(api_key=api_key)
                        
                        log.info("Uploading audio to OpenAI Whisper API...")
                        with open(audio_file, "rb") as audio:
                            response = client.audio.transcriptions.create(
                                model=config.transcription.whisper.cloud_model,
                                file=audio,
                                response_format="text"
                            )
                        
                        if not response:
                            log.error("Cloud transcription returned empty response")
                            return None
                            
                        log.success("Cloud transcription successful!")
                        return str(response)
                        
                    except Exception as cloud_error:
                        log.error(f"Cloud transcription failed: {str(cloud_error)}")
                        return None
                else:
                    log.warning("Cloud transcription declined by user")
                    return None
            else:
                log.warning("Cloud fallback is disabled")
                return None

    except Exception as e:
        log.error(f"Error in transcribe_audio: {str(e)}")
        log.debug(traceback.format_exc())
        return None


def summarize(text):
    ai_service = AIService()
    prompt = config.ai.prompts.summary.format(text=text)
    return ai_service.query(prompt)


def analyze_sentiment(text):
    ai_service = AIService()
    prompt = config.ai.prompts.sentiment.format(text=text)
    sentiment = ai_service.query(prompt).strip().lower()
    return sentiment if sentiment in ["positive", "neutral", "negative"] else "neutral"


def detect_intent(text):
    ai_service = AIService()
    prompt = config.ai.prompts.intent.format(text=text)
    return ai_service.query(prompt)


def detect_topics(text):
    ai_service = AIService()
    prompt = config.ai.prompts.topics.format(text=text)
    return ai_service.query(prompt)


def export_to_markdown(text, session_dir):
    """Export transcription text to a markdown file in the session directory.

    Args:
        text (str): The transcription text
        session_dir (str): Path to the session directory
    """
    file_path = os.path.join(session_dir, "whisper_transcript.md")

    with open(file_path, "w") as f:
        f.write("# Raw Whisper Transcription\n\n")
        f.write(text)

    log.save(f"Raw transcription saved to {file_path}")


def get_sentiment_color(sentiment):
    return {"positive": "green3", "neutral": "gold1", "negative": "red1"}.get(
        sentiment, "white"
    )


class Shallowgram:
    def __init__(self, whisperfile_path=None):
        self.whisperfile_path = whisperfile_path or get_models_dir()
        self.ai_service = AIService()

    def transcribe(self, audio_file, model=DEFAULT_WHISPER_MODEL, full_analysis=False):
        log.debug(f"using file {audio_file}")
        if not os.path.exists(audio_file):
            raise FileNotFoundError(f"Audio file not found: {audio_file}")

        # Ensure we have a valid model
        if not model:
            from ..core.config import DEFAULT_CONFIG
            default_model = DEFAULT_CONFIG["transcription"]["whisper"]["model"]
            log.warning(f"No model specified, using default: {default_model}")
            model = default_model
            # Update config with default model
            if "transcription" not in config._config:
                config._config["transcription"] = {}
            if "whisper" not in config._config["transcription"]:
                config._config["transcription"]["whisper"] = {}
            config._config["transcription"]["whisper"]["model"] = model
            config.save()
            log.debug(f"Updated config with default model: {model}")

        # Convert to wav if needed
        file_ext = os.path.splitext(audio_file)[1].lower()
        if file_ext != ".wav":
            log.info("Converting audio to WAV format...")
            wav_file = "temp_audio.wav"
            convert_to_wav(audio_file, wav_file)
            audio_file = wav_file

        try:
            log.info("Running Whisper transcription...")
            transcript = transcribe_audio(
                model, self.whisperfile_path, audio_file, True
            )  # Set verbose=True

            if not transcript:
                log.error("Whisper returned empty transcript")
                return None

            return {"text": transcript}

        except Exception as e:
            log.error(f"Error in transcription: {str(e)}")
            raise
        finally:
            # Cleanup temporary file
            if file_ext != ".wav" and os.path.exists("temp_audio.wav"):
                os.remove("temp_audio.wav")
