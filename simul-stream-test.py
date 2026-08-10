#!/usr/bin/env python3 
from whisper_online import *
import pyaudio
import time
import asyncio

src_lan = "en"  # source language
tgt_lan = "en"  # target language  -- same as source for ASR, "en" if translate task is used

asr = FasterWhisperASR(lan, "large-v2")  # loads and wraps Whisper model
# set options:
# asr.set_translate_task()  # it will translate from lan into English
# asr.use_vad()  # set using VAD

online = OnlineASRProcessor(asr)  # create processing object with default buffer trimming option

# Setup parameters
CHUNK = 1024 # Size of the frame ? 
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100  # Rate of frames sent per second ? 

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open stream for input
stream = p.open(
    format=FORMAT,
    channels=CHANNELS,
    rate=RATE,
    input=True,
    frames_per_buffer=CHUNK,
)

print("Listening...")


try: 

    while audio_has_not_ended:   # processing loop:
        a = stream.read(CHUNK, exception_on_overflow=False)# receive new audio chunk (and e.g. wait for min_chunk_size seconds first, ...)
        online.insert_audio_chunk(a)
        o = online.process_iter()
        print(o) # do something with current partial output at the end of this audio processing

    o = online.finish() # end of audio processing ? 
    print(o)  # do something with the last output


    # restarts execution loop ? 
    online.init()  # refresh if you're going to re-use the object for the next audio

# Standard exception to kill the program with ctrl+c 
except KeyboardInterrupt:
    print("Stopping...") 


finally:
    stream.stop_stream() # Cleanup , cleanup , everybody clap your hands 
    stream.close() 
    p.terminate() # Close the pyaudio 
