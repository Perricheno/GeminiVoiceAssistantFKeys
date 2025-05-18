# src/voice_agent_core.py
# -*- coding: utf-8 -*-
from pynput import keyboard # Using pynput for keyboard ONLY
import io
import time
import logging
import sys
from pathlib import Path
import datetime
import threading
import queue

# --- Required imports (audio, Gemini, Windows API, etc.) ---
try:
    import sounddevice as sd
    import numpy as np
    from scipy.io.wavfile import write as write_wav
    import google.generativeai as genai
    from google.api_core import exceptions as google_exceptions
    import pyperclip
    from winotify import Notification, audio
    import win32clipboard
    import win32con
    from PIL import ImageGrab # Pillow is included as PyInstaller sometimes needs its dependencies
except ImportError:
    # This message is primarily for users running the .py file directly
    # without a proper environment. PyInstaller should catch missing deps during build.
    critical_error_msg = "ERROR: One or more essential libraries are missing.\nPlease install: pip install pynput sounddevice numpy scipy google-generativeai pyperclip winotify pywin32 Pillow"
    print(critical_error_msg)
    # Attempt to show a GUI message if Tkinter is available by chance
    try:
        import tkinter as tk
        from tkinter import messagebox
        root_err = tk.Tk()
        root_err.withdraw()
        messagebox.showerror("Critical Dependency Error", critical_error_msg)
        root_err.destroy()
    except:
        pass
    sys.exit(1)
# ---------------------------------------------------------------

# --- Logging Setup ---
if getattr(sys, 'frozen', False): # Running as a PyInstaller .exe
    base_path = Path(sys.executable).parent
else: # Running as a .py script
    base_path = Path(__file__).parent

LOG_DIRECTORY_PATH = base_path / "Logs_VoiceAssistantV6"
AUDIO_DIRECTORY_PATH = base_path / "audioV6"
try:
    LOG_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    AUDIO_DIRECTORY_PATH.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIRECTORY_PATH / "voice_assistant_v6.log"
except OSError as e:
    # Fallback if preferred log directory creation fails
    print(f"ERROR: Could not create log/audio directories. Error: {e}")
    log_file = base_path / "voice_assistant_v6_ERROR.log"

log_formatter = logging.Formatter('%(asctime)s:%(msecs)03d - %(levelname)s - %(threadName)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
file_log_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8', delay=False)
file_log_handler.setFormatter(log_formatter)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO) # Default to INFO, set to DEBUG for detailed key logs
if not logger.hasHandlers(): # Prevent duplicate handlers
    logger.addHandler(file_log_handler)

# --- CONFIGURATION ---
# --- Hotkeys (F-Keys) ---
TRIGGER_KEY = keyboard.Key.f9 # Main key for recording and actions
# Modifiers (Shift, Ctrl) will be checked when TRIGGER_KEY is pressed
# -----------------------------

# Gemini Models (Using Preview versions as requested)
MODEL_FLASH = "gemini-2.5-flash-preview-04-17"
MODEL_PRO = "gemini-2.5-pro-preview-03-25"
DEFAULT_MODEL = MODEL_PRO

# Prompt Modes
PROMPT_MODE_TRANSCRIBE = "Transcribe"
PROMPT_MODE_ASSISTANT = "Assistant"
DEFAULT_PROMPT_MODE = PROMPT_MODE_ASSISTANT

# Prompts (Russian, as per previous versions)
PROMPTS = {
    PROMPT_MODE_TRANSCRIBE: "Слушай внимательно, и транскрибируй мои голосовые, и ничего лишнего кроме транскрибации не отправляй, я могу иногда смешивать языки русского и английского, транскрибируй их внимательно и тщательно.",
    PROMPT_MODE_ASSISTANT: "Слушай внимательно, ты даешь ответ на мои вопросы, без воды, ясно и понятно."
}

# Audio Settings
SAMPLE_RATE = 44100  # Standard sampling rate
CHANNELS = 1         # Mono recording

# API Key and App Name
API_KEY_HARDCODED = "YOUR_API_KEY_HERE" # <<< IMPORTANT: Replace with your actual Google Gemini API Key
APP_NAME_FOR_NOTIFICATION = "Gemini Voice Assistant V6"

