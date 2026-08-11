import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from max.speech import main


@pytest.mark.asyncio
async def test_stt_stage_transcribes_audio_and_queues_text(monkeypatch):
    segment_q = asyncio.Queue()
    transcript_q = asyncio.Queue()

    fake_segments = [
        SimpleNamespace(text="hello "),
        SimpleNamespace(text="world"),
    ]

    fake_model = MagicMock()
    fake_model.transcribe.return_value = (
        fake_segments,
        {"language": "en"},
    )

    monkeypatch.setattr(
        main,
        "model",
        fake_model,
    )

    task = asyncio.create_task(
        main.stt_stage(segment_q, transcript_q)
    )

    audio = np.array(
        [0.1, 0.2, 0.3],
        dtype=np.float32,
    )

    await segment_q.put(audio)

    transcript = await asyncio.wait_for(
        transcript_q.get(),
        timeout=1,
    )

    assert transcript == "hello world"

    fake_model.transcribe.assert_called_once()

    call_args, call_kwargs = fake_model.transcribe.call_args

    np.testing.assert_array_equal(
        call_args[0],
        audio,
    )

    assert call_kwargs["beam_size"] == 1

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_stt_stage_joins_multiple_segments(monkeypatch):
    segment_q = asyncio.Queue()
    transcript_q = asyncio.Queue()

    fake_model = MagicMock()

    fake_model.transcribe.return_value = (
        [
            SimpleNamespace(text="The "),
            SimpleNamespace(text="quick "),
            SimpleNamespace(text="brown "),
            SimpleNamespace(text="fox."),
        ],
        None,
    )

    monkeypatch.setattr(
        main,
        "model",
        fake_model,
    )

    task = asyncio.create_task(
        main.stt_stage(segment_q, transcript_q)
    )

    await segment_q.put(
        np.zeros(512, dtype=np.float32)
    )

    transcript = await asyncio.wait_for(
        transcript_q.get(),
        timeout=1,
    )

    assert transcript == "The quick brown fox."

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_stt_stage_does_not_queue_empty_transcript(monkeypatch):
    segment_q = asyncio.Queue()
    transcript_q = asyncio.Queue()

    fake_model = MagicMock()

    fake_model.transcribe.return_value = (
        [
            SimpleNamespace(text=""),
        ],
        None,
    )

    monkeypatch.setattr(
        main,
        "model",
        fake_model,
    )

    task = asyncio.create_task(
        main.stt_stage(segment_q, transcript_q)
    )

    await segment_q.put(
        np.zeros(512, dtype=np.float32)
    )

    # Allow stt_stage to process the audio.
    await asyncio.sleep(0.05)

    assert transcript_q.empty()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_stt_stage_does_not_queue_whitespace_only_transcript(
    monkeypatch,
):
    segment_q = asyncio.Queue()
    transcript_q = asyncio.Queue()

    fake_model = MagicMock()

    fake_model.transcribe.return_value = (
        [
            SimpleNamespace(text="   "),
            SimpleNamespace(text="\n"),
            SimpleNamespace(text="\t"),
        ],
        None,
    )

    monkeypatch.setattr(
        main,
        "model",
        fake_model,
    )

    task = asyncio.create_task(
        main.stt_stage(segment_q, transcript_q)
    )

    await segment_q.put(
        np.zeros(512, dtype=np.float32)
    )

    await asyncio.sleep(0.05)

    assert transcript_q.empty()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_stt_stage_processes_multiple_audio_segments(monkeypatch):
    segment_q = asyncio.Queue()
    transcript_q = asyncio.Queue()

    fake_model = MagicMock()

    fake_model.transcribe.side_effect = [
        (
            [SimpleNamespace(text="first")],
            None,
        ),
        (
            [SimpleNamespace(text="second")],
            None,
        ),
        (
            [SimpleNamespace(text="third")],
            None,
        ),
    ]

    monkeypatch.setattr(
        main,
        "model",
        fake_model,
    )

    task = asyncio.create_task(
        main.stt_stage(segment_q, transcript_q)
    )

    audio_1 = np.array(
        [0.1],
        dtype=np.float32,
    )

    audio_2 = np.array(
        [0.2],
        dtype=np.float32,
    )

    audio_3 = np.array(
        [0.3],
        dtype=np.float32,
    )

    await segment_q.put(audio_1)
    await segment_q.put(audio_2)
    await segment_q.put(audio_3)

    result_1 = await asyncio.wait_for(
        transcript_q.get(),
        timeout=1,
    )

    result_2 = await asyncio.wait_for(
        transcript_q.get(),
        timeout=1,
    )

    result_3 = await asyncio.wait_for(
        transcript_q.get(),
        timeout=1,
    )

    assert result_1 == "first"
    assert result_2 == "second"
    assert result_3 == "third"

    assert fake_model.transcribe.call_count == 3

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_stt_stage_uses_beam_size_one(monkeypatch):
    segment_q = asyncio.Queue()
    transcript_q = asyncio.Queue()

    fake_model = MagicMock()

    fake_model.transcribe.return_value = (
        [
            SimpleNamespace(text="test"),
        ],
        None,
    )

    monkeypatch.setattr(
        main,
        "model",
        fake_model,
    )

    task = asyncio.create_task(
        main.stt_stage(segment_q, transcript_q)
    )

    audio = np.zeros(
        512,
        dtype=np.float32,
    )

    await segment_q.put(audio)

    await asyncio.wait_for(
        transcript_q.get(),
        timeout=1,
    )

    fake_model.transcribe.assert_called_once()

    _, kwargs = fake_model.transcribe.call_args

    assert kwargs == {
        "beam_size": 1,
    }

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_stt_stage_waits_for_audio(monkeypatch):
    segment_q = asyncio.Queue()
    transcript_q = asyncio.Queue()

    fake_model = MagicMock()

    monkeypatch.setattr(
        main,
        "model",
        fake_model,
    )

    task = asyncio.create_task(
        main.stt_stage(segment_q, transcript_q)
    )

    await asyncio.sleep(0.05)

    fake_model.transcribe.assert_not_called()
    assert transcript_q.empty()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_stt_stage_passes_same_audio_to_model(monkeypatch):
    segment_q = asyncio.Queue()
    transcript_q = asyncio.Queue()

    received_audio = []

    class FakeModel:
        def transcribe(self, audio, beam_size):
            received_audio.append(audio)

            return (
                [
                    SimpleNamespace(
                        text="audio received"
                    )
                ],
                None,
            )

    monkeypatch.setattr(
        main,
        "model",
        FakeModel(),
    )

    task = asyncio.create_task(
        main.stt_stage(segment_q, transcript_q)
    )

    audio = np.array(
        [
            0.10,
            0.20,
            0.30,
            0.40,
        ],
        dtype=np.float32,
    )

    await segment_q.put(audio)

    await asyncio.wait_for(
        transcript_q.get(),
        timeout=1,
    )

    assert len(received_audio) == 1

    np.testing.assert_array_equal(
        received_audio[0],
        audio,
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
