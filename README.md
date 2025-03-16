# WhisperBox

A powerful command-line tool for transcribing and analyzing audio recordings with AI assistance. Record meetings, lectures, or any audio directly from your terminal and get instant transcriptions with summaries, sentiment analysis, and topic detection.


## Features

- Live audio recording through terminal
- Multiple transcription models via Whisper AI
- AI-powered analysis including:
  - Meeting summaries and action items
  - Keynote presentation generation
  - Speech quality feedback
  - Modify voice input for any application
- Support for multiple AI providers:
  - Anthropic
  - OpenAI
  - Groq
  - Ollama (local models)
- Export to Markdown
- Rich terminal UI with color-coded output
- Configurable audio settings and output formats

## Prerequisites

- Python 3.10 or higher
- FFmpeg (required for audio processing)
- Poetry (for dependency management)

## Installation

1. Install FFmpeg if not already installed:

```bash
# On macOS using Homebrew
brew install ffmpeg

# On Ubuntu/Debian
sudo apt-get install ffmpeg libgirepository-2.0-dev
```

2. Install BlackHole for system audio capture (MacOS only)

```bash
brew install blackhole-2ch
```

3. Install portaudio for audio capture

```bash
brew install portaudio
```

4. Install whisperbox from pip

```bash
pip install whisperbox
```

## System Audio Capture Setup

### macOS

1. Install BlackHole: `brew install blackhole-2ch`
2. Set up a Multi-Output Device in Audio MIDI Setup:
   - Open Audio MIDI Setup (using Spotlight or from Applications/Utilities)
   - Click the + in the bottom left and select "Create Multi-Output Device"
   - Check both your regular output and BlackHole 2ch
3. Select the new Multi-Output Device as your system output
4. In WhisperBox, select BlackHole 2ch as your system audio input

### Linux and Windows

System audio capture requires additional setup that varies by distribution/version. When running `wb --devices`, WhisperBox will look for common system audio capture devices like:

- Linux: PulseAudio monitors, JACK inputs, or audio loopback devices
- Windows: Stereo Mix, VB-Cable, or other virtual audio devices

Please check your system's documentation for setting up audio capture devices.

## Usage

### Setup

The first time you run the app, you will go through the setup wizard.

```bash
wb
```

Then select the Whisper model you want to use. The smaller models are faster and quicker to download but the larger models are more accurate.
Download times will vary depending on your internet speed.

Then select the AI provider you want to use. Ollama runs locally and does not require an API key.

Then select the model you want to use.

Then you will have the option to view the config file location so you can customize additional settings. This directory also contains the whisper models you downloaded and the data directory that contains all your recordings and transcriptions.

### Basic Transcription

1. Start recording:

```bash
wb
```

2. Press Enter to stop recording when finished.

### Advanced Options

- Specify a profile:

```bash
wb --profile monologue_to_keynote
```

- Configure audio devices:

```bash
wb --devices
```

This will launch an interactive device selection menu where you can configure both your microphone input and system audio capture devices. Useful for setting up or changing your recording sources.

- Specify a Whisper model:

```bash
wb --model large
```

- Enable full analysis (summary, sentiment, intent, topics):

```bash
wb --analyze
```

- Enable verbose output:

```bash
wb --verbose
```

## Configuration

The `config.yaml` file allows you to customize:

- API settings for AI providers
- Audio recording parameters
- Transcription settings
- Output formats and directories
- Display preferences
- AI prompt templates

See the example `config.yaml` for all available options.

## Extending WhisperBox

WhisperBox can be customized to handle your recordings exactly how you want. There are two main ways to extend it:

1. **Profiles**: Define what to do with your recordings
2. **Scripts**: Create custom actions for your profiles

### Creating Custom Profiles

A profile is a simple YAML file that tells WhisperBox:

- What to do with your recording
- How to process the transcript
- Where to send the results

To create a profile:

1. Create a new `.yaml` file in the `profiles/` folder (e.g., `my_profile.yaml`)
2. Add these three main sections:

```yaml
# The name that appears in WhisperBox
name: my_profile

# Instructions for processing your recording
prompt: >
  Here's where you tell WhisperBox what to do with your recording.
  For example: "Create a summary with these key points..."

  The recording will appear here: {transcript}

# What to do with the results
actions:
  - script: output_to_markdown # Save as a file
  - script: copy_to_clipboard # Copy to clipboard
```

### Built-in Actions

WhisperBox comes with several ready-to-use actions:

- `output_to_markdown`: Save as a Markdown file
- `copy_to_clipboard`: Copy to your clipboard
- `output_to_terminal`: Show in the terminal
- `send_post_request`: Send to a webhook URL

You can use multiple actions in a single profile:

```yaml
actions:
  # Save the file
  - script: output_to_markdown
    config:
      filename: meeting_notes.md

  # Also copy it to clipboard
  - script: copy_to_clipboard
```

### Creating Custom Scripts

Want to do something more custom? You can create your own action scripts:

1. Create a new Python file in the `scripts/` folder (e.g., `my_script.py`)
2. Add a `run_action` function that handles the text:

```python
def run_action(text, config):
    """
    text: The processed recording
    config: Any settings from your profile
    """
    print("I got the text:", text)
    # Do whatever you want with the text here!
```

3. Use it in your profile:

```yaml
actions:
  - script: my_script
    config:
      any_setting: value
```

### Example: Meeting Summary Profile

Here's a complete example that creates meeting summaries:

```yaml
name: meeting_summary
prompt: >
  Create a clear summary of this meeting with:
  1. Key topics and decisions
  2. Action items and who's responsible
  3. Important deadlines or dates

  Meeting transcript: {transcript}

actions:
  # Save as a file
  - script: output_to_markdown
    config:
      filename: summary.md

  # Also copy to clipboard
  - script: copy_to_clipboard
```

### Tips

- Test your profiles with short recordings first
- Check the `profiles/` folder for more examples
- Use multiple actions to create powerful workflows
- Keep your prompts clear and specific

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- [Whisper](https://github.com/openai/whisper) for the transcription models
- [Rich](https://github.com/Textualize/rich) for the terminal UI
- All the AI providers supported by this tool

## Authors

- Ty Fiero <tyfierodev@gmail.com>
- Mike Bird <tooluseai@gmail.com>