# --- Global State Variables ---
shift_pressed = False
ctrl_pressed = False
is_recording = False
audio_frames = []       # List to store audio frames during recording
recording_thread = None # Thread object for audio recording
recording_stop_event = threading.Event() # Event to signal recording thread to stop
current_model_name = DEFAULT_MODEL
current_prompt_mode = DEFAULT_PROMPT_MODE
processing_lock = threading.Lock() # To prevent race conditions when toggling states
last_hotkey_time = 0       # For basic hotkey debounce
keyboard_listener = None   # pynput keyboard listener object

# --- Core Functions ---

def show_system_notification(title, message, sound=audio.Default):
    """Displays a standard Windows notification using winotify."""
    try:
        toast = Notification(app_id=APP_NAME_FOR_NOTIFICATION, title=title, msg=message, duration="short")
        toast.set_audio(sound, loop=False)
        toast.show()
        logger.info(f"Notification shown: '{title}' - '{message[:50]}...'")
    except Exception as e:
        logger.error(f"Failed to show system notification: {e}")

def audio_recording_worker():
    """Worker function executed in a separate thread for audio recording."""
    global audio_frames, is_recording, recording_stop_event
    
    audio_frames = [] # Clear frames before a new recording
    recording_stop_event.clear() # Reset stop event
    
    # Queue for transferring audio data from callback to this thread
    # This is good practice for sounddevice callbacks
    data_queue = queue.Queue()

    def sd_callback(indata, frame_count, time_info, status):
        """This callback is called by sounddevice for each audio block."""
        if status:
            logger.warning(f"Audio stream status: {status}")
        data_queue.put(indata.copy()) # Put a copy of the data into the queue

    try:
        logger.info("Audio recording thread: Starting InputStream...")
        # Start the input stream with the callback
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16', callback=sd_callback):
            logger.info("Audio recording thread: InputStream active. Waiting for stop signal...")
            while not recording_stop_event.is_set():
                try:
                    # Get data from the queue and append to global frames list
                    audio_frames.append(data_queue.get(timeout=0.1)) 
                except queue.Empty:
                    continue # No new data, just continue waiting for stop signal
            logger.info("Audio recording thread: Stop signal received.")
            
    except Exception as e:
        logger.exception("CRITICAL ERROR in audio recording thread!")
        show_system_notification("Recording Error", f"Error during recording: {e}", sound=audio.Caution)
        # Ensure is_recording is reset if the thread crashes
        with processing_lock:
            is_recording = False
    finally:
        logger.info("Audio recording thread: Finishing.")

def start_audio_recording():
    """Starts the audio recording process in a new thread."""
    global is_recording, recording_thread
    with processing_lock:
        if is_recording:
            logger.warning("Attempted to start recording, but already recording.")
            return False # Indicate action was not performed
        is_recording = True
        logger.info("Starting audio recording...")
        show_system_notification("Recording Started", "Speak now...", sound=audio.LoopingCall2) # Different sound
        
        recording_thread = threading.Thread(target=audio_recording_worker, daemon=True, name="AudioRecordThread")
        recording_thread.start()
        return True # Indicate action was performed

