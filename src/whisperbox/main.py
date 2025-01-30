import os
import time
import logging
import argparse
from threading import Thread
from .core.config import config
from .core.migration import MigrationManager
from .audio.recording_manager import RecordingManager
from .utils.logger import log
from .core.setup import setup
from .audio.audio import list_audio_devices
from .utils.utils import (
    is_first_run,
    get_transcript_path,
    get_app_dir,
    reveal_in_file_manager,
)
from .utils.model_utils import check_whisper_model
from .ai.process_transcript import process_transcript
from .ai.ai_service import AIService
from .utils.profile_parser import load_profile_yaml, get_available_profiles
from .utils.profile_executor import run_profile_actions
import traceback
from pathlib import Path
from InquirerPy import inquirer


def select_profile():
    """Interactive profile selection."""
    try:
        available_profiles = get_available_profiles()
        if not available_profiles:
            log.warning("No profiles found!")
            return None, None

        # Create profile choices with descriptions
        choices = []
        profile_dict = {}  # Create a dictionary from the profiles
        
        for profile in available_profiles:
            try:
                profile_data = load_profile_yaml(profile)
                if profile_data:
                    desc = profile_data.get('description', '')
                    choice_str = f"{profile}"
                    if desc:
                        choice_str += f" - {desc}"
                    choices.append(choice_str)
                    profile_dict[profile] = profile_data
            except Exception as e:
                log.debug(f"Error loading profile {profile}: {e}")
                continue

        if not choices:
            log.warning("No valid profiles found!")
            return None, None

        # Show profile selection prompt
        selection = inquirer.select(
            message="Select a profile:",
            choices=choices,
        ).execute()

        # Extract profile ID from selection
        selected_profile = selection.split(" - ")[0]
        return selected_profile, profile_dict.get(selected_profile)

    except Exception as e:
        log.error(f"Error selecting profile: {e}")
        return None, None


def cli_mode(ai_provider=None, debug=False, profile=None):
    """Run the application in CLI mode."""
    try:
        # Initialize logging
        log.debug_mode = debug or config.system.debug_mode

        logging.basicConfig(
            level=logging.INFO if not config.system.debug_mode else logging.DEBUG
        )
        logger = logging.getLogger(__name__)

        # Check for required Whisper model
        check_whisper_model()
        
        # Print header and instructions
        log.print_header()
        
        # Handle profile selection
        profile_data = {}
        
        if profile == "":  # Empty string means --profile was passed without a value
            profile, profile_data = select_profile()
            if not profile:
                log.error("No profile selected")
                return
        # If no profile specified at all, try to use default from config
        elif not profile and config.output.default_profile:
            profile = config.output.default_profile
            try:
                profile_data = load_profile_yaml(profile) or {}
            except Exception as e:
                log.error(f"Error loading default profile: {e}")
                if debug:
                    log.debug(traceback.format_exc())
                return
        # If profile name specified, load it
        elif profile:
            try:
                profile_data = load_profile_yaml(profile) or {}
            except Exception as e:
                log.error(f"Error loading profile: {e}")
                if debug:
                    log.debug(traceback.format_exc())
                return
        else:
            log.error("No profile specified and no default profile configured")
            return

        # Display profile information if we have it
        if profile and profile_data:
            name = profile_data.get('name') or profile
            log.info(f"\nUsing profile: {name}")
            if description := profile_data.get('description'):
                log.info(f"Description: {description}")

        log.info("\nControls:")
        log.info("- Press Enter to start and stop recording")
        log.info("- Press Ctrl+C to quit\n")

        # Initialize recording manager
        recording_manager = RecordingManager()

        # Initialize AI service if provider specified
        if ai_provider:
            try:
                ai_service = AIService(service_type=ai_provider)
            except ValueError as e:
                logger.error(f"Error initializing AI service: {e}")
                return

        try:
            while True:
                try:
                    if not recording_manager.is_recording:
                        input("Press Enter to start recording...")
                        log.recording("Starting recording...")
                        recording_manager.start_recording()
                    else:
                        input("Recording in progress. Press Enter to stop...")
                        log.recording("Stopping recording...")
                        audio_file_path = recording_manager.stop_recording()
                        transcript_path = get_transcript_path(audio_file_path)

                        if transcript_path and profile:
                            logger.info(f"Processing transcript with profile: {profile}...")
                            # run AI
                            processed_output = process_transcript(
                                transcript_path,
                                ai_provider=ai_provider,
                                prompt=profile_data.get("prompt", ""),
                            )
                            # run the actions
                            run_profile_actions(profile_data, processed_output)
                            
                        time.sleep(1)
                        log.done("All done! Ready for the next recording 🫡")

                except EOFError:
                    break

        except KeyboardInterrupt:
            log.warning("\nReceived keyboard interrupt, shutting down...")
            if recording_manager.is_recording:
                recording_manager.stop_recording()

        log.info("\nShutting down...")
        if recording_manager.is_recording:
            recording_manager.stop_recording()
        log.success("Goodbye!")

    except Exception as e:
        log.error(f"Unexpected error in cli_mode: {str(e)}")
        if debug:
            log.debug(traceback.format_exc())


