# Artemis

**A voice assistant built around natural conversation on a personal device.**

Artemis began in 2025 with a Google AIY Voice Kit and Raspberry Pis. It has since evolved through desktop experiments into a native iPhone prototype with local speech recognition, language-model inference, speech synthesis, and turn-taking. The goal is to speak, pause, and interrupt without managing a push-to-talk interface for every exchange.

This repository contains **early Python prototypes** and the public project write-up. The newer Swift phone implementation is maintained privately; cloning this repository gives you the historical Python code, not the iPhone app.

## From a hardware experiment to a phone conversation

| Stage | What changed |
| --- | --- |
| 2025: AIY / Raspberry Pi | Separate audio client and processing server; local transcription with a cloud language model. Early versions stopped listening during replies. |
| Late 2025: desktop and Swift experiments | Explored streaming audio, voice activity detection, model reuse, and conversation state; began the native iPhone implementation. |
| October 2026: recorded iPhone run | Speech recognition, a local language model, speech synthesis, and learned turn completion ran on the phone. Listening continued during replies, with interruption-triggered speech cancellation. |

The hard part has been coordinating the conversation: deciding whether a pause means the user is finished, preventing the assistant's own voice from becoming new input, and cancelling old speech when the user takes the floor.

## Phone architecture

The recorded October 2, 2026 run used:

- **Capture and playback:** a shared `AVAudioEngine` with voice processing.
- **Speech recognition:** Parakeet EOU 120M via Core ML.
- **Voice activity and turn completion:** Silero VAD plus a WhisperTinyDualScale turn detector.
- **Language model:** Gemma E2B through LiteRT-LM.
- **Speech synthesis:** Supertonic 3 through Core ML.

These are integrations of existing models. My work is the application and the coordination between capture, recognition, inference, turn-taking, and playback.

## Measured results

A recorded physical-iPhone session on **October 2, 2026** contained seven finalized turns:

| Observation | Result |
| --- | --- |
| Final transcript → first audio queued | **1.053 s median** across seven turns |
| Learned completion decisions after speech end | **333–345 ms** across four decisions; three other turns used timeout completion |
| Speech cancelled when the user interrupted | **5 cancellation events** |
| Speech streams that finished | **2 streams** |

The 1.053-second figure ends when audio is scheduled, not when sound is measured at the speaker. It excludes speech recognition and turn-end detection time. This is a small recorded session, not an end-to-end latency benchmark or a claim about today's installed build.

[Measurement details and machine-readable summary](docs/voice-results.md)

## Code in this repository

| File | Purpose |
| --- | --- |
| [`newclient_pizero.py`](newclient_pizero.py) | Raspberry Pi audio client with button/voice activity handling and socket transport. |
| [`secure_server.py`](secure_server.py) | Historical server using faster-whisper transcription and Groq model inference. Despite its filename, it should not be treated as a hardened network service. |
| [`chatlog_parser.py`](chatlog_parser.py) | Separate experiment processing exported conversation text with a local Transformers model. |

These hardware-specific scripts retain historical configuration and dependencies. There is no packaged installation or supported public release. Review device addresses, audio settings, model availability, and credential handling before trying them; the server's cloud-model path is separate from the later all-local phone work.

Built by [Devansh Jain](https://github.com/Devansh-Jain1).