def stop_audio_recording_and_process():
    """Stops recording, saves the audio, and sends it for AI processing."""
    global is_recording, recording_thread, audio_frames, processing_lock
    
    action_was_taken = False
    with processing_lock:
        if not is_recording:
            logger.warning("Attempted to stop recording, but not currently recording.")
            return False
        logger.info("Stopping audio recording...")
        recording_stop_event.set() # Signal the recording thread to stop
        action_was_taken = True # Recording will be stopped (attempted)

    # Wait for the recording thread to finish
    if recording_thread is not None and recording_thread.is_alive():
        logger.debug("Waiting for audio recording thread to complete...")
        recording_thread.join(timeout=2.0) # Wait up to 2 seconds
        if recording_thread.is_alive():
            logger.error("Audio recording thread did not finish in time!")
    recording_thread = None # Clear the thread object
    
    # Lock again for state consistency after thread join
    with processing_lock:
        is_recording = False # Ensure recording flag is false now

        if not audio_frames:
            logger.error("Recording stopped, but no audio data was captured.")
            show_system_notification("Recording Error", "Failed to record audio (no data).", sound=audio.Caution)
            return action_was_taken 

        try:
            logger.debug(f"Concatenating {len(audio_frames)} audio frames...")
            recording_data = np.concatenate(audio_frames, axis=0)
            logger.debug(f"Final recording shape: {recording_data.shape}, dtype: {recording_data.dtype}")
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"rec_fkeys_{timestamp}.wav" # Differentiate filenames
            filepath = AUDIO_DIRECTORY_PATH / filename
            
            logger.info(f"Saving audio to: {filepath}...")
            write_wav(filepath, SAMPLE_RATE, recording_data)
            logger.info("Audio saved successfully.")
            show_system_notification("Recording Saved", f"File: {filename}\nSending to Gemini...", sound=audio.Mail)

            # Process the audio with Gemini in a new thread to keep UI/hotkeys responsive
            gemini_processing_thread = threading.Thread(target=submit_audio_to_gemini, args=(filepath,), daemon=True, name="GeminiThread")
            gemini_processing_thread.start()

        except Exception as e:
            logger.exception("ERROR during audio saving or processing submission:")
            show_system_notification("Processing Error", f"Could not save/send audio: {e}", sound=audio.Caution)
        finally:
             audio_frames = [] # Clear frames for the next recording
    return action_was_taken

def submit_audio_to_gemini(audio_filepath):
    """Uploads audio, sends to Gemini, and handles the response."""
    global current_model_name, current_prompt_mode
    logger.info(f"Submitting '{audio_filepath.name}' to Gemini (Model: {current_model_name}, Mode: {current_prompt_mode})...")
    
    uploaded_audio_file = None
    try:
        logger.debug("Uploading audio file to Google...")
        upload_start_time = time.time()
        uploaded_audio_file = genai.upload_file(path=audio_filepath, display_name=audio_filepath.name)
        logger.info(f"Audio file uploaded in {time.time() - upload_start_time:.2f}s. URI: {uploaded_audio_file.uri}")

        ai_model = genai.GenerativeModel(current_model_name)
        prompt_text_for_ai = PROMPTS.get(current_prompt_mode, PROMPTS[DEFAULT_PROMPT_MODE])
        logger.debug(f"Using prompt: '{prompt_text_for_ai}'")

        logger.info("Requesting content generation from Gemini...")
        generation_start_time = time.time()
        # Construct the content: prompt text first, then the uploaded file object
        response = ai_model.generate_content([prompt_text_for_ai, uploaded_audio_file])
        logger.info(f"Gemini response received in {time.time() - generation_start_time:.2f}s.")

        if not response.parts: # Check if the response has content parts
             if hasattr(response, 'prompt_feedback') and response.prompt_feedback and response.prompt_feedback.block_reason:
                 block_reason_name = response.prompt_feedback.block_reason.name
                 error_message = f"Request blocked by safety filter (Reason: {block_reason_name})"
                 logger.error(f"Gemini API ERROR: {error_message}")
                 for rating in response.prompt_feedback.safety_ratings:
                     logger.warning(f"  - Safety Rating: Category={rating.category.name}, Probability={rating.probability.name}")
                 show_system_notification("Gemini Error", error_message, sound=audio.Caution)
             else:
                 logger.error("Gemini API ERROR: Response is empty (no parts and no specific block reason).")
                 show_system_notification("Gemini Error", "Received an empty response from AI.", sound=audio.Caution)
             return

        ai_response_text = response.text.strip()
        logger.info("AI response processed successfully.")
        logger.debug(f"--- START OF FULL AI RESPONSE ---\n{ai_response_text}\n--- END OF FULL AI RESPONSE ---")

        try:
            pyperclip.copy(ai_response_text)
            logger.info("AI response copied to clipboard.")
            show_system_notification("Gemini Response", ai_response_text, sound=audio.SMS) # Display full response
        except Exception as e_clip:
            logger.error(f"Failed to copy AI response to clipboard: {e_clip}")
            show_system_notification("AI Response (Clipboard Error)", ai_response_text, sound=audio.Caution)

    except google_exceptions.PermissionDenied as e_perm:
        error_msg = f"ACCESS DENIED! Invalid API key or no permission for model '{current_model_name}'."
        logger.error(error_msg); logger.debug(f"Details: {e_perm}")
        show_system_notification("Gemini API Error", error_msg, sound=audio.Caution)
    except (google_exceptions.InvalidArgument, google_exceptions.NotFound) as e_arg:
        error_msg = f"MODEL ERROR! Model '{current_model_name}' not found or invalid."
        logger.error(error_msg); logger.debug(f"Details: {e_arg}")
        show_system_notification("Gemini API Error", error_msg, sound=audio.Caution)
    except google_exceptions.ResourceExhausted as e_quota:
        error_msg = "QUOTA ERROR! API request limit reached."
        logger.error(error_msg); logger.debug(f"Details: {e_quota}")
        show_system_notification("Gemini API Error", error_msg, sound=audio.Caution)
    except Exception as e_gen:
        logger.exception("UNKNOWN ERROR during Gemini interaction:")
        show_system_notification("Unknown Gemini Error", f"An error occurred: {e_gen}", sound=audio.Caution)
    finally:
        if uploaded_audio_file:
            try:
                logger.debug(f"Deleting uploaded file '{uploaded_audio_file.name}' from Google server...")
                genai.delete_file(uploaded_audio_file.name) # Use the file object's name attribute
                logger.info("Uploaded audio file deleted successfully.")
            except Exception as e_del:
                logger.error(f"Failed to delete uploaded file '{uploaded_audio_file.name}': {e_del}")

