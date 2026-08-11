import asyncio

import numpy as np
import pytest

from max.speech import main


class FakeVADIterator:
    """
    Fake replacement for Silero's VADIterator.

    Each call returns the next predefined VAD result.
    """

    responses = []
    calls = []
    init_kwargs = None
    model = None

    def __init__(self, model, **kwargs):
        FakeVADIterator.model = model
        FakeVADIterator.init_kwargs = kwargs
        FakeVADIterator.calls = []

    def __call__(self, frame, return_seconds=False):
        FakeVADIterator.calls.append(
            {
                "frame": frame,
                "return_seconds": return_seconds,
            }
        )

        if FakeVADIterator.responses:
            return FakeVADIterator.responses.pop(0)

        return None


@pytest.fixture
def fake_vad(monkeypatch):
    """
    Replace Silero model loading and VADIterator with fake versions.
    """

    fake_model = object()

    FakeVADIterator.responses = []
    FakeVADIterator.calls = []
    FakeVADIterator.init_kwargs = None
    FakeVADIterator.model = None

    monkeypatch.setattr(
        main,
        "load_silero_vad",
        lambda onnx=True: fake_model,
    )

    monkeypatch.setattr(
        main,
        "VADIterator",
        FakeVADIterator,
    )

    return FakeVADIterator


@pytest.mark.asyncio
async def test_vad_stage_creates_iterator_with_expected_settings(fake_vad):
    frame_q = asyncio.Queue()
    segment_q = asyncio.Queue()

    task = asyncio.create_task(
        main.vad_stage(frame_q, segment_q)
    )

    # Give vad_stage() time to construct VADIterator and block on frame_q.get().
    await asyncio.sleep(0)

    assert fake_vad.init_kwargs is not None

    assert (
        fake_vad.init_kwargs["sampling_rate"]
        == main.SAMPLE_RATE
    )

    assert fake_vad.init_kwargs["threshold"] == 0.5

    assert (
        fake_vad.init_kwargs["min_silence_duration_ms"]
        == 700
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_vad_stage_passes_frame_to_vad(fake_vad):
    frame_q = asyncio.Queue()
    segment_q = asyncio.Queue()

    fake_vad.responses = [None]

    task = asyncio.create_task(
        main.vad_stage(frame_q, segment_q)
    )

    await asyncio.sleep(0)

    frame = np.array(
        [0.1, 0.2, 0.3],
        dtype=np.float32,
    )

    await frame_q.put(frame)

    await asyncio.sleep(0)

    assert len(fake_vad.calls) == 1

    np.testing.assert_array_equal(
        fake_vad.calls[0]["frame"],
        frame,
    )

    assert (
        fake_vad.calls[0]["return_seconds"]
        is True
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_silence_before_speech_does_not_create_segment(fake_vad):
    frame_q = asyncio.Queue()
    segment_q = asyncio.Queue()

    fake_vad.responses = [
        None,
        None,
        None,
    ]

    task = asyncio.create_task(
        main.vad_stage(frame_q, segment_q)
    )

    await asyncio.sleep(0)

    for _ in range(3):
        await frame_q.put(
            np.zeros(512, dtype=np.float32)
        )

    # Allow all queued frames to be processed.
    for _ in range(3):
        await asyncio.sleep(0)

    assert segment_q.empty()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_single_speech_frame_creates_segment_after_silence(fake_vad):
    frame_q = asyncio.Queue()
    segment_q = asyncio.Queue()

    # First frame = speech
    # Second frame = silence
    fake_vad.responses = [
        {"start": 0.0},
        None,
    ]

    task = asyncio.create_task(
        main.vad_stage(frame_q, segment_q)
    )

    await asyncio.sleep(0)

    speech_frame = np.array(
        [0.1, 0.2, 0.3],
        dtype=np.float32,
    )

    silence_frame = np.zeros(
        3,
        dtype=np.float32,
    )

    await frame_q.put(speech_frame)
    await frame_q.put(silence_frame)

    segment = await asyncio.wait_for(
        segment_q.get(),
        timeout=1,
    )

    np.testing.assert_array_equal(
        segment,
        speech_frame,
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_multiple_speech_frames_are_concatenated(fake_vad):
    frame_q = asyncio.Queue()
    segment_q = asyncio.Queue()

    fake_vad.responses = [
        {"start": 0.0},
        {"speech": True},
        {"speech": True},
        None,
    ]

    task = asyncio.create_task(
        main.vad_stage(frame_q, segment_q)
    )

    await asyncio.sleep(0)

    frame_1 = np.array(
        [0.1, 0.2],
        dtype=np.float32,
    )

    frame_2 = np.array(
        [0.3, 0.4],
        dtype=np.float32,
    )

    frame_3 = np.array(
        [0.5, 0.6],
        dtype=np.float32,
    )

    silence_frame = np.zeros(
        2,
        dtype=np.float32,
    )

    await frame_q.put(frame_1)
    await frame_q.put(frame_2)
    await frame_q.put(frame_3)
    await frame_q.put(silence_frame)

    segment = await asyncio.wait_for(
        segment_q.get(),
        timeout=1,
    )

    expected = np.concatenate(
        [
            frame_1,
            frame_2,
            frame_3,
        ]
    )

    np.testing.assert_array_equal(
        segment,
        expected,
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_buffer_resets_after_segment(fake_vad):
    frame_q = asyncio.Queue()
    segment_q = asyncio.Queue()

    fake_vad.responses = [
        {"start": 0.0},
        None,
        {"start": 1.0},
        None,
    ]

    task = asyncio.create_task(
        main.vad_stage(frame_q, segment_q)
    )

    await asyncio.sleep(0)

    first_speech = np.array(
        [0.1, 0.2],
        dtype=np.float32,
    )

    first_silence = np.zeros(
        2,
        dtype=np.float32,
    )

    second_speech = np.array(
        [0.7, 0.8],
        dtype=np.float32,
    )

    second_silence = np.zeros(
        2,
        dtype=np.float32,
    )

    await frame_q.put(first_speech)
    await frame_q.put(first_silence)
    await frame_q.put(second_speech)
    await frame_q.put(second_silence)

    segment_1 = await asyncio.wait_for(
        segment_q.get(),
        timeout=1,
    )

    segment_2 = await asyncio.wait_for(
        segment_q.get(),
        timeout=1,
    )

    np.testing.assert_array_equal(
        segment_1,
        first_speech,
    )

    np.testing.assert_array_equal(
        segment_2,
        second_speech,
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_no_segment_until_speech_has_started(fake_vad):
    frame_q = asyncio.Queue()
    segment_q = asyncio.Queue()

    fake_vad.responses = [
        None,
        None,
    ]

    task = asyncio.create_task(
        main.vad_stage(frame_q, segment_q)
    )

    await asyncio.sleep(0)

    await frame_q.put(
        np.zeros(512, dtype=np.float32)
    )

    await frame_q.put(
        np.zeros(512, dtype=np.float32)
    )

    await asyncio.sleep(0)
    await asyncio.sleep(0)

    assert segment_q.empty()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
