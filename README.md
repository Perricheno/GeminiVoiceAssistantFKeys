# Gemini Voice Assistant (F-Key Edition) 🎙️✨

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/) [![Platform](https://img.shields.io/badge/platform-Windows-0078D6.svg?style=flat-square)](https://www.microsoft.com/windows/)
<!-- Future Badges:
[![Latest Release](https://img.shields.io/github/v/release/Perricheno/GeminiVoiceAssistantFKeys)](https://github.com/Perricheno/GeminiVoiceAssistantFKeys/releases/latest)
[![Downloads](https://img.shields.io/github/downloads/Perricheno/GeminiVoiceAssistantFKeys/total.svg)](https://github.com/Perricheno/GeminiVoiceAssistantFKeys/releases)
-->

A Windows voice assistant powered by Google's Gemini AI, controlled by simple F-key hotkeys. It records your voice, transcribes it, and can provide AI-generated responses or perform actions based on your commands.

**Note:** This version uses direct F-keys (`F9`, `Shift+F9`, `Ctrl+F9`) for controls.

## 🌟 Core Features

*   **Voice Command Recording (`F9`):** Press `F9` to start recording, press `F9` again to stop.
*   **Transcription & AI Assistance:** Recorded audio is sent to Gemini for transcription and/or to get an assistant's response.
*   **Switchable Prompts (`Shift+F9`):** Toggle between:
    *   **Assistant Mode:** Gemini interprets your transcribed audio to answer questions or follow instructions.
    *   **Transcription Mode:** Gemini only transcribes your audio to text.
*   **Switchable AI Models (`Ctrl+F9`):** Cycle between powerful (e.g., Gemini Pro preview) and faster (e.g., Gemini Flash preview) models for AI responses.
*   **Output to Clipboard:** The AI's final response is copied to the clipboard.
*   **System Notifications:** Get notified about recording status, mode changes, and when responses are ready.
*   **Local Audio Storage:** Recorded audio files are saved locally in `.wav` format with timestamps.
*   **Logging:** Detailed logs for operation tracking and troubleshooting.
*   **Background Operation:** Runs as a background process.

## 🛠 Technologies Used

*   Python 3
*   Google Gemini API (`google-generativeai`)
*   `pynput` (for global hotkey listening)
*   `sounddevice` & `numpy` (for audio recording)
*   `scipy` (for saving WAV files)
*   `pyperclip` (for clipboard operations)
*   `winotify` (for Windows system notifications)
*   `pywin32` (Windows API access, often a dependency)
*   `PyInstaller` (for packaging into an `.exe`)

## 🚀 Installation & Setup

### For Users (Recommended - using pre-built `.exe`):

1.  Navigate to the [**Releases**](https://github.com/Perricheno/GeminiVoiceAssistantFKeys/releases) section of this repository.
2.  Download the latest `GeminiVoiceAssistantV6.exe` (or similar name). **This `.exe` includes a pre-configured API key for demonstration purposes.**
3.  **Crucial:** The `.exe` file **must be run as administrator** for global hotkeys to work correctly.
    *   Right-click the `.exe` -> "Run as administrator".
    *   For auto-start, use Windows Task Scheduler configured with "Run with highest privileges".
4.  Ensure your microphone is properly configured in Windows.

### For Developers (from source code):

1.  Clone the repository:
    ```bash
    git clone https://github.com/Perricheno/GeminiVoiceAssistantFKeys.git
    cd GeminiVoiceAssistantFKeys
    ```
2.  Create and activate a virtual environment:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate  
    ```
    (For PowerShell. For CMD, use `venv\Scripts\activate.bat`)
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  **IMPORTANT API KEY SETUP:**
    *   Open the main script file located at `src/voice_agent_core.py` in a text editor.
    *   Navigate to approximately **line 96** (the exact line number might vary slightly if code above it changes). You will find:
        ```python
        API_KEY_HARDCODED = "YOUR_API_KEY_HERE" # <<< IMPORTANT: Replace with your actual Google Gemini API Key
        ```
    *   Replace `"YOUR_API_KEY_HERE"` with your **actual Google Gemini API Key**.
    *   Save the file.
5.  Run the script (requires administrator privileges for global hotkeys):
    ```bash
    python src/voice_agent_core.py
    ```

## 📋 How to Use

1.  Ensure the application (`.exe` or script) is **running with administrator privileges**.
2.  **Start/Stop Recording:**
    *   Press **`F9`**. A notification "Recording started" will appear.
    *   Speak your command or query.
    *   Press **`F9`** again to stop recording. A notification "Recording saved, sending to Gemini..." will appear.
3.  **Toggle Prompt Mode (Assistant/Transcribe):**
    *   Press **`Shift+F9`**. A notification will show the new active mode.
4.  **Toggle AI Model (Pro/Flash):**
    *   Press **`Ctrl+F9`**. A notification will show the new active model.
5.  **Getting the Result:**
    *   After processing, the AI's response will be:
        *   **Copied to your clipboard**.
        *   Displayed as a **Windows system notification**.
6.  **Files:**
    *   **Logs:** Check `Logs_VoiceAssistantV6/voice_assistant_v6.log` (in the app's directory).
    *   **Audio Recordings:** Saved in `audioV6/` (in the app's directory).

## ⚙️ Configuration (for developers modifying the source)

*   **API Key:** `API_KEY_HARDCODED` in `src/voice_agent_core.py`.
*   **Hotkeys:** `TRIGGER_KEY` (F9) and modifier checks in `on_key_press` function in `src/voice_agent_core.py`.
*   **AI Models:** `MODEL_FLASH`, `MODEL_PRO` can be changed to other compatible Gemini models.
*   **Prompts:** The `PROMPTS` dictionary defines the instructions sent to Gemini for "Assistant" and "Transcribe" modes.
*   **Audio Settings:** `SAMPLE_RATE`, `CHANNELS` can be adjusted if needed.

## ⚠️ Troubleshooting

*   **Hotkeys not working:** THE MOST COMMON ISSUE. **Ensure the application is running with administrator privileges.**
*   **No audio recorded / "No audio data":** Check your microphone settings in Windows and ensure it's selected as the default input device.
*   **API Errors (logged or in notifications):**
    *   `PermissionDenied`: API key might be invalid or lack permissions for the specified models.
    *   `ResourceExhausted`: You might have exceeded the free quota for the API.
    *   `NotFound`: The specified Gemini model name might be incorrect or unavailable.
    *   Content blocking: Your audio or prompt might have been blocked by safety filters.

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## 🙏 Acknowledgements

*   Google for the Gemini API.
*   The developers of `pynput`, `sounddevice`, `numpy`, `scipy`, `pyperclip`, `winotify`, `pywin32`, `Pillow`.