#!/usr/bin/env python3
"""
Improved Real-time Assistant Server
Handles continuous conversations with context
"""
import socket
import os
import sys
import threading
import tempfile
import time
import signal
import logging
import json
from pathlib import Path

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    print("Warning: faster-whisper not installed. Install with: pip install faster-whisper")
    WHISPER_AVAILABLE = False

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    print("Warning: groq not installed. Install with: pip install groq")
    GROQ_AVAILABLE = False

# ─── CONFIG ───────────────────────────────────────────────
TCP_IP = "0.0.0.0"
TCP_PORT = 5006
API_KEY = os.environ.get("GROQ_API_KEY")  # Load from environment variable
MODEL_NAME = "llama3-8b-8192"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB max
MAX_REQUEST_SIZE = 10 * 1024 * 1024  # 10MB max for request data
TEMP_DIR = tempfile.gettempdir()

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class ConversationManager:
    def __init__(self):
        self.sessions = {}  # client_id -> conversation_history

    def get_system_prompt(self):
        return """You are a helpful voice assistant. Be concise and conversational. Keep responses under 100 words. If confused, ask for clarification."""

    def format_conversation(self, history):
        messages = [{"role": "system", "content": self.get_system_prompt()}]
        for entry in history[-10:]:
            messages.append({"role": entry["role"], "content": entry["content"]})
        return messages

    def add_to_history(self, client_id, role, content):
        if client_id not in self.sessions:
            self.sessions[client_id] = []
        self.sessions[client_id].append({"role": role, "content": content})
        self.sessions[client_id] = self.sessions[client_id][-40:]

class AssistantServer:
    def __init__(self):
        self.whisper_model = None
        self.groq_client = None
        self.server_socket = None
        self.running = True
        self.conversation_manager = ConversationManager()

    def initialize(self):
        if not API_KEY:
            logger.error("GROQ_API_KEY environment variable not set!")
            logger.error("Set it with: export GROQ_API_KEY='your_api_key_here'")
            return False
            
        if WHISPER_AVAILABLE:
            self.whisper_model = WhisperModel("tiny.en", device="cpu", compute_type="int8")
            logger.info("Whisper model loaded")
        if GROQ_AVAILABLE:
            self.groq_client = Groq(api_key=API_KEY)
            logger.info("Groq initialized")
        return self.whisper_model and self.groq_client

    def transcribe(self, wav_path):
        segments, _ = self.whisper_model.transcribe(wav_path, language="en")
        return " ".join([seg.text.strip() for seg in segments]).strip()

    def get_response(self, text, history, client_id):
        messages = self.conversation_manager.format_conversation(history)
        messages.append({"role": "user", "content": text})
        res = self.groq_client.chat.completions.create(model=MODEL_NAME, messages=messages)
        reply = res.choices[0].message.content.strip()
        self.conversation_manager.add_to_history(client_id, "user", text)
        self.conversation_manager.add_to_history(client_id, "assistant", reply)
        return reply

    def handle_client(self, conn, addr):
        client_id = f"{addr[0]}:{addr[1]}"
        wav_path = None
        try:
            conn.settimeout(30)
            size_data = conn.recv(8)
            request_size = int.from_bytes(size_data, 'big')
            request_data = conn.recv(request_size)
            request_json = json.loads(request_data.decode('utf-8'))
            audio_file_size = request_json.get("audio_file_size", 0)
            history = request_json.get("conversation_history", [])

            if audio_file_size <= 0 or audio_file_size > MAX_FILE_SIZE:
                return

            wav_path = os.path.join(TEMP_DIR, f"audio_{time.time_ns()}.wav")
            with open(wav_path, 'wb') as f:
                remaining = audio_file_size
                while remaining > 0:
                    chunk = conn.recv(min(8192, remaining))
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)

            transcript = self.transcribe(wav_path)

            # **ADDED: log timestamp + transcript here**
            logger.info(f"User said at {time.strftime('%Y-%m-%d %H:%M:%S')}: {transcript}")

            response = self.get_response(transcript, history, client_id)
            response_data = json.dumps({"response": response, "transcript": transcript}).encode('utf-8')
            conn.send(len(response_data).to_bytes(8, 'big'))
            conn.send(response_data)
        except Exception as e:
            logger.error(f"Error handling client {client_id}: {e}")
        finally:
            if wav_path and os.path.exists(wav_path):
                os.remove(wav_path)
            try: conn.close()
            except: pass

    def start(self):
        if not self.initialize():
            logger.error("Initialization failed")
            return
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((TCP_IP, TCP_PORT))
        self.server_socket.listen(5)
        logger.info(f"Server listening on {TCP_IP}:{TCP_PORT}")
        try:
            while self.running:
                conn, addr = self.server_socket.accept()
                threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True).start()
        except KeyboardInterrupt:
            logger.info("Shutting down server")
        finally:
            self.server_socket.close()

if __name__ == "__main__":
    server = AssistantServer()
    server.start()
