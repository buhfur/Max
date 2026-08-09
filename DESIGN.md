# Local Linux Voice Assistant — Initial Project Design

## Goal

Build a small Linux desktop assistant that can:

1. Listen to spoken commands.
2. Convert speech to text.
3. Interpret the request.
4. Map it to a predefined system action.
5. Execute the action.
6. Report what it is doing through speech and text.
7. Capture the command result.
8. Summarize the result.
9. Speak the result back to the user.

Example:

```text
User:
"Run a system update."

Assistant:
"Okay Ryan, let me run that for you."

System executes:
sudo apt update

Assistant:
"The update completed successfully. Seventeen packages can be upgraded."
```

The initial version should remain deliberately small.

The design should follow Unix principles:

- Do one thing well.
- Keep components small.
- Prefer simple interfaces between components.
- Make components replaceable.
- Avoid unnecessary frameworks.
- Use existing Linux tools instead of rebuilding them.
- Keep policy and execution separate.
- Prefer explicit behavior over hidden automation.

---

# Basic Architecture

```text
Microphone
    |
    v
Speech-to-Text
    |
    v
Plain text
    |
    v
Intent Router
    |
    v
Approved Tool
    |
    v
Command Executor
    |
    v
stdout / stderr / exit code
    |
    v
Result Summarizer
    |
    v
Text-to-Speech
    |
    v
Speakers
```

Each part should be independently replaceable.

The assistant should not require changing the rest of the application simply because the STT model, TTS engine, or LLM changes.

---

# Unix/KISS Design

Instead of creating one large application that handles everything, split the project into small components.

```text
voice-assistant/
├── assistant.py
├── config.py
│
├── speech/
│   ├── stt.py
│   └── tts.py
│
├── agent/
│   ├── intent.py
│   └── summarize.py
│
├── tools/
│   ├── registry.py
│   ├── system.py
│   └── development.py
│
├── executor/
│   └── process.py
│
└── audio/
    ├── record.py
    └── playback.py
```

Each module should have a narrow responsibility.

For example:

```text
record.py
```

only records audio.

```text
stt.py
```

only turns audio into text.

```text
intent.py
```

only determines what action the user requested.

```text
process.py
```

only executes approved processes and returns their output.

```text
tts.py
```

only converts text into speech.

This also makes every component easy to test independently.

---

# Speech-to-Text Layer

Speech recognition should not be tied to one specific model.

Define a very small interface:

```python
class SpeechToText:
    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError
```

Individual implementations can then sit behind it.

Example:

```text
speech/
├── stt.py
├── whisper_stt.py
├── faster_whisper_stt.py
└── vosk_stt.py
```

The application only needs to know:

```python
text = stt.transcribe(audio_file)
```

It should not care which model produced the transcription.

---

# Possible Speech-to-Text Engines

Several STT engines can be evaluated.

## Whisper

Useful baseline.

Advantages:

- Strong general transcription quality.
- Good handling of conversational speech.
- Large ecosystem.
- Multiple model sizes.

Disadvantages:

- Larger models can require significant compute.
- Real-time performance depends on hardware.

---

## faster-whisper

A practical Whisper implementation optimized for inference.

Likely a strong choice for the first implementation.

Possible flow:

```text
Microphone
   |
   v
Audio buffer
   |
   v
faster-whisper
   |
   v
"run a system update"
```

---

## whisper.cpp

Useful if a lightweight native implementation is preferred.

It may fit the Unix philosophy particularly well because it can run as a relatively self-contained component.

It could potentially even be treated as an external process:

```bash
whisper-cli recording.wav
```

The Python application then consumes its output.

This keeps the speech engine separated from the assistant itself.

---

## Vosk

Another option for offline recognition.

It may be worth testing for lightweight or low-latency commands even if Whisper produces better general transcription.

---

# STT Selection

The speech engine should be configured rather than hard-coded.

For example:

```toml
[stt]
engine = "faster-whisper"
model = "small"
language = "en"
```

Or:

```yaml
stt:
  engine: faster-whisper
  model: small
```

The assistant then loads the appropriate implementation.

This makes experimentation easy.

---

# Text-to-Speech Layer

Text-to-speech should follow exactly the same design.

Define a minimal interface:

```python
class TextToSpeech:
    def speak(self, text: str) -> None:
        raise NotImplementedError
```

Possible implementations:

```text
speech/
├── tts.py
├── piper_tts.py
├── kokoro_tts.py
└── system_tts.py
```

The rest of the application only calls:

```python
tts.speak("The update completed successfully.")
```

---

# Possible Text-to-Speech Engines

## Piper

A strong initial option for a local Linux assistant.

Advantages:

- Local.
- Lightweight.
- Fast.
- Straightforward command-line usage.
- Fits well with Unix-style process composition.

For example, the assistant could potentially pipe text into Piper:

```bash
echo "System update complete." | piper ...
```

