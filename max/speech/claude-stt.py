#!/usr/bin/env python3 

import asyncio, numpy as np, sounddevice as sd
import httpx
import pyaudio
import json
from faster_whisper import WhisperModel
from silero_vad import load_silero_vad, VADIterator
import tempfile 
import soundfile as sf

SAMPLE_RATE = 16000
FRAME_MS = 30
#FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
FRAME_SAMPLES = 512 

model = WhisperModel("large-v3", device="cuda", compute_type="float16")
# Capture microphone audio , place each 30 ms chunk into frame_q 
async def mic_producer(frame_q: asyncio.Queue):

    def enqueue_frame(frame):
        if frame_q.full(): # checks if the queue is full 
            try:
                frame_q.get_nowait() # gets frame from the queue 
            except asyncio.QueueEmpty:
                pass

        frame_q.put_nowait(frame) # adds frame to queue 

    # Called automatically by soundevice whenever another microphone chunk is available 
    try: 
        loop = asyncio.get_running_loop()
    
    except RuntimeError:
        print("No loop actively running")

    def callback(indata, frames, time, status):
        if status:
            print(status)

        try:
            loop.call_soon_threadsafe(
                enqueue_frame, # Helper function 
                indata.copy(),
            )
        except RuntimeError:
            print("No loop actively running")

    with sd.InputStream(
        samplerate=SAMPLE_RATE, 
        channels=1,
        dtype="float32",
        blocksize=FRAME_SAMPLES, callback=callback
    ):
            await asyncio.Future()  # keep stream open forever

# Speech detection 
async def vad_stage(
    frame_q: asyncio.Queue,
    segment_q: asyncio.Queue
):
    buf = []
    in_speech = False

    vad_iterator = VADIterator(
        load_silero_vad(onnx=True),
        sampling_rate=SAMPLE_RATE,
        threshold=0.5,
        min_silence_duration_ms=700,
    )

    while True:
        frame = await frame_q.get()

        # sounddevice gives (512, 1)
        # Silero wants (512,)
        frame = np.asarray(
            frame,
            dtype=np.float32
        ).reshape(-1)

        event = vad_iterator(
            frame,
            return_seconds=True
        )

        # If we're already inside speech,
        # keep EVERY frame.
        if in_speech:
            buf.append(frame)

        # Speech just started.
        if event and "start" in event:
            print("Speech started")

            in_speech = True

            # Start buffer with current frame.
            buf = [frame]

        # Speech just ended.
        elif event and "end" in event and in_speech:
            print("Speech ended")

            audio = np.concatenate(buf)

            print("VAD OUT shape:", audio.shape)
            print(
                "VAD OUT duration:",
                len(audio) / SAMPLE_RATE
            )

            await segment_q.put(audio)

            buf = []
            in_speech = False

# TODO: verify this function is actually running 

async def stt_stage(segment_q: asyncio.Queue, transcript_q: asyncio.Queue):
    loop = asyncio.get_running_loop()

    while True:
        audio = await segment_q.get()

        audio = np.asarray(
                audio,
                dtype=np.float32,
                ).reshape(-1)

        print("shape:", audio.shape)
        print("range:", audio.min(), audio.max())
        print("duration:", len(audio) / SAMPLE_RATE)

        # Ignore tiny fragments
        if len(audio) < SAMPLE_RATE // 2:
            print("Skipping segment: too short")
            continue

        segments, info = await loop.run_in_executor(
                None,
                lambda: model.transcribe(
                    audio,
                    language="en",
                    task="transcribe",
                    beam_size=5,
                    no_speech_threshhold=0.6,
                    condition_on_previous_text=False,
                    ),
                )


        text = " ".join(
                segment.text.strip()
                for segment in segments
                ).strip()

        print("Transcript:", text)

        if text:
            await transcript_q.put(text)

async def llm_stage(transcript_q: asyncio.Queue, token_q: asyncio.Queue):
    async with httpx.AsyncClient(timeout=None) as client:
        print("Making POST request to Model... ")
        while True:
            prompt = await transcript_q.get()
            async with client.stream(
                "POST", "http://localhost:11434/api/generate",
                json={"model": "qwen3:8b", "prompt": prompt, "stream": True},
            ) as resp:
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    chunk = json.loads(line)
                    await token_q.put(chunk.get("response", ""))
                    if chunk.get("done"):
                        await token_q.put(None)  # end-of-turn sentinel

async def output_stage(token_q: asyncio.Queue):
    while True:
        tok = await token_q.get()
        if tok is None:
            print()  # utterance complete
            continue
        print(tok, end="", flush=True)   # or hand to a streaming TTS stage

async def main():
    # Sets limit for bounded queue 
    frame_q, segment_q, transcript_q, token_q = (asyncio.Queue(maxsize=n) for n in (20, 8, 4, 256))
    await asyncio.gather(
        mic_producer(frame_q),
        vad_stage(frame_q, segment_q),
        stt_stage(segment_q, transcript_q),
        llm_stage(transcript_q, token_q),
        output_stage(token_q),
    )

asyncio.run(main())
