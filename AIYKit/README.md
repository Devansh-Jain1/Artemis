# Artemis — AIY Kit

The early Raspberry Pi / Google AIY Kit implementation, with its device client and processing server kept together here.

```text
AIYKit/
  README.md
  client/
    newclient_pizero.py
  server/
    secure_server.py
```

## How the two parts work together

1. The [client](client/newclient_pizero.py) captures microphone audio, uses WebRTC VAD to segment speech, and sends a WAV recording plus recent conversation history over TCP.
2. The [server](server/secure_server.py) transcribes with faster-whisper, sends the text and conversation context to Groq, and returns a transcript and text response.
3. The client updates its conversation history and speaks the response through its locally configured speech command.

This checked-in pair returns text to the client; it is not the separate historical server-side Kokoro audio-streaming version or the later native iPhone stack. The Groq inference path requires a cloud service.

## Configuration and dependencies

- **Client:** Python, PyAudio, WebRTC VAD, optional Raspberry Pi GPIO, and a supported local speech command. Configure the server address, audio device and GPIO settings for your hardware.
- **Server:** Python, faster-whisper and the Groq SDK. Supply `GROQ_API_KEY` privately through the environment and check the configured model's availability.
- Both scripts use port `5006` by default. This historical TCP protocol does not implement transport encryption or authentication; the server filename is not a security guarantee.

These are development snapshots, not a verified installation package. They have not been rerun on hardware as part of this documentation update.

[Back to Artemis](../README.md)