The Python application does not necessarily need to understand how speech synthesis works internally.

---

## Kokoro

Another local TTS option worth evaluating if voice quality is more important.

It can be exposed through the same `TextToSpeech` interface.

Switching from Piper to Kokoro should require changing configuration, not rewriting the assistant.

---

## System TTS

A very simple fallback implementation could use existing Linux speech tools.

This is useful during early development because voice quality is not important while testing the architecture.

For example:

```text
Assistant -> espeak-ng -> audio
```

Once the control loop works, replace the TTS engine.

---

# TTS Selection

Example configuration:

```toml
[tts]
engine = "piper"
voice = "default"
```

Later:

```toml
[tts]
engine = "kokoro"
voice = "voice_name"
```

No other application code should need to change.

---

# Speech Pipeline

The complete speech flow becomes:

```text
       Microphone
           |
           v
     audio/record.py
           |
           v
      STT adapter
           |
           v
     Plain text string
           |
           v
        Assistant
           |
           v
      TTS adapter
           |
           v
        Speakers
```

The assistant communicates with text internally.

Audio is only an input/output concern.

That separation is important.

The core assistant should not care whether the request originally came from:

- microphone
- keyboard
- API
- Tauri
- SSH
- another program

Everything eventually becomes plain text.

---

# Example

The microphone captures:

```text
"Hey, run a system update."
```

STT outputs:

```text
run a system update
```

That plain text is passed to the intent router.

---

# Intent Routing

The LLM should **not generate arbitrary shell commands and immediately execute them**.

Instead, the LLM chooses from a small collection of predefined tools.

For example:

```python
TOOLS = {
    "apt_update": {
        "description": "Refresh Ubuntu package indexes",
        "command": ["sudo", "apt", "update"],
    },

    "disk_usage": {
        "description": "Show filesystem disk usage",
        "command": ["df", "-h"],
    },
}
```

The LLM sees something conceptually like:

```text
User:
"Run a system update."

Available actions:

apt_update
    Refresh Ubuntu package indexes.

disk_usage
    Show filesystem usage.
```

It returns:

```json
{
  "tool": "apt_update"
}
```

The model never needs to generate:

```bash
sudo apt update
```

The application already knows exactly what `apt_update` means.

---

# Why This Matters

This prevents something like:

```text
User says:
"Can you clean things up?"
```

from accidentally becoming:

```bash
sudo rm -rf ...
```

The LLM decides intent.

The program decides implementation.

That boundary should remain fundamental to the design.

---

# Tool Registry

The initial tool registry can remain extremely simple.

```python
TOOLS = {
    "apt_update": apt_update,
    "disk_usage": disk_usage,
    "run_pytest": run_pytest,
}
```

Each function returns a common structure:

```python
{
    "success": True,
    "exit_code": 0,
    "stdout": "...",
    "stderr": "",
}
```

This avoids unnecessary abstraction early in development.

If the project becomes large later, the registry can evolve.

Do not build the future architecture before it is needed.

---

# Command Execution

Use Python's subprocess support.

For example:

```python
import asyncio


async def run_command(command):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    stdout, stderr = await process.communicate()

    return {
        "exit_code": process.returncode,
        "stdout": stdout.decode(),
        "stderr": stderr.decode(),
        "success": process.returncode == 0,
    }
```

The executor should not interpret the output.

Its only job is:

```text
command in
    ↓
process execution
    ↓
stdout + stderr + exit code out
```

---

# Example apt Tool

```python
async def apt_update():
    return await run_command(
        ["sudo", "apt", "update"]
    )
```

Later, other operations can be added:

```python
async def disk_usage():
    return await run_command(
        ["df", "-h"]
    )
```

And:

```python
async def run_pytest():
    return await run_command(
        ["python", "-m", "pytest"]
    )
```

Same execution system.

Different tools.

---

# Assistant Orchestrator

The orchestrator coordinates the components.

Conceptually:

```python
async def handle_request(audio_file):
    text = stt.transcribe(audio_file)

    action = await determine_intent(text)

    await tts.speak(
        acknowledgement_for(action)
    )

    result = await execute_tool(action)

    response = await summarize_result(result)

    await tts.speak(response)

    return response
```

Eventually acknowledgements can also come from the model.

For the first version, simple predefined acknowledgement strings may actually be better.

Example:

```python
ACKNOWLEDGEMENTS = {
    "apt_update":
        "Okay Ryan, let me update the package lists.",

    "disk_usage":
        "Sure, I'll check disk usage.",

    "run_pytest":
        "Okay, I'll run the tests.",
}
```

That avoids an extra LLM call just to say one sentence.

KISS.

---

# Result Summarization

The raw tool result might be:

```text
Hit:1 http://archive.ubuntu.com/ubuntu...
Get:2 ...
Fetched 4,215 kB in 2s
Reading package lists... Done
Building dependency tree... Done
17 packages can be upgraded.
```

