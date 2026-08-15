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
# Capture microphone audio , place each 30 ms chunk intoraw_frame_q 
async def mic_producer(frame_q: asyncio.Queue):

    def enqueue_frame(frame):
        if raw_frame_q.full(): # checks if the queue is full 
            try:
                raw_frame_q.get_nowait() # gets frame from the queue 
            except asyncio.QueueEmpty:
                pass

        raw_frame_q.put_nowait(frame) # adds frame to queue 

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

async def ffmpeg_filter_stage(
    raw_frame_q: asyncio.Queue,
    filtered_frame_q: asyncio.Queue,
):
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",

        "-hide_banner",
        "-loglevel", "error",

        # Input is raw float32 audio from sounddevice
        "-f", "f32le",
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        "-i", "pipe:0",

        # Speech-oriented band-pass
        "-af", "highpass=f=80,lowpass=f=7500",

        # Output raw float32
        "-f", "f32le",
        "-ar", str(SAMPLE_RATE),
        "-ac", "1",
        "pipe:1",

        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    bytes_per_frame = FRAME_SAMPLES * 4  # float32 = 4 bytes

    async def writer():
        while True:
            frame = await raw_frame_q.get()

            frame = np.asarray(
                frame,
                dtype=np.float32,
            ).reshape(-1)

            process.stdin.write(frame.tobytes())
            await process.stdin.drain()

    async def reader():
        while True:
            data = await process.stdout.readexactly(
                bytes_per_frame
            )

            frame = np.frombuffer(
                data,
                dtype=np.float32,
            ).copy()

            await filtered_frame_q.put(frame)

    await asyncio.gather(
        writer(),
        reader(),
    )
# Speech detection 
# TODO: verify this function is actually running 
async def vad_stage(
    filtered_frame_q: asyncio.Queue,
    segment_q: asyncio.Queue,
):
    buf = []
    in_speech = False

    vad_iterator = VADIterator(
        load_silero_vad(onnx=True),
        sampling_rate=SAMPLE_RATE,
        threshold=0.5,
        min_silence_duration_ms=700,
        temperature=0.0,  # Reduce halluncinations hopefully , more practical 
    )

    while True:
        frame = await filtered_frame_q.get()

        frame = np.asarray(
            frame,
            dtype=np.float32,
        ).reshape(-1)

        event = vad_iterator(
            frame,
            return_seconds=True,
        )

        if in_speech:
            buf.append(frame)

        if event and "start" in event:
            print("Speech started")

            in_speech = True
            buf = [frame]

        elif event and "end" in event and in_speech:
            print("Speech ended")

            audio = np.concatenate(buf)

            print(
                "Segment duration:",
                len(audio) / SAMPLE_RATE,
            )

            await segment_q.put(audio)

            buf = []
            in_speech = False

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
                    no_speech_threshhold=0.6, # hallucination related options 
                    condition_on_previous_text=False,# hallucination related options 
                    hallucination_silence_threshhold=1.0,
                    ),
                )

        text = " ".join(
                segment.text.strip()
                for segment in segments
                ).strip()

        parts = []

        # Filter whisper segments 
        for segment in segments:
            print(
                "text:", repr(segment.text),
                "avg_logprob:", segment.avg_logprob,
                "no_speech_prob:", segment.no_speech_prob,
            )

            if segment.no_speech_prob > 0.6:
                continue

            parts.append(segment.text.strip())

        text = " ".join(parts).strip()
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
    '''
    raw_frame_q, filtered_frame_q,  segment_q, transcript_q, token_q = (asyncio.Queue(maxsize=n) for n in (20,20, 8, 4, 256))
    await asyncio.gather(

        mic_producer(frame_q),
        ffmpeg_filter_stage(
            raw_frame_q,
            filtered_frame_q,
            )
        vad_stage(frame_q, segment_q),
        stt_stage(segment_q, transcript_q),
        llm_stage(transcript_q, token_q),
        output_stage(token_q),
    )

'''
    transcript_q = asyncio.Queue()

    await test_stt_file(
            "/home/buhfur/max/max/speech/test.wav",
            transcript_q, 
        )

asyncio.run(main())

