#!/usr/bin/env python3 
import numpy as np
import sounddevice as sd

# --- Configuration ---
SAMPLE_RATE = 16000  # Matches Whisper's required native rate
BLOCK_SIZE = 1000    # How often the meter updates (lower = faster updates)

print("Available Audio Devices:")
print(sd.query_devices())
print("-" * 50)
print(f"Using default input device: {sd.query_devices(kind='input')['name']}")
print("Speak into your mic to test input. Press Ctrl+C to exit.")
print("-" * 50)

def print_volume_meter(indata, frames, time, status):
    """Callback function that calculates audio amplitude and prints a meter."""
    if status:
        print(status)
    
    # Calculate root-mean-square (RMS) to determine volume levels
    volume_norm = np.linalg.norm(indata) * 10
    magnitude = int(volume_norm)
    
    # Draw a visual level bar in the terminal window
    bar = "█" * magnitude
    # Clear the current line and redraw the live meter
    print(f"Volume: {magnitude:3d} {bar:<50}", end="\r")

try:
    # Open the stream with the microphone callback function
    with sd.InputStream(callback=print_volume_meter, channels=1, samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE):
        while True:
            sd.sleep(100)
except KeyboardInterrupt:
    print("\n\nTest finished.")

