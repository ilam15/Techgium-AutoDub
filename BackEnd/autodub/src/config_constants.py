# config_constants.py
# Centralized constants to avoid magic numbers and strings

# Redis Key Templates
PIPELINE_KEY_TEMPLATE = "pipeline:{trace_id}"
PIPELINE_RESULTS_KEY_TEMPLATE = "pipeline:{trace_id}:results"
ASSEMBLER_LOCK_TEMPLATE = "assembler_lock:{trace_id}"
TASK_TRACE_MAP_TEMPLATE = "task:{task_id}:trace"

# Pipeline & VAD Constants
VAD_MIN_SILENCE_DURATION_MS = 400
VAD_SPEECH_PAD_MS = 250
VAD_THRESHOLD = 0.4
VAD_MIN_SPEECH_DURATION_MS = 400
VAD_MAX_SPEECH_DURATION_S = 12

SEGMENT_MIN_DURATION = 0.5
SEGMENT_MAX_DURATION = 10.0
SEGMENT_MIN_GAP_MERGE = 0.25
SEGMENT_MIN_DURATION_MERGE = 1.5  # Added for forcing merges of short segments

# Hallucination & Filter Constants
HALLUCINATION_NO_SPEECH_PROB = 0.6
HALLUCINATION_LOGPROB_THRESHOLD = -1.0
DUPLICATE_SIMILARITY_THRESHOLD = 0.8
MIN_TEXT_LENGTH = 2

BANNED_PHRASES = [
    "subtitles by",
    "copyright",
    "amara.org",
    "community",
    "subscribe",
    "captioned by",
    "al-jazeera"
]

# Redis TTL
PIPELINE_TTL = 3600  # 1 hour
LOCK_TTL = 300       # 5 minutes

# Language Detection
LANG_DETECT_AUDIO_THRESHOLD = 0.50
LANG_DETECT_TEXT_THRESHOLD = 0.85

# Feature Flags
ENABLE_TORCHCODEC = False
