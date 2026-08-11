#!/usr/bin/env python3 
import asyncio

import numpy as np
import pytest

from max.speech import main


class FakeInputStream:
    """
    Fake sounddevice.InputStream.

    This prevents pytest from opening the real microphone while still
    allowing us to test the callback used by mic_producer().
    """

    callback = None
    kwargs = None
    entered = False
    exited = False

    def __init__(self, **kwargs):
        FakeInputStream.kwargs = kwargs
        FakeInputStream.callback = kwargs["callback"]

    def __enter__(self):
        FakeInputStream.entered = True
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        FakeInputStream.exited = True
        return False


@pytest.fixture
def fake_input_stream(monkeypatch):
    """
    Replace sounddevice.InputStream inside main.py with our fake stream.
    """

    FakeInputStream.callback = None
    FakeInputStream.kwargs = None
    FakeInputStream.entered = False
    FakeInputStream.exited = False

    monkeypatch.setattr(
        main.sd,
        "InputStream",
        FakeInputStream,
    )

    return FakeInputStream


@pytest.mark.asyncio
async def test_mic_producer_creates_input_stream(fake_input_stream):
    """
    Verify mic_producer creates sounddevice.InputStream
    with the expected configuration.
    """

    frame_q = asyncio.Queue()

    task = asyncio.create_task(
        main.mic_producer(frame_q)
    )

    # Allow mic_producer() to execute until it reaches
    # await asyncio.Future().
    await asyncio.sleep(0)

    assert fake_input_stream.kwargs is not None
    assert fake_input_stream.entered is True

    assert (
        fake_input_stream.kwargs["samplerate"]
        == main.SAMPLE_RATE
    )

    assert (
        fake_input_stream.kwargs["channels"]
        == 1
    )

    assert (
        fake_input_stream.kwargs["dtype"]
        == "float32"
    )

    assert (
        fake_input_stream.kwargs["blocksize"]
        == main.FRAME_SAMPLES
    )

    assert callable(
        fake_input_stream.kwargs["callback"]
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert fake_input_stream.exited is True


@pytest.mark.asyncio
async def test_callback_places_frame_in_queue(fake_input_stream):
    """
    Verify that microphone data received by the sounddevice callback
    is placed into frame_q.
    """

    frame_q = asyncio.Queue()

    task = asyncio.create_task(
        main.mic_producer(frame_q)
    )

    await asyncio.sleep(0)

    frame = np.array(
        [
            [0.1],
            [0.2],
            [0.3],
        ],
        dtype=np.float32,
    )

    # Simulate sounddevice delivering microphone samples.
    fake_input_stream.callback(
        frame,
        len(frame),
        None,
        None,
    )

    # call_soon_threadsafe() schedules put_nowait() on
    # the event loop, so give the loop a chance to run it.
    await asyncio.sleep(0)

    queued_frame = await asyncio.wait_for(
        frame_q.get(),
        timeout=1,
    )

    np.testing.assert_array_equal(
        queued_frame,
        frame,
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_callback_copies_input_buffer(fake_input_stream):
    """
    Verify that indata.copy() is being used.

    sounddevice may reuse its input buffer after the callback returns.
    The queued frame must therefore be independent of the original
    numpy array.
    """

    frame_q = asyncio.Queue()

    task = asyncio.create_task(
        main.mic_producer(frame_q)
    )

    await asyncio.sleep(0)

    frame = np.array(
        [
            [0.25],
            [0.50],
            [0.75],
        ],
        dtype=np.float32,
    )

    expected = frame.copy()

    fake_input_stream.callback(
        frame,
        len(frame),
        None,
        None,
    )

    # Modify the original buffer after the callback.
    frame[:] = 99.0

    await asyncio.sleep(0)

    queued_frame = await asyncio.wait_for(
        frame_q.get(),
        timeout=1,
    )

    np.testing.assert_array_equal(
        queued_frame,
        expected,
    )

    # Make sure it really is a different numpy buffer.
    assert queued_frame is not frame

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_callback_reports_sounddevice_status(
    fake_input_stream,
    capsys,
):
    """
    Verify that a sounddevice status message is printed.
    """

    frame_q = asyncio.Queue()

    task = asyncio.create_task(
        main.mic_producer(frame_q)
    )

    await asyncio.sleep(0)

    frame = np.zeros(
        (main.FRAME_SAMPLES, 1),
        dtype=np.float32,
    )

    fake_input_stream.callback(
        frame,
        len(frame),
        None,
        "input overflow",
    )

    await asyncio.sleep(0)

    captured = capsys.readouterr()

    assert "input overflow" in captured.out

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_multiple_frames_are_queued_in_order(
    fake_input_stream,
):
    """
    Verify that multiple microphone frames arrive in frame_q
    in the same order they were received.
    """

    frame_q = asyncio.Queue()

    task = asyncio.create_task(
        main.mic_producer(frame_q)
    )

    await asyncio.sleep(0)

    frames = [
        np.array([[0.1]], dtype=np.float32),
        np.array([[0.2]], dtype=np.float32),
        np.array([[0.3]], dtype=np.float32),
    ]

    for frame in frames:
        fake_input_stream.callback(
            frame,
            len(frame),
            None,
            None,
        )

    await asyncio.sleep(0)

    results = []

    for _ in frames:
        result = await asyncio.wait_for(
            frame_q.get(),
            timeout=1,
        )

        results.append(result)

    for expected, actual in zip(frames, results):
        np.testing.assert_array_equal(
            actual,
            expected,
        )

    assert frame_q.empty()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_callback_accepts_silent_audio(fake_input_stream):
    """
    Verify that an all-zero audio frame can pass through normally.
    """

    frame_q = asyncio.Queue()

    task = asyncio.create_task(
        main.mic_producer(frame_q)
    )

    await asyncio.sleep(0)

    frame = np.zeros(
        (main.FRAME_SAMPLES, 1),
        dtype=np.float32,
    )

    fake_input_stream.callback(
        frame,
        len(frame),
        None,
        None,
    )

    await asyncio.sleep(0)

    queued_frame = await asyncio.wait_for(
        frame_q.get(),
        timeout=1,
    )

    np.testing.assert_array_equal(
        queued_frame,
        frame,
    )

    assert queued_frame.dtype == np.float32

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
