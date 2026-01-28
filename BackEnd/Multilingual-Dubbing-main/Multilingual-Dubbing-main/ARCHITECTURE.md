# AutoDub Production Architecture

## 1. Request Lifecycle
1. **API Gateway**: Validates payload size and language codes.
2. **RequestContext**: Generates unique Job ID and Sandbox `/temp/requests/{id}/`.
3. **Audio Domain**: Extract PCM stream from video bits.
4. **ASR Domain**: Concurrent Whisper (Transcription) and Pyannote (Diarization).
5. **Translation Domain**: Batched translation using ID-tag mapping to prevent segment loss.
6. **TTS Domain**: Engine selector (Kokoro/Edge) with prosody-preserving elastic speed control.
7. **Mix/Mux**: Sidechain ducking of background music + Video stream copy.
8. **Cleanup**: Sandbox purged in `finally` loop.

## 2. Fallback Table
| Failure | Fallback Strategy |
| :--- | :--- |
| **GPU OOM** | Model Manager triggers `clear_cache()`, retries on CPU if mandatory. |
| **Diarization Error** | Fallback to `SPEAKER_00` profile for whole video. |
| **Kokoro TTS Down** | Auto-switch to Microsoft Edge TTS Legacy. |
| **Translation Fail** | Return original source language subtitles. |

## 3. Reliability Metrics
- **Integrated Observability**: Every log line contains a `request_id`.
- **Latency Tracking**: Per-stage timing exposed via JSON metrics.
- **Auto-Scale**: stateless design permits horizontal scaling via Kubernetes.
