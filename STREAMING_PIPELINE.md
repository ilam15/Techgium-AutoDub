# STREAMING PIPELINE ARCHITECTURE

## The Key Difference

### ❌ OLD APPROACH (Batch Processing)
```
ASR finds ALL segments first:
[Seg 1] [Seg 2] [Seg 3] [Seg 4] ... [Seg 20]
   ↓
Wait for ALL segments to be found
   ↓
THEN start processing in parallel:
[Seg 1: Translate→TTS] [Seg 2: Translate→TTS] ...
```

### ✅ NEW APPROACH (Streaming/Pipelined)
```
Time 0s:  ASR finds Seg 1 → IMMEDIATELY start Translate→TTS for Seg 1
          ↓ (ASR continues...)
Time 2s:  ASR finds Seg 2 → IMMEDIATELY start Translate→TTS for Seg 2
          ↓ (ASR continues...)
Time 4s:  ASR finds Seg 3 → IMMEDIATELY start Translate→TTS for Seg 3
          ↓ (ASR continues...)
...

All happening SIMULTANEOUSLY:
- ASR is finding new segments
- Earlier segments are being translated
- Even earlier segments are generating TTS
```

## Visual Timeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    STREAMING PIPELINE                            │
└─────────────────────────────────────────────────────────────────┘

Time →
0s ────────────────────────────────────────────────────────────→ 60s

ASR:      [Seg1][Seg2][Seg3][Seg4][Seg5]...[Seg20]
           ↓     ↓     ↓     ↓     ↓        ↓
Translate:  [T1]  [T2]  [T3]  [T4]  [T5]    [T20]
             ↓     ↓     ↓     ↓     ↓        ↓
TTS:         [TTS1][TTS2][TTS3][TTS4][TTS5]  [TTS20]

Legend:
[Seg1] = ASR detects segment 1
[T1]   = Translate segment 1
[TTS1] = Generate TTS for segment 1

Notice: Everything flows continuously!
- While Seg 1 is being translated, ASR is finding Seg 2
- While Seg 1 TTS is generating, Seg 2 is translating, ASR is finding Seg 3
```

## How It Works

### 1. **ASR Streams Segments**
```python
for chunk in audio_chunks:
    segments = whisper.transcribe(chunk)
    
    for seg in segments:
        # DON'T WAIT! Launch processing immediately
        process_single_segment_task.apply_async(seg)
        # ↑ This returns immediately, doesn't block
```

### 2. **Each Segment Processes Independently**
```python
def process_single_segment_task(segment):
    # 1. Detect language (already done)
    # 2. Decide: TRANSLATE or KEEP
    # 3. If TRANSLATE:
    translated = translate(segment.text)
    tts_audio = generate_tts(translated)  # Queued to TTS worker
    return segment_with_tts
```

### 3. **TTS Queue Handles Concurrency**
```
TTS Worker (concurrency=4):

Slot 1: [Generating TTS for Seg 1]
Slot 2: [Generating TTS for Seg 2]
Slot 3: [Generating TTS for Seg 3]
Slot 4: [Generating TTS for Seg 4]

When Slot 1 finishes → Seg 5 starts immediately
When Slot 2 finishes → Seg 6 starts immediately
...
```

## Performance Improvement

### Example: 2-minute video, 20 segments

**OLD BATCH APPROACH:**
```
1. ASR all segments:        20s
2. Wait for all ASR done    ← BOTTLENECK
3. Translate all (parallel): 5s
4. TTS all (4 concurrent):  150s (20 segments ÷ 4 = 5 batches × 30s)
5. Merge:                   10s
─────────────────────────────
TOTAL:                      185s (~3 minutes)
```

**NEW STREAMING APPROACH:**
```
Timeline:
0-20s:   ASR finds segments 1-20
         └→ Seg 1 starts translating at 2s
         └→ Seg 2 starts translating at 4s
         └→ ...

2-7s:    Seg 1 translates (5s)
         └→ Seg 1 starts TTS at 7s

4-9s:    Seg 2 translates (5s)
         └→ Seg 2 starts TTS at 9s

7-37s:   Seg 1 TTS (30s)
9-39s:   Seg 2 TTS (30s)
11-41s:  Seg 3 TTS (30s)
13-43s:  Seg 4 TTS (30s)
...

