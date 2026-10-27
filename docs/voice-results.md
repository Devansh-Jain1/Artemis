# Recorded iPhone voice results

**Run date:** October 2, 2026  
**Device identifier:** `iPhone17,2`  
**Build number:** `20261002`  
**Evidence:** retained application telemetry from a physical-device session. This page summarizes the run without publishing conversation content or raw device logs.

## What was measured

For each finalized transcript, the application recorded when the first output audio was scheduled. The seven intervals were:

```text
1757, 1156, 1269, 977, 1053, 1019, 293 milliseconds
```

The median is **1,053 ms**. This measures a portion of the interaction pipeline: finalized transcript → first scheduled audio buffer. It is not user-speech-end → audible response, and it does not establish acoustic playback latency.

The session also recorded four learned turn-completion decisions at 333–345 ms after speech end, three timeout completions, five interruption-triggered TTS cancellations, and two completed speech streams. The seven turns were therefore not seven uninterrupted responses.

## Configuration

| Component | Recorded path |
| --- | --- |
| Speech recognition | Parakeet EOU 120M, Core ML, 160 ms configuration |
| Language model | Gemma E2B, LiteRT-LM |
| Voice activity detection | Silero, Core ML |
| Turn completion | WhisperTinyDualScale |
| Speech synthesis | Supertonic 3, Core ML, F1 voice |
| Audio I/O | Shared AVAudioEngine, voice processing enabled |

## Interpreting the evolution

The earlier Raspberry Pi system and this phone session differ in hardware, models, prompts, response lengths, and timing definitions. They demonstrate the project's progression, but they do not support a numerical speedup ratio. A matched test with acoustic timestamps would be needed for an end-to-end latency comparison.

The next useful evaluation is a repeatable set of pauses and interruptions, including false interruptions from the assistant's own audio, with device configuration and speech-end-to-audible-response timing reported together.

[Download the aggregate measurements](voice-results.json) · [Back to Artemis](../README.md)