def main():
    """Main entry point for the application."""
    args = None  # Initialize args outside try block
    try:
        parser = argparse.ArgumentParser(
            description="WhisperBox - Audio Recording and Transcription Tool",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  # Run initial setup
  wb --setup

  # Record and transcribe with profile selector
  wb --profile

  # Record and transcribe with specific profile
  wb --profile meeting_summary

  # Record and transcribe a meeting with Ollama
  wb --ai-provider ollama --profile meeting_summary

  # Record and create a blog post with OpenAI
  wb --ai-provider openai --profile meeting_to_blogpost

  # List and configure audio devices
  wb --devices

For more information, visit: https://github.com/ToolUse/whisperbox
"""
        )

        # Setup and configuration group
        setup_group = parser.add_argument_group('Setup and Configuration')
        setup_group.add_argument(
            "--setup",
            action="store_true",
            help="Run the initial setup process (configure AI, audio devices, etc.)",
        )
        setup_group.add_argument(
            "--devices",
            action="store_true",
            help="List and select audio input devices (microphone and system audio)",
        )
        setup_group.add_argument(
            "--open",
            action="store_true",
            help="Open the WhisperBox data folder in Documents",
        )

        # Recording and Processing group
        processing_group = parser.add_argument_group('Recording and Processing')
        processing_group.add_argument(
            "--ai-provider",
            type=str,
            choices=['ollama', 'groq', 'anthropic', 'openai'],
            help="AI provider to use for processing transcripts",
        )
        processing_group.add_argument(
            "-p", "--profile",
            type=str,
            nargs='?',
            const='',  # This makes the value empty string when flag is used without value
            help="Profile to use for processing. Use without a value to select from available profiles.",
        )

        # Debug group
        debug_group = parser.add_argument_group('Debugging')
        debug_group.add_argument(
            "--debug", 
            action="store_true", 
            help="Enable debug logging for troubleshooting",
        )

        args = parser.parse_args()

        # Initialize logging - enable debug mode for both loggers
        debug_enabled = args.debug or config.system.debug_mode
        log.debug_mode = True  # Enable debug mode for custom logger during startup
        logging.basicConfig(
            level=logging.DEBUG if debug_enabled else logging.INFO,
            format='%(levelname)s: %(message)s'
        )
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG if debug_enabled else logging.INFO)
        
        log.debug("Starting WhisperBox...")

        # Check if this is first run or setup is explicitly requested
        if args.setup or is_first_run():
            log.info("Running initial setup...")
            setup()
            log.success("Setup completed! Please run WhisperBox again to start using it.")
            return

        # Only check for migrations if this isn't the first run
        if not is_first_run():
            log.info("Checking for migrations...")
            migration_manager = MigrationManager()
            logger.debug("Migration manager created")
            migration_results = migration_manager.check_and_migrate()
            logger.debug(f"Migration results: {migration_results}")
            
            # Reset debug mode to user preference after migration
            log.debug_mode = debug_enabled
            
            if migration_results["migrations_performed"]:
                log.info("Configuration updates applied:")
                for migration in migration_results["migrations_performed"]:
                    log.info(f"- {migration}")
                if migration_results["needs_restart"]:
                    log.warning("Some changes require a restart to take effect.")
                    return

        # Handle special commands
        if args.devices:
            list_audio_devices()
            return

        if args.open:
            reveal_in_file_manager(get_app_dir())
            return

        # Run the main CLI mode
        cli_mode(
            ai_provider=args.ai_provider,
            debug=args.debug,
            profile=args.profile,
        )

    except KeyboardInterrupt:
        log.warning("\nReceived keyboard interrupt, shutting down...")
    except Exception as e:
        log.error(f"An error occurred: {str(e)}")
        if args and args.debug:  # Check if args exists and debug is True
            log.debug(traceback.format_exc())


if __name__ == "__main__":
    main()