def cycle_prompt_mode():
    """Toggles between Assistant and Transcribe prompt modes."""
    global current_prompt_mode
    with processing_lock: # Ensure thread-safe modification
        current_prompt_mode = PROMPT_MODE_TRANSCRIBE if current_prompt_mode == PROMPT_MODE_ASSISTANT else PROMPT_MODE_ASSISTANT
        message = f"Prompt Mode: {current_prompt_mode}"
        logger.info(f"*** {message} ***")
        show_system_notification("Mode Changed", message, sound=audio.Reminder)
    return True # Indicate action was taken

def cycle_ai_model():
    """Toggles between PRO and FLASH AI models."""
    global current_model_name
    with processing_lock: # Ensure thread-safe modification
        current_model_name = MODEL_FLASH if current_model_name == MODEL_PRO else MODEL_PRO
        message = f"AI Model: {current_model_name.split('/')[-1]}" # Show short name
        logger.info(f"*** {message} ***")
        show_system_notification("Model Changed", message, sound=audio.Reminder)
    return True # Indicate action was taken

# --- Pynput Hotkey Handlers (Revised for F-Keys) ---
def on_key_press(key):
    """Handles key press events from pynput keyboard listener."""
    global shift_pressed, ctrl_pressed, last_hotkey_time, is_recording

    # Update modifier states
    if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
        shift_pressed = True
        logger.debug("Shift Pressed")
        return
    if key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        ctrl_pressed = True
        logger.debug("Ctrl Pressed")
        return

    # Check if the main TRIGGER_KEY (F9) is pressed
    if key == TRIGGER_KEY:
        logger.debug(f"F9 Pressed! Current Modifier State: Shift={shift_pressed}, Ctrl={ctrl_pressed}")

        # Debounce mechanism
        current_time = time.time()
        if current_time - last_hotkey_time < 0.6: # Increased debounce time
            logger.debug("Debounce: F9 press ignored due to rapid succession.")
            return

        action_performed = False
        # Determine action based on modifier state AT THE TIME F9 IS PRESSED
        if shift_pressed and not ctrl_pressed: # Shift + F9
            logger.info("Hotkey Detected: Shift+F9 (Toggle Prompt Mode)")
            action_performed = cycle_prompt_mode()
        elif ctrl_pressed and not shift_pressed: # Ctrl + F9
            logger.info("Hotkey Detected: Ctrl+F9 (Toggle AI Model)")
            action_performed = cycle_ai_model()
        elif not shift_pressed and not ctrl_pressed: # Just F9
            logger.info("Hotkey Detected: F9 (Toggle Recording)")
            if is_recording:
                action_performed = stop_audio_recording_and_process()
            else:
                action_performed = start_audio_recording()
        else:
            # F9 pressed with both Shift and Ctrl, or other unexpected combo
            logger.debug("F9 pressed with an unsupported modifier combination (e.g., Ctrl+Shift+F9), ignoring.")

        if action_performed:
            last_hotkey_time = current_time # Update timestamp only if an action was taken
    else:
        # Log other key presses (non-modifier, non-F9) for debugging if needed
        try:
            logger.debug(f"Other key pressed: {key.char}")
        except AttributeError:
            logger.debug(f"Other special key pressed: {key}")

