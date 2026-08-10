#!/usr/bin/env python3 

import asyncio, numpy as np, sounddevice as sd
from faster_whisper import WhisperModel
import httpx

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000

model = WhisperModel("small.en", device="cuda", compute_type="float16")

async def mic_producer(frame_q: asyncio.Queue):
    loop = asyncio.get_running_loop()
    def callback(indata, frames, time, status):
        loop.call_soon_threadsafe(frame_q.put_nowait, indata.copy())
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                         blocksize=FRAME_SAMPLES, callback=callback):
        await asyncio.Future()  # keep stream open forever

async def vad_stage(frame_q: asyncio.Queue, segment_q: asyncio.Queue):
    buf, in_speech = [], False
    while True:
        frame = await frame_q.get()
        is_voice = simple_vad(frame)          # webrtcvad / silero, cheap enough for inline
        if is_voice:
            buf.append(frame); in_speech = True
        elif in_speech:
            await segment_q.put(np.concatenate(buf))
            buf, in_speech = [], False

async def stt_stage(segment_q: asyncio.Queue, transcript_q: asyncio.Queue):
    loop = asyncio.get_running_loop()
    while True:
        audio = await segment_q.get()
        # offload the CPU/GPU-heavy call so it doesn't block the loop
        segments, _ = await loop.run_in_executor(
            None, lambda: model.transcribe(audio, beam_size=1))
        text = "".join(s.text for s in segments)
        if text.strip():
            await transcript_q.put(text)

async def llm_stage(transcript_q: asyncio.Queue, token_q: asyncio.Queue):
    async with httpx.AsyncClient(timeout=None) as client:
        while True:
            prompt = await transcript_q.get()
            async with client.stream(
                "POST", "http://localhost:11434/api/generate",
                json={"model": "llama3", "prompt": prompt, "stream": True},
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
    frame_q, segment_q, transcript_q, token_q = (asyncio.Queue(maxsize=n) for n in (64, 8, 4, 256))
    await asyncio.gather(
        mic_producer(frame_q),
        vad_stage(frame_q, segment_q),
        stt_stage(segment_q, transcript_q),
        llm_stage(transcript_q, token_q),
        output_stage(token_q),
    )

asyncio.run(main())
