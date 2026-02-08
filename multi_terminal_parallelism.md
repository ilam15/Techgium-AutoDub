# DISTRIBUTED PARALLEL ARCHITECTURE (Multi-Terminal)

## How the Factory Line Works

We have split the processing into **5 separate stations** (terminals). Each station is its own process, meaning they all work **at the same time**.

### **The 5 Terminals:**

| Terminal | Name | Task | Parallelism |
| :--- | :--- | :--- | :--- |
| **Terminal 1** | `ASR_WORKER` | Extracts audio & finds segments | Processes chunks sequentially |
| **Terminal 2** | `RECOG_WORKER` | Identifies Speaker & Gender | Up to 5 segments at once |
| **Terminal 3** | `TRANS_WORKER` | Local NLLB Translation | Up to 5 segments at once |
| **Terminal 4** | `TTS_WORKER` | Generates Voice (CPU) | Up to 4 segments at once |
| **Terminal 5** | `MERGE_WORKER` | Final Video Assembly | Sequential processing |

---

## **Streaming Flow Example**

For a video with 20 segments, the "simultaneous" flow looks like this:

1. **ASR (T1)** finds Segment 0 and pushes it to **RECOG (T2)**.
2. While **T1** is finding Segment 1...
3. **RECOG (T2)** identifies Segment 0 and pushes it to **TRANS (T3)**.
4. While **T1** is finding Segment 2...
5. **RECOG (T2)** identify Segment 1...
6. **TRANS (T3)** translates Segment 0 and pushes it to **TTS (T4)**.

**Result**: Within 30 seconds, ALL 5 terminals are active!
* T1 is finding new segments.
* T2 is identifying genders.
* T3 is translating.
* T4 is generating voices.
* T5 is waiting to merge.

---

## **Key Benefits**

* **Zero Waiting**: Segment 5 does not wait for Segment 1 to be dubbed. It starts its journey through the "factory" as soon as it's discovered.
* **CPU Efficiency**: Each stage uses its own worker thread pool.
* **Transparency**: You can literally watch the segments "hop" from one terminal window to the next in real-time.

---

## **Launching the Stack**

To see this in action:
1. Close all current terminal windows.
2. Run `run_autodub.bat`.
3. Watch the **7 new windows** open (Redis, API, and 5 Production Terminals).

## **Expected Logs**

### Terminal 1 (ASR)
`📍 Segment 3 detected - Pushing to terminal_2 (Recognition)`

### Terminal 2 (Recognition)
`terminal_2: Recognition Seg 3`
`Speaker 0 pitch: 120Hz -> Male`

### Terminal 3 (Translation)
`terminal_3: Translation Seg 3`
`'Hello' -> 'Hola'`

### Terminal 4 (TTS)
`terminal_4: TTS Seg 3`
`Sync needed: 1200ms -> 1150ms`

### Terminal 5 (Merge)
`terminal_5: Merge START`
`Merging complex with background ducking`
`✅ Final video ready!`