Instead of speaking all of that, the result can be given to the model.

Prompt:

```text
Summarize this command result for the user.

Command:
apt update

Exit code:
0

stdout:
...

stderr:
...
```

Response:

```text
The update completed successfully.
Your package lists are current, and 17 packages
have available upgrades.
```

Then the TTS layer speaks that result.

---

# Handling Failure

If:

```text
exit_code != 0
```

the assistant should not pretend the command succeeded.

Example:

```text
The update failed because one repository could not be reached.
I can show you the full error if you want.
```

Raw output should remain available for inspection.

---

# Privileged Commands

The model should never receive or store the user's sudo password.

Avoid designs such as:

```text
LLM
 ↓
"What is your password?"
 ↓
password stored in prompt
```

Instead:

```text
Assistant
    |
    v
Requests privileged operation
    |
    v
Linux authentication
    |
    v
User approves
    |
    v
Operation executes
```

For the earliest prototype, running the assistant backend from an interactive terminal is sufficient.

When:

```bash
sudo apt update
```

needs authentication, the normal Linux terminal can handle it.

Later, `polkit` can provide a cleaner desktop authorization flow.

---

# Initial User Experience

A first working prototype could behave like this:

```text
[User presses Push-to-Talk]

User:
"Run a system update."

STT:
run a system update

Intent:
apt_update

Assistant:
"Okay Ryan, let me update the package lists."

Command:
sudo apt update

Status:
running

...

Exit code:
0

Assistant:
"The update completed successfully.
Seventeen packages can be upgraded."
```

That alone proves almost the entire architecture.

---

# Keep Tauri Out Initially

Do not start by building the full UI.

Version one can simply run from:

```bash
python assistant.py
```

The terminal can display:

```text
Listening...

Heard:
run a system update

Intent:
apt_update

Running:
sudo apt update

Reading package lists... Done

Exit code: 0

Assistant:
The update completed successfully.
```

Once that pipeline works reliably, Tauri becomes a UI around an already-working system.

---

# Future Tauri Architecture

Later:

```text
┌──────────────────────────────┐
│           Tauri              │
│                              │
│ Conversation                 │
│ Current task                 │
│ Terminal output              │
│ Microphone state             │
│ Tool activity                │
└──────────────┬───────────────┘
               |
          WebSocket
               |
               v
┌──────────────────────────────┐
│        Python Backend        │
│                              │
│ STT                          │
│ Intent Router                │
│ Tools                        │
│ Executor                     │
│ Summarizer                   │
│ TTS                          │
└──────────────────────────────┘
```

The Python backend remains useful even if the UI changes completely.

---

# Configuration

Keep configurable components outside application logic.

Example:

```toml
[assistant]
name = "Max"

[stt]
engine = "faster-whisper"
model = "small"

[tts]
engine = "piper"
voice = "default"

[model]
provider = "ollama"
model = "local-model"

[security]
require_confirmation_for_privileged = true
```

This makes experimentation easy.

For example:

```text
faster-whisper
       ↓
whisper.cpp
```

should be a configuration change rather than an architectural rewrite.

Likewise:

```text
Piper
  ↓
Kokoro
```

should not affect the orchestration code.

---

# Phase 1

Implement only:

```text
Microphone
    ↓
Speech-to-text
    ↓
Intent recognition
    ↓
apt_update tool
    ↓
subprocess
    ↓
result summarization
    ↓
text-to-speech
```

One command.

One tool.

One complete loop.

---

# Phase 2

Add a few safe commands:

```text
disk_usage
memory_usage
system_uptime
git_status
run_pytest
docker_status
```

Do not add arbitrary shell execution yet.

---

# Phase 3

Add push-to-talk and better continuous audio handling.

Potential later addition:

```text
Wake word detector
        ↓
STT activation
```

---

# Phase 4

Add Tauri.

Tauri provides:

```text
Conversation
Terminal output
Code snippets
Tool status
Push-to-talk button
Permission dialogs
System tray
```

The existing Python assistant remains the backend.

---

# Phase 5

Expand Tools

Possible developer tools:

```text
run_pytest
git_status
git_diff
docker_compose_ps
docker_compose_logs
build_project
```

Possible system tools:

```text
apt_update
disk_usage
memory_usage
system_uptime
service_status
```

Each remains a small function or executable operation.

---

# Long-Term Principle

The system should continue to look conceptually like:

```text
INPUT
  |
  v
TEXT
  |
  v
INTENT
  |
  v
TOOL
  |
  v
RESULT
  |
  v
TEXT
  |
  v
OUTPUT
```

Voice should remain replaceable.

The model should remain replaceable.

The UI should remain replaceable.

The tools should remain independent.

That is the main architectural rule for the project:

> Build small components that communicate through simple interfaces, and avoid coupling the entire assistant to any particular model, speech engine, UI framework, or automation system.