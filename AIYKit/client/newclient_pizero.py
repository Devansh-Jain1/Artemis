#!/usr/bin/env python3
"""
Improved Real-time Assistant Client
Continuous conversation with VAD-driven recording and faster TTS via stdin streaming
"""
import os
import sys
import socket
import signal
import time
import wave
import threading
import subprocess
from datetime import datetime
import json

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    print("❌ PyAudio not installed. Install with: pip install pyaudio")
    PYAUDIO_AVAILABLE = False

try:
    import webrtcvad
    VAD_AVAILABLE = True
except ImportError:
    print("❌ WebRTC VAD not installed. Install with: pip install webrtcvad")
    VAD_AVAILABLE = False

try:
    import RPi.GPIO as GPIO
    IS_PI = True
except ImportError:
    IS_PI = False

# ─── CONFIG ─────────────────────────────────────────────────────────────
SERVER_IP    = "100.127.160.77"  # Change to your server IP
SERVER_PORT  = 5006
BUTTON_PIN   = 23
RATE         = 16000
CHUNK        = int(0.02 * RATE)  # 20ms frames = 320 samples
FORMAT       = pyaudio.paInt16
CHANNELS     = 1
MIN_SPEECH_FRAMES = 15  # ~300ms of speech
SILENCE_FRAMES    = 25  # ~500ms silence to end recording
TAIL_FRAMES       = 10  # ~200ms tail buffer after silence
AUDIO_DIR   = "/tmp/assistant_audio"

class AudioProcessor:
    def __init__(self):
        self.vad = None
        self.silence_count = 0
        self.speech_started = False

    def initialize_vad(self):
        if VAD_AVAILABLE:
            try:
                self.vad = webrtcvad.Vad(1)  # Moderate aggressiveness
                return True
            except Exception as e:
                print(f"⚠️ VAD initialization failed: {e}")
        return False

    def process_frame(self, frame_data):
        if not self.vad:
            return True, False  # No VAD: always record

        try:
            is_speech = self.vad.is_speech(frame_data, RATE)
            if is_speech:
                if not self.speech_started:
                    print("👂 Speech detected!")
                    self.speech_started = True
                self.silence_count = 0
                return True, False
            else:
                if self.speech_started:
                    self.silence_count += 1
                    if self.silence_count >= SILENCE_FRAMES:
                        print("🔇 End of speech detected")
                        return True, True
                return self.speech_started, False
        except Exception:
            return True, False

    def reset(self):
        self.silence_count = 0
        self.speech_started = False

class AssistantClient:
    def __init__(self):
        self.recording = False
        self.should_stop = False
        self.conversation_active = False
        self.tts_playing = False
        self.pa = None
        self.audio_processor = AudioProcessor()
        self.conversation_history = []
        self.tts_cmd = None  # will be set in initialize()

    def initialize(self):
        print("🎤 Initializing Assistant Client...")
        if not PYAUDIO_AVAILABLE:
            print("❌ PyAudio not available")
            return False
        try:
            self.pa = pyaudio.PyAudio()
            print("✅ PyAudio initialized")
        except Exception as e:
            print(f"❌ Failed to initialize PyAudio: {e}")
            return False
        if self.audio_processor.initialize_vad():
            print("✅ VAD initialized")
        else:
            print("⚠️ VAD not available - using continuous recording")
        for candidate in ("espeak-ng", "espeak"):
            if subprocess.run(["which", candidate], capture_output=True).returncode == 0:
                self.tts_cmd = candidate
                break
        if self.tts_cmd:
            print(f"✅ TTS engine found: {self.tts_cmd}")
        else:
            print("⚠️ No TTS engine found (espeak-ng/espeak)")
        return True

    def list_audio_devices(self):
        if not self.pa:
            return
        print("\n🎧 Available audio devices:")
        for i in range(self.pa.get_device_count()):
            try:
                info = self.pa.get_device_info_by_index(i)
                if info['maxInputChannels'] > 0:
                    print(f"  {i}: {info['name']} (inputs: {info['maxInputChannels']})")
            except:
                pass
        print()

    def record_audio_vad(self):
        print("🎙️ Starting VAD recording...")
        try:
            stream = self.pa.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            frames = []
            self.audio_processor.reset()
            print("🎧 Listening for speech...")
            while self.recording and not self.should_stop:
                data = stream.read(CHUNK, exception_on_overflow=False)
                if self.tts_playing:
                    continue
                should_record, speech_ended = self.audio_processor.process_frame(data)
                if should_record:
                    frames.append(data)
                    if speech_ended and len(frames) >= MIN_SPEECH_FRAMES:
                        for _ in range(TAIL_FRAMES):
                            if not self.recording:
                                break
                            tail = stream.read(CHUNK, exception_on_overflow=False)
                            frames.append(tail)
                        break
            stream.stop_stream()
            stream.close()
            if not frames or len(frames) < MIN_SPEECH_FRAMES:
                print("❌ Insufficient audio recorded")
                return None
            os.makedirs(AUDIO_DIR, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            wav_path = os.path.join(AUDIO_DIR, f"recording_{timestamp}.wav")
            with wave.open(wav_path, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(self.pa.get_sample_size(FORMAT))
                wf.setframerate(RATE)
                wf.writeframes(b''.join(frames))
            print(f"💾 Saved recording: {wav_path} ({len(frames)} frames)")
            return wav_path
        except Exception as e:
            print(f"❌ Recording error: {e}")
            return None

    def send_audio_with_context(self, wav_path):
        try:
            if not os.path.exists(wav_path):
                print(f"❌ Audio file not found: {wav_path}")
                return None
            request_data = {
                "conversation_history": self.conversation_history[-10:],
                "audio_file_size": os.path.getsize(wav_path)
            }
            request_json = json.dumps(request_data).encode('utf-8')
            print("📤 Sending audio + context to server...")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((SERVER_IP, SERVER_PORT))
            sock.send(len(request_json).to_bytes(8, 'big'))
            sock.send(request_json)
            with open(wav_path, 'rb') as f:
                while True:
                    chunk = f.read(8192)
                    if not chunk:
                        break
                    sock.send(chunk)
            size_data = sock.recv(8)
            response_size = int.from_bytes(size_data, 'big')
            response_data = b""
            while len(response_data) < response_size:
                part = sock.recv(response_size - len(response_data))
                if not part:
                    break
                response_data += part
            sock.close()
            response = json.loads(response_data.decode('utf-8'))
            print(f"💬 Server response: {response.get('response', '<no response>')}")
            return response
        except Exception as e:
            print(f"❌ Communication error: {e}")
            return None
        finally:
            try:
                if os.path.exists(wav_path):
                    os.remove(wav_path)
            except:
                pass

    def speak_response_fast(self, text):
        if not self.tts_cmd:
            print("⚠️ No TTS engine available")
            return
        try:
            self.tts_playing = True
            proc = subprocess.Popen(
                [self.tts_cmd, "-s", "180", "-p", "50", "--stdin"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            proc.communicate(input=text.encode("utf-8"))
        except Exception as e:
            print(f"❌ TTS error: {e}")
        finally:
            self.tts_playing = False

    def handle_conversation_turn(self):
        print("\n" + "-" * 30)
        print("🎯 Recording turn...")
        wav_path = self.record_audio_vad()
        if not wav_path:
            self.speak_response_fast("Sorry, I didn't catch that. Could you repeat?")
            return False
        response_data = self.send_audio_with_context(wav_path)
        if response_data and response_data.get('response'):
            transcript = response_data.get('transcript', '')
            response_text = response_data['response']
            if transcript:
                self.conversation_history.append({"role": "user", "content": transcript})
            self.conversation_history.append({"role": "assistant", "content": response_text})
            self.speak_response_fast(response_text)
            return True
        else:
            self.speak_response_fast("Sorry, I didn't catch that. Could you repeat?")
            return False

    def start_conversation(self):
        print("\n🚀 Starting conversation session...")
        self.conversation_active = True
        self.conversation_history.clear()
        self.speak_response_fast("Hi, how can I help you?")
        print("🎤 Conversation active - speak naturally")
        print("🔘 Press button again to end conversation")
        while self.conversation_active and not self.should_stop:
            self.recording = True
            success = self.handle_conversation_turn()
            self.recording = False
            if not success:
                time.sleep(0.5)
        print("✅ Conversation session ended")
        self.speak_response_fast("Goodbye!")

    def button_callback(self, channel):
        if self.should_stop:
            return
        print("🔘 Button pressed!")
        if not self.conversation_active:
            threading.Thread(target=self.start_conversation, daemon=True).start()
        else:
            print("🛑 Ending conversation...")
            self.conversation_active = False
            self.recording = False

    def setup_gpio(self):
        if not IS_PI:
            print("⚠️ Not running on Pi - GPIO not available")
            return False
        try:
            GPIO.setwarnings(False)
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.add_event_detect(
                BUTTON_PIN,
                GPIO.FALLING,
                callback=self.button_callback,
                bouncetime=500
            )
            print(f"✅ GPIO button configured on pin {BUTTON_PIN}")
            return True
        except Exception as e:
            print(f"❌ GPIO setup failed: {e}")
            return False

    def simulate_interactions(self):
        print("🔘 Starting conversation simulation in 3 seconds...")
        time.sleep(3)
        self.button_callback(None)
        time.sleep(30)
        print("🔘 Ending conversation simulation...")
        self.button_callback(None)

    def run(self):
        if not self.initialize():
            print("❌ Failed to initialize client")
            return
        os.makedirs(AUDIO_DIR, exist_ok=True)
        self.list_audio_devices()
        gpio_ok = self.setup_gpio()
        if not gpio_ok:
            threading.Thread(target=self.simulate_interactions, daemon=True).start()
        print("\n🚀 Assistant Client Ready!")
        print(f"📡 Server: {SERVER_IP}:{SERVER_PORT}")
        if gpio_ok:
            print(f"🔘 Press GPIO {BUTTON_PIN} to toggle conversation")
        else:
            print("🔘 Running simulation automatically")
        print("Press Ctrl+C to exit\n")
        try:
            while not self.should_stop:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n🛑 Shutting down...")
            self.cleanup()

    def cleanup(self):
        print("�� Cleaning up...")
        self.should_stop = True
        self.recording = False
        self.conversation_active = False
        if self.pa:
            try:
                self.pa.terminate()
            except:
                pass
        if IS_PI:
            try:
                GPIO.cleanup()
            except:
                pass

def signal_handler(signum, frame):
    print(f"\n📴 Received signal {signum}, exiting.")
    sys.exit(0)

def main():
    print("🎤 Improved Real-time Assistant Client")
    print("=" * 50)
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    client = AssistantClient()
    client.run()

if __name__ == "__main__":
    main()

