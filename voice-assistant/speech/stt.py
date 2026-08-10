#!/usr/bin/env python3 
import numpy as np
import pyaudio
from faster_whisper import WhisperModel

# --- Configuration ---
# Options: "tiny", "base", "small", "medium", "large-v3"
# Use "tiny" or "base" for the lowest latency on standard CPUs
MODEL_SIZE = "base" 
DEVICE = "cpu"       # Change to "cuda" if you have an NVIDIA GPU

# Audio recording settings
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000         # Whisper models strictly expect 16kHz audio
CHUNK_SIZE = 1024    # Number of frames per read
RECORD_SECONDS = 3   # How often to chunk and process audio (latency window)

def main():
    print("Loading Whisper model...")
    # Initialize the model with float32 computation on CPU (or float16 on GPU)
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type="float32")
    print("Model loaded successfully.")

    # Initialize PyAudio
    audio_interface = pyaudio.PyAudio()
    
    # Open the microphone stream
    stream = audio_interface.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE
    )

    print("\n---> Start speaking... (Press Ctrl+C to stop) <---")
    
    # Keep track of transcription context
    audio_buffer = []

    try:
        while True:
            # 1. Capture audio in chunks matching our chunk window duration
            frames = []
            for _ in range(0, int(RATE / CHUNK_SIZE * RECORD_SECONDS)):
                data = stream.read(CHUNK_SIZE, exception_on_overflow=False)
                frames.append(data)

            # 2. Convert raw byte data into a NumPy float32 array
            raw_bytes = b"".join(frames)
            audio_np = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0

            # 3. Feed the audio array directly to Whisper
            # beam_size=1 provides the fastest possible transcription speeds
            segments, info = model.transcribe(audio_np, beam_size=1, language="en")

            # 4. Print results in real time
            for segment in segments:
                if segment.text.strip():
                    print(f"[{segment.start:.1f}s -> {segment.end:.1f}s]: {segment.text}")

    except KeyboardInterrupt:
        print("\nStopping stream...")
    finally:
        # Clean up audio resources safely
        stream.stop_stream()
        stream.close()
        audio_interface.terminate()
        print("Stream closed.")

if __name__ == "__main__":
    main()
