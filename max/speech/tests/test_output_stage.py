import asyncio

import pytest

from max.speech import main


@pytest.mark.asyncio
async def test_output_stage_prints_token(capsys):
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.output_stage(token_q)
    )

    await token_q.put(
        "hello"
    )

    await asyncio.sleep(0)

    captured = capsys.readouterr()

    assert captured.out == "hello"

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_output_stage_prints_multiple_tokens(capsys):
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.output_stage(token_q)
    )

    await token_q.put("Hello")
    await token_q.put(" ")
    await token_q.put("world")
    await token_q.put("!")

    # Give output_stage enough loop iterations
    # to consume each queued token.
    for _ in range(4):
        await asyncio.sleep(0)

    captured = capsys.readouterr()

    assert captured.out == "Hello world!"

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_output_stage_none_prints_newline(capsys):
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.output_stage(token_q)
    )

    await token_q.put(None)

    await asyncio.sleep(0)

    captured = capsys.readouterr()

    assert captured.out == "\n"

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_output_stage_complete_utterance(capsys):
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.output_stage(token_q)
    )

    await token_q.put("The")
    await token_q.put(" ")
    await token_q.put("system")
    await token_q.put(" ")
    await token_q.put("is")
    await token_q.put(" ")
    await token_q.put("ready.")
    await token_q.put(None)

    for _ in range(8):
        await asyncio.sleep(0)

    captured = capsys.readouterr()

    assert (
        captured.out
        == "The system is ready.\n"
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_output_stage_continues_after_sentinel(capsys):
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.output_stage(token_q)
    )

    # First LLM response
    await token_q.put("first")
    await token_q.put(None)

    # Second LLM response
    await token_q.put("second")
    await token_q.put(None)

    for _ in range(4):
        await asyncio.sleep(0)

    captured = capsys.readouterr()

    assert captured.out == (
        "first\n"
        "second\n"
    )

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_output_stage_waits_for_token(capsys):
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.output_stage(token_q)
    )

    await asyncio.sleep(0.05)

    captured = capsys.readouterr()

    assert captured.out == ""

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_output_stage_prints_empty_string(capsys):
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.output_stage(token_q)
    )

    await token_q.put("")

    await asyncio.sleep(0)

    captured = capsys.readouterr()

    assert captured.out == ""

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