Last segment (Seg 20):
- Starts translating at ~40s
- Starts TTS at ~45s
- Finishes TTS at ~75s

Merge: 75-85s
─────────────────────────────
TOTAL: ~85s (~1.5 minutes)
```

**SPEEDUP: 2x faster!** 🚀

## Key Advantages

### 1. **No Waiting**
- Old: ASR must finish ALL segments before ANY processing starts
- New: Processing starts as SOON as first segment is detected

### 2. **Better Resource Utilization**
- Old: CPU idle during ASR, then busy during TTS
- New: CPU always busy (ASR + Translation + TTS all happening)

### 3. **Faster Feedback**
- Old: User waits for entire ASR to complete
- New: Progress updates start immediately

### 4. **Scalable**
- Old: Limited by batch size
- New: Unlimited segments, all stream through

## Code Flow

```python
# MAIN ORCHESTRATOR
streaming_asr_and_process_task():
    
    # Start diarization in background thread
    threading.Thread(run_diarization).start()
    
    segment_tasks = []
    
    # Stream through audio chunks
    for chunk in audio_chunks:
        segments = whisper.transcribe(chunk)
        
        for seg in segments:
            # IMMEDIATELY launch processing (non-blocking)
            task = process_single_segment_task.apply_async(seg)
            segment_tasks.append(task)
            # ↑ Returns immediately, doesn't wait!
    
    # Now wait for ALL tasks to complete
    results = [task.get() for task in segment_tasks]
    
    return results

# SEGMENT PROCESSOR (runs in parallel for each segment)
process_single_segment_task(segment):
    
    # Decide if translation needed
    if should_translate:
        translated = translate(segment.text)
        
        # Launch TTS (queued to TTS worker)
        tts_task = generate_tts_task.apply_async(
            segment, 
            queue='tts'  # Goes to TTS queue
        )
        
        # Wait for TTS to finish
        tts_path = tts_task.get()
        
    return segment_with_tts

# TTS GENERATOR (runs on TTS worker with concurrency=4)
generate_tts_task(segment):
    tts_audio = your_tts(segment.translated_text)
    return tts_audio_path
```

## Configuration

### Celery Workers

**Default Worker** (handles ASR, translation, orchestration):
```bash
celery -A src.core.celery_app worker --loglevel=info -Q default -P solo
```

**TTS Worker** (handles TTS generation with 4 concurrent slots):
```bash
celery -A src.core.celery_app worker --loglevel=info -Q tts -P solo --concurrency=4
```

### Why This Works

1. **ASR runs on Default Worker** (single-threaded, sequential)
2. **Translation runs on Default Worker** (can handle multiple segments)
3. **TTS runs on TTS Worker** (4 concurrent slots)

The magic is in `apply_async()` which:
- Returns immediately (non-blocking)
- Queues the task for background execution
- Allows ASR to continue finding more segments

## Monitoring

Watch your terminal windows:

**DEFAULT_WORKER:**
```
[trace] 📍 Segment 0 detected at 0.50s - LAUNCHING PROCESSING
[trace] 📍 Segment 1 detected at 2.30s - LAUNCHING PROCESSING
[trace] 📍 Segment 2 detected at 4.10s - LAUNCHING PROCESSING
[trace] Seg 0: TRANSLATE English → Spanish
[trace] Seg 0: 'Hello world' → 'Hola mundo'
[trace] Seg 1: TRANSLATE English → Spanish
...
```

**TTS_WORKER:**
```
[trace] Seg 0: TTS complete
[trace] Seg 1: TTS complete
[trace] Seg 2: TTS complete
[trace] Seg 3: TTS complete  ← These appear rapidly!
```

## Troubleshooting

### Issue: Segments still processing sequentially
**Check:** TTS_WORKER should show `concurrency: 4` on startup

### Issue: Out of memory
**Solution:** Reduce TTS concurrency:
```bash
--concurrency=2  # For 4GB RAM
```

### Issue: Tasks timing out
**Solution:** Increase timeout in `process_single_segment_task`:
```python
tts_result = tts_task.get(timeout=300)  # 5 minutes
```

## Summary

This is **true streaming parallelism**:
- ASR produces segments continuously
- Each segment processes immediately (doesn't wait)
- Multiple segments process simultaneously
- Result: **2x faster** than batch approach!
