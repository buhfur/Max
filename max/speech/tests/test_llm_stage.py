import asyncio
import json

import pytest

from max.speech import main


class FakeResponse:
    """
    Fake streaming HTTP response.

    aiter_lines() behaves like httpx.Response.aiter_lines().
    """

    def __init__(self, lines):
        self.lines = lines

    async def aiter_lines(self):
        for line in self.lines:
            yield line


class FakeStreamContext:
    """
    Async context manager returned by client.stream().
    """

    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False


class FakeAsyncClient:
    """
    Fake replacement for httpx.AsyncClient.

    Stores request information so tests can verify:
    - HTTP method
    - URL
    - JSON payload
    - timeout
    """

    response_lines = []
    requests = []
    timeout = None

    def __init__(self, timeout=None):
        FakeAsyncClient.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        return False

    def stream(
        self,
        method,
        url,
        json=None,
    ):
        FakeAsyncClient.requests.append(
            {
                "method": method,
                "url": url,
                "json": json,
            }
        )

        response = FakeResponse(
            FakeAsyncClient.response_lines
        )

        return FakeStreamContext(response)


@pytest.fixture
def fake_httpx(monkeypatch):
    """
    Replace httpx.AsyncClient with FakeAsyncClient.
    """

    FakeAsyncClient.response_lines = []
    FakeAsyncClient.requests = []
    FakeAsyncClient.timeout = None

    monkeypatch.setattr(
        main.httpx,
        "AsyncClient",
        FakeAsyncClient,
    )

    return FakeAsyncClient


@pytest.mark.asyncio
async def test_llm_stage_sends_prompt_to_ollama(fake_httpx):
    transcript_q = asyncio.Queue()
    token_q = asyncio.Queue()

    fake_httpx.response_lines = [
        json.dumps(
            {
                "response": "hello",
                "done": True,
            }
        )
    ]

    task = asyncio.create_task(
        main.llm_stage(
            transcript_q,
            token_q,
        )
    )

    await transcript_q.put(
        "Say hello"
    )

    await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    assert len(fake_httpx.requests) == 1

    request = fake_httpx.requests[0]

    assert request["method"] == "POST"

    assert (
        request["url"]
        == "http://localhost:11434/api/generate"
    )

    assert request["json"] == {
        "model": "qwen3:8b",
        "prompt": "Say hello",
        "stream": True,
    }

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_llm_stage_uses_no_http_timeout(fake_httpx):
    transcript_q = asyncio.Queue()
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.llm_stage(
            transcript_q,
            token_q,
        )
    )

    await asyncio.sleep(0)

    assert fake_httpx.timeout is None

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_llm_stage_places_tokens_in_queue(fake_httpx):
    transcript_q = asyncio.Queue()
    token_q = asyncio.Queue()

    fake_httpx.response_lines = [
        json.dumps(
            {
                "response": "Hello",
                "done": False,
            }
        ),
        json.dumps(
            {
                "response": " ",
                "done": False,
            }
        ),
        json.dumps(
            {
                "response": "world",
                "done": False,
            }
        ),
        json.dumps(
            {
                "response": "!",
                "done": True,
            }
        ),
    ]

    task = asyncio.create_task(
        main.llm_stage(
            transcript_q,
            token_q,
        )
    )

    await transcript_q.put(
        "Give me a greeting"
    )

    token_1 = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    token_2 = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    token_3 = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    token_4 = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    sentinel = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    assert token_1 == "Hello"
    assert token_2 == " "
    assert token_3 == "world"
    assert token_4 == "!"
    assert sentinel is None

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_llm_stage_adds_none_sentinel_when_done(fake_httpx):
    transcript_q = asyncio.Queue()
    token_q = asyncio.Queue()

    fake_httpx.response_lines = [
        json.dumps(
            {
                "response": "finished",
                "done": True,
            }
        )
    ]

    task = asyncio.create_task(
        main.llm_stage(
            transcript_q,
            token_q,
        )
    )

    await transcript_q.put(
        "test prompt"
    )

    token = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    sentinel = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    assert token == "finished"
    assert sentinel is None

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_llm_stage_ignores_blank_lines(fake_httpx):
    transcript_q = asyncio.Queue()
    token_q = asyncio.Queue()

    fake_httpx.response_lines = [
        "",
        "",
        json.dumps(
            {
                "response": "hello",
                "done": True,
            }
        ),
    ]

    task = asyncio.create_task(
        main.llm_stage(
            transcript_q,
            token_q,
        )
    )

    await transcript_q.put(
        "test"
    )

    token = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    sentinel = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    assert token == "hello"
    assert sentinel is None
    assert token_q.empty()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_llm_stage_handles_missing_response_field(fake_httpx):
    transcript_q = asyncio.Queue()
    token_q = asyncio.Queue()

    fake_httpx.response_lines = [
        json.dumps(
            {
                "done": True,
            }
        )
    ]

    task = asyncio.create_task(
        main.llm_stage(
            transcript_q,
            token_q,
        )
    )

    await transcript_q.put(
        "test"
    )

    token = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    sentinel = await asyncio.wait_for(
        token_q.get(),
        timeout=1,
    )

    assert token == ""
    assert sentinel is None

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_llm_stage_waits_for_prompt(fake_httpx):
    transcript_q = asyncio.Queue()
    token_q = asyncio.Queue()

    task = asyncio.create_task(
        main.llm_stage(
            transcript_q,
            token_q,
        )
    )

    await asyncio.sleep(0.05)

    assert fake_httpx.requests == []
    assert token_q.empty()

    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
