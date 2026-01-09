## Multilingual-Video-Dubbing
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/NeuralFalconYT//Multilingual-Dubbing/blob/main/Multilingual_Dubbing_latest.ipynb) <br>


[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/NeuralFalconYT//Multilingual-Dubbing/blob/main/Multilingual_Video_Dubbing.ipynb) <br>


### Overview:
The pipeline works as follows:
1. **Speech-to-Text**:
   - Uses the [faster-whisper-large-v3-turbo-ct2](https://huggingface.co/deepdml/faster-whisper-large-v3-turbo-ct2) model to generate subtitles from the original video.
   
2. **Translation**:
   - Translates the generated subtitles into any target language using Google Translate.
   
3. **Text-to-Speech**:
   - Uses the [Edge TTS](https://github.com/rany2/edge-tts) to convert the translated text into speech (Audio).

4. **Background Music Separation**:
   - Extracts the background music from the original audio using `audio-separator[gpu]` to ensure that the original audio effects (if any) are maintained.

5. **Overlaying TTS on Video**:
   - Overlays the generated TTS (translated voice) onto the video, replacing the original audio, using `ffmpeg`.


### License:
This repository is open-source and available under the MIT License.
