class AutoDubException(Exception):
    """Base exception for AutoDub Engine"""
    def __init__(self, message: str, stage: str = "unknown"):
        self.stage = stage
        super().__init__(message)

class ASRError(AutoDubException):
    """Raised when transcription fails"""
    pass

class DiarizationError(AutoDubException):
    """Raised when speaker diarization fails"""
    pass

class TranslationError(AutoDubException):
    """Raised when machine translation fails"""
    pass

class TTSError(AutoDubException):
    """Raised when TTS generation fails"""
    pass

class MediaError(AutoDubException):
    """Raised when FFmpeg or audio processing fails"""
    pass

class ValidationError(AutoDubException):
    """Raised when input validation fails"""
    pass
