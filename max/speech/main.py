#!/usr/bin/env python3 

import asyncio, numpy as np, sounddevice as sd
import json 
from faster_whisper import WhisperModel
import httpx
import pyaudio
from silero_vad import load_silero_vad, VADIterator
SAMPLE_RATE = 16000
FRAME_MS = 30
#FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_SAMPLES = 512 # Silero VAD expects 512 samples per inference 
model = WhisperModel("large-v3", device_index=0,device="cuda", compute_type="float32")
# Capture microphone audio , place each 30 ms chunk into frame_q 
async def mic_producer(frame_q: asyncio.Queue):
    loop = asyncio.get_running_loop()
    # Called automatically by soundevice whenever another microphone chunk is available 
    def callback(indata, frames, time, status):
        if status:
            print(status)


        ''' 
        notes: 

        call_soon_threadsafe(): takes frame_q as input and schedules function callback to run on event loop on a different OS thread
        indata.copy() : safely duplicates a numpy buffer before background thread modification , prevents race conditions 
        asyncio.get_running_loop(): schedules downstream async tasks 

        '''

        try:
            # new OS thread , sched callback function 
            loop.call_soon_threadsafe(frame_q.put_nowait, indata.copy())
        except RuntimeError:
            print("No loop actively running")

    
    with sd.InputStream(
        samplerate=SAMPLE_RATE, 
        channels=1,
        dtype="float32",
        blocksize=FRAME_SAMPLES,
        callback=callback
    ):
            await asyncio.Future()  # keep stream open forever

# Speech detection 
async def vad_stage(frame_q: asyncio.Queue, segment_q: asyncio.Queue):
    buf, in_speech = [], False

    vad_iterator = VADIterator(
        load_silero_vad(onnx=True), # Load the model 
        sampling_rate=SAMPLE_RATE, # Sets sampling rate 
        threshold=0.5, # sets threshhold 
        min_silence_duration_ms=700, # min secs of silence 
    )
    while True:
        # Silero expects 1D array , flatten the array  
        frame = np.asarray(await frame_q.get(), dtype=np.float32).reshape(-1) # gets recent frame in frame_q , or "microphone" chunk 

        # Testing for what the frame looks like  , remove later 
        print(
        "VAD frame:",
        frame.shape,
        frame.dtype,
        len(frame),
        )

        is_voice = vad_iterator( # 
                frame,
                return_seconds=True
                )

        if is_voice: 
            buf.append(frame); in_speech = True # Checks for received frame from vad_iterator 
        elif in_speech:
            await segment_q.put(np.concatenate(buf)) # concatenates frames in buffer , puts in segment queue 
            buf, in_speech = [], False

'''notes:
run_in_executor(): Runs sync blocking code in async event loop without freezing , sends heavy or slow task to separate thread pool or process pool making synchro functions awaitable 
'''
async def stt_stage(segment_q: asyncio.Queue, transcript_q: asyncio.Queue):
    loop = asyncio.get_running_loop()
    while True:
        audio = await segment_q.get() # Grabs segment from async Queue 
        # offload the CPU/GPU-heavy call so it doesn't block the loop
        segments, _ = await loop.run_in_executor( 
            None, lambda: model.transcribe(audio, beam_size=1)) # Transcribes the audio using the WhisperModel 
        text = "".join(s.text for s in segments)
        if text.strip():
            await transcript_q.put(text) # Adds transcribed text into transcribe queue 

async def llm_stage(transcript_q: asyncio.Queue, token_q: asyncio.Queue):
    async with httpx.AsyncClient(timeout=None) as client: # Creates async http client 
        while True:
            prompt = await transcript_q.get() # Grabs data from transcript queue 
            async with client.stream(  # Http connection attempt 
                "POST", "http://localhost:11434/api/generate",
                json={"model": "qwen3:8b", "prompt": prompt, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line) # loads json response from Http client 
                    await token_q.put(chunk.get("response", "")) # adds data from json object into token_q
                    if chunk.get("done"): # once tokens are added , adds None to signal end of processing 
                        await token_q.put(None)  # end-of-turn sentinel

# Gets llm output from prompt a.k.a the token_q 
async def output_stage(token_q: asyncio.Queue):
    while True:
        tok = await token_q.get() # Gets recent data from token_q 
        if tok is None:
            print()  # utterance complete
            continue
        print(tok, end="", flush=True)   # or hand to a streaming TTS stage

async def main():
    # Sets limit for bounded queue 
    frame_q, segment_q, transcript_q, token_q = (asyncio.Queue(maxsize=n) for n in (64, 8, 4, 256))
    await asyncio.gather(
        mic_producer(frame_q),
        vad_stage(frame_q, segment_q),
        stt_stage(segment_q, transcript_q),
        llm_stage(transcript_q, token_q),
        output_stage(token_q),
    )

if __name__ == '__main__':
    asyncio.run(main())