def on_key_release(key):
    """Handles key release events from pynput keyboard listener."""
    global shift_pressed, ctrl_pressed

    # Update modifier states
    if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
        shift_pressed = False
        logger.debug("Shift Released")
    elif key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
        ctrl_pressed = False
        logger.debug("Ctrl Released")
    else:
        logger.debug(f"Key released: {key}")

# --- Main Application Execution Block ---
if __name__ == "__main__":
    logger.info("=" * 20 + " Starting Gemini Voice Assistant V6 (F-Keys) " + "=" * 20)
    logger.warning("--- IMPORTANT: This application MUST be run with Administrator privileges for global hotkeys to work! ---")
    
    keyboard_listener = None # Initialize for the finally block

    # Configure Gemini Client (moved from global scope to main execution)
    try:
        if not API_KEY_HARDCODED or API_KEY_HARDCODED == "YOUR_API_KEY_HERE":
            logger.critical("CRITICAL ERROR: API_KEY_HARDCODED is not set or is a placeholder!")
            # Try to show a Tkinter messagebox if possible
            try:
                root_tk_err = tk.Tk(); root_tk_err.withdraw()
                messagebox.showerror("API Key Error", "Google Gemini API Key is not configured in the script!")
                root_tk_err.destroy()
            except:
                print("CRITICAL ERROR: API KEY NOT SET!")
            sys.exit(1)
        genai.configure(api_key=API_KEY_HARDCODED)
        logger.info("Google AI SDK configured successfully.")
    except Exception as e:
        logger.exception("CRITICAL ERROR during Gemini SDK initialization:")
        sys.exit(1)

    logger.info(f"Default Execution Model: {current_model_name}")
    logger.info(f"Default Prompt Mode: {current_prompt_mode}")
    logger.info(f"Record/Stop Hotkey: F9")
    logger.info(f"Toggle Prompt Mode Hotkey: Shift+F9")
    logger.info(f"Toggle AI Model Hotkey: Ctrl+F9")

    try:
        # Start the pynput keyboard listener
        # suppress=False allows key presses to pass through to other applications
        keyboard_listener = keyboard.Listener(on_press=on_key_press, on_release=on_key_release, suppress=False)
        keyboard_listener.start()
        logger.info("Pynput keyboard listener started. Application is active.")
        
        # Keep the main thread alive while the listener runs in its own thread.
        # A simple way for a non-GUI background app.
        # If a GUI were present, its mainloop would handle this.
        while keyboard_listener.is_alive(): # Or just keyboard_listener.join() if that's preferred
            time.sleep(1) # Check periodically or simply join

    except ImportError:
        logger.critical("ERROR: Pynput or other essential libraries not found. Please install all requirements.")
    except Exception as e:
        logger.exception("CRITICAL ERROR in the main application loop:")
        logger.critical("!!! This might be due to missing Administrator privileges for pynput to hook global keys !!!")
    finally:
        logger.info("Shutting down application...")
        if keyboard_listener and keyboard_listener.is_alive():
            try:
                keyboard_listener.stop()
                logger.info("Pynput keyboard listener stopped.")
            except Exception as e_kl_stop:
                logger.error(f"Error stopping keyboard listener: {e_kl_stop}")
        
        # Ensure recording is stopped if exiting abruptly
        if is_recording:
            logger.warning("Forcing recording stop during shutdown...")
            recording_stop_event.set()
            if recording_thread and recording_thread.is_alive():
                recording_thread.join(timeout=1.0) # Give it a second to finish
        
        logger.info("=" * 20 + " Gemini Voice Assistant V6 Shutdown Complete " + "=" * 20)