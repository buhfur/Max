# Local Linux AI Desktop Assistant

## Project vision

Build a voice-first AI assistant that runs on a Linux desktop and feels
like a persistent general-purpose assistant rather than only a chatbot.

The assistant should be able to:

-   Talk naturally through a microphone and speakers.
-   Act as a "rubber duck" while programming: ask questions, challenge
    assumptions, and help reason through code.
-   Switch into a more direct "do it" mode when asked.
-   Run tests, compile code, inspect errors, search documentation, and
    work with Git repositories.
-   Display code snippets, terminal output, status information, and
    other visual content while the voice conversation continues.
-   Automate a browser and, eventually, selected desktop applications.
-   Remember the current project/task so work can resume without
    reconstructing all the context.
-   Use image-generation/editing models as optional tools.
-   Use a wake word for hands-free activation.
-   Keep sensitive/destructive operations behind explicit confirmation.

The goal is not to train a large model from scratch. The practical
approach is to combine an existing local model with specialized tools.

------------------------------------------------------------------------

## High-level architecture

``` text
Microphone
    |
    v
Wake-word detector (optional)
    |
    v
Speech-to-text
    |
    v
+-----------------------+
|  Orchestrator / Agent |
|  "main brain"         |
+-----------------------+
    |
    +----> Local LLM
    |
    +----> Terminal / shell tools
    |
    +----> Test runner / compiler
    |
    +----> File-system tools
    |
    +----> Git tools
    |
    +----> Browser automation
    |
    +----> Documentation/search tools
    |
    +----> Image tools
    |
    +----> Desktop automation
    |
    +----> Memory / task state
    |
    v
Text-to-speech
    |
    v
Speakers

At the same time:

Agent -> Desktop UI -> conversation / code / terminal / tool status
```

The important design idea is that the LLM is not directly given
unrestricted control of the computer. The orchestrator exposes specific
tools with defined permissions.

------------------------------------------------------------------------

## Suggested Ubuntu stack

### Core language

**Python**

Use Python for the initial backend/orchestration layer. It has strong
libraries for AI models, audio, automation, testing, APIs, and system
integration.

### Local model runtime

**Ollama** is a convenient starting point for running local models.

Do not optimize around finding the perfect model initially. First prove
that the complete assistant loop works.

The model should initially handle:

-   Conversation
-   Tool selection
-   Reasoning about tool results
-   Coding assistance
-   Task planning

Models can be swapped later.

### Backend / orchestrator

**FastAPI**

The backend can expose endpoints or WebSockets connecting the desktop
interface to:

-   The LLM
-   Audio pipeline
-   Tool execution
-   Memory
-   Long-running tasks

A simple internal tool interface might conceptually look like:

``` python
class Tool:
    name: str
    description: str

    async def execute(self, arguments):
        ...
```

Then tools can be registered independently.

### Memory

Start with **SQLite**.

Possible information to store:

-   Current project
-   Current task
-   Recent commands
-   Conversation summaries
-   Decisions
-   Files recently discussed
-   Pending work

PostgreSQL can replace SQLite later if the requirements justify it.

Avoid dumping unlimited conversation history into the model. Prefer
compact summaries and explicit task state.

### Browser automation

**Playwright**

Potential actions:

-   Open a page
-   Search documentation
-   Read page content
-   Navigate forums
-   Fill forms
-   Interact with web development environments

Browser automation should initially operate in a restricted profile
rather than automatically inheriting every authenticated personal
session.

### Git

You can begin by invoking the `git` CLI from a controlled subprocess.

**GitPython** is another option if a Python API becomes useful.

Potential tools:

-   `git status`
-   Show diffs
-   Create branches
-   Commit changes
-   Inspect history

Pushing, force operations, deleting branches, or changing remote state
should require confirmation.

### Speech-to-text

A **Whisper-family** speech-to-text implementation is a reasonable
starting point.

The voice pipeline should eventually support streaming so the assistant
does not have to wait for a long recording to finish before processing
speech.

### Text-to-speech

**Piper** is a lightweight local option worth testing.

The TTS engine should be replaceable because voice quality is likely to
matter substantially for a voice-first assistant.

### Wake word

Possible wake-word engines include:

-   openWakeWord
-   Porcupine

Architecture:

``` text
Always-on microphone
       |
       v
Small wake-word detector
       |
   wake word?
    /     \
  no       yes
  |         |
sleep    activate STT
```

Also keep a push-to-talk keyboard shortcut. It is useful when the room
is noisy or you do not want accidental activation.

### Desktop interface

**Tauri** is a strong option for a lightweight Linux desktop
application.

An alternative is **Electron**, especially if rapid web-style UI
development matters more than footprint.

A useful layout:

``` text
+-----------------------------------------------------+
| Assistant status / current project / current task   |
+----------------------+------------------------------+
| Conversation         | Code / document viewer       |
|                      |                              |
| You: run the tests   | def calculate_total(...):   |
| AI: running pytest   |     ...                      |
|                      |                              |
+----------------------+------------------------------+
| Terminal / tool output                              |
| $ pytest tests/...                                  |
| FAILED ...                                          |
+-----------------------------------------------------+
```

Voice can continue while this interface updates.

------------------------------------------------------------------------

## Interaction modes

One assistant can support multiple behaviors without using entirely
separate applications.

### Assistant mode

The user gives direct commands:

-   "Run the tests."
-   "Open the documentation for this API."
-   "Show me the failing function."
-   "Compile this."
-   "Check Git status."

The assistant acts and reports the result.

### Learning / rubber-duck mode

The assistant deliberately avoids immediately solving everything.

Examples:

-   "What behavior are we testing?"
-   "What do you expect this function to return?"
-   "Which dependency should be mocked?"
-   "Why do you think this test is failing?"

This is useful when the goal is understanding the code rather than
merely producing code.

### Automatic mode selection

This can be added later.

Initially, explicit commands are safer:

-   "Learning mode."
-   "Just do it."
-   "Walk me through this."
-   "Take over this task."
-   "Ask me questions instead of giving me the answer."

After enough experience, the orchestrator can infer the appropriate mode
while still allowing manual overrides.

------------------------------------------------------------------------

## Development tools

The first useful coding capabilities could be deliberately small.

### Terminal tool

Start with read-only or low-risk commands:

-   `pwd`
-   `ls`
-   `git status`
-   `git diff`
-   `pytest`
-   Compiler/build commands
-   Log inspection

Do not initially give the model unrestricted shell execution.

Create an allowlist or policy layer.

For example:

``` text
SAFE
git status
git diff
pytest
python -m pytest
docker compose ps

CONFIRM
git commit
docker compose restart
package installation

HIGH-RISK / CONFIRM CAREFULLY
rm
sudo
git push --force
credential changes
filesystem-wide operations
```

### Pytest assistant

This could become one of the first genuinely useful tools.

Example conversation:

``` text
You:
Run the tests for the auction service.

Assistant:
Running pytest for that module.

[terminal updates]

Assistant:
Two tests failed. The first failure is in bid validation.
Do you want the explanation, or should I attempt a fix?
```

In learning mode:

``` text
Assistant:
Before I fix it: what condition do you think this test is
trying to guarantee?
```

That keeps the user cognitively involved instead of silently generating
an entire test suite.

### Documentation tool

The assistant could:

1.  Determine the library/API involved.
2.  Search official documentation.
3.  Retrieve the relevant section.
4.  Summarize it.
5.  Display examples in the UI.
6.  Apply the information to the current code only when asked.

------------------------------------------------------------------------

## AMD Radeon RX 6800 XT considerations

The RX 6800 XT has substantial GPU capability and can be useful for
local inference.

The main complication is software compatibility. Local AI tooling has
historically been more straightforward on NVIDIA/CUDA, so AMD support
needs to be checked for the exact model runtime and Linux configuration
being used.

The practical strategy:

1.  Choose a runtime that supports the GPU.
2.  Start with a moderate-size quantized model.
3.  Benchmark actual latency.
4.  Optimize only after the end-to-end assistant works.

CPU and RAM still matter, especially for:

-   Model loading/offloading
-   Speech processing
-   Tool execution
-   Browser automation
-   Compilation
-   Databases

But LLM inference is typically where GPU acceleration provides the
largest benefit.

------------------------------------------------------------------------

## Credentials and security

Do not make the model the owner of passwords, GitHub tokens, SSH keys,
or other sensitive credentials.

Instead, use the operating system and established credential systems.

Possible pattern:

``` text
Assistant requests GitHub operation
        |
        v
Tool checks existing authenticated credential
        |
        v
Operation is categorized by risk
        |
        +--> read-only -> execute
        |
        +--> write/destructive -> ask user
```

The assistant can guide credential creation, but credential material
should ideally never be copied into the model's conversational context.

Potential storage mechanisms include:

-   System keyring
-   SSH agent
-   Git credential helpers
-   Environment/secrets managers with restricted access

### General security rules

1.  Least privilege by default.
2.  Separate read and write tools.
3.  Require confirmation for destructive actions.
4.  Log every tool invocation.
5.  Display commands before high-risk execution.
6.  Restrict filesystem access to approved project directories
    initially.
7.  Do not run the assistant itself as root.
8.  Treat browser sessions and credentials as separate privileged
    resources.
9.  Give the user an immediate kill switch.
10. Make autonomous execution bounded by time, command count, and scope.

------------------------------------------------------------------------

## Image capabilities

Image generation/editing can simply be another tool.

Possible operations:

-   Generate an image.
-   Remove/replace an object.
-   Extend an image.
-   Change visual style.
-   Edit screenshots.
-   Blur sensitive information.
-   Annotate visual material.

The orchestrator does not need to understand the internal image model.
It only needs a defined interface such as:

``` text
edit_image(
    image,
    instruction
)
```

The result can then appear in the desktop UI.

------------------------------------------------------------------------

## Suggested first milestone

Do **not** begin with:

-   Wake words
-   Full desktop control
-   Autonomous browsing
-   Image editing
-   Multiple agents
-   Long-term semantic memory
-   Credential management

Build this first:

``` text
Keyboard / microphone input
        |
        v
Local model
        |
        v
Tool request
        |
        v
Run pytest
        |
        v
Display terminal output
        |
        v
Assistant explains result
```

A good first command:

> "Run the tests in this project and explain the first failure."

If that works reliably, the project already has practical value.

------------------------------------------------------------------------

## Incremental roadmap

### Phase 1 - Text agent

Build:

-   Python orchestrator
-   Local LLM
-   Terminal tool
-   Project-directory restriction
-   Simple chat interface

Goal:

> "Run pytest and explain the first failure."

### Phase 2 - Developer assistant

Add:

-   Git integration
-   File reading/editing
-   Documentation retrieval
-   Better code display
-   Task state
-   Confirmation system

Goal:

> "Inspect this failure, show me the relevant code, and help me
> understand it."

### Phase 3 - Voice

Add:

-   Microphone input
-   Streaming STT
-   TTS
-   Push-to-talk
-   Interruptible speech

Goal:

Have a natural voice conversation while tools execute.

### Phase 4 - Desktop UI

Add:

-   Tauri/Electron interface
-   Conversation pane
-   Code pane
-   Terminal pane
-   Tool-status indicators
-   Current project/task display

Goal:

Voice and visual information operate simultaneously.

### Phase 5 - Wake word

Add:

-   openWakeWord/Porcupine
-   Wake/sleep states
-   Audible or visual activation feedback

Goal:

Hands-free activation.

### Phase 6 - Browser agent

Add:

-   Playwright
-   Restricted browser profile
-   Documentation search
-   Page reading
-   Controlled interaction

Goal:

> "Find the official documentation for this error and show me the
> relevant section."

### Phase 7 - Persistent memory

Add structured memory for:

-   Projects
-   Tasks
-   Decisions
-   Recent work
-   Summaries

Goal:

> "What was I working on yesterday?"

The assistant should recover useful context without requiring a complete
replay of old conversations.

### Phase 8 - Broader desktop control

Only after the permission model is mature:

-   Window management
-   Application launching
-   Clipboard
-   Screenshots
-   Selected GUI interaction

Avoid unrestricted "AI controls my entire desktop" permissions until the
audit/confirmation system is trustworthy.

------------------------------------------------------------------------

## A possible repository layout

``` text
desktop-assistant/
├── app/
│   ├── orchestrator/
│   │   ├── agent.py
│   │   ├── prompts.py
│   │   └── policy.py
│   │
│   ├── tools/
│   │   ├── terminal.py
│   │   ├── pytest_tool.py
│   │   ├── git.py
│   │   ├── filesystem.py
│   │   ├── browser.py
│   │   └── images.py
│   │
│   ├── voice/
│   │   ├── stt.py
│   │   ├── tts.py
│   │   └── wakeword.py
│   │
│   ├── memory/
│   │   ├── database.py
│   │   ├── tasks.py
│   │   └── summaries.py
│   │
│   ├── api/
│   │   └── server.py
│   │
│   └── security/
│       ├── permissions.py
│       └── audit.py
│
├── ui/
├── tests/
├── config/
├── data/
├── pyproject.toml
├── README.md
└── docker-compose.yml
```

------------------------------------------------------------------------

## Design principle: make it useful before making it impressive

The tempting version of this project is:

> "Build Jarvis."

That scope is enormous.

The useful version is:

> "Build something I can talk to that understands my current project,
> runs a test when I ask, shows me what happened, and helps me reason
> through the failure."

Once that works, each additional capability is just another tool.

The architecture should therefore prioritize:

-   Replaceable models
-   Small independent tools
-   Explicit permissions
-   Visible tool activity
-   Persistent task state
-   Voice plus visual output
-   Human control over consequential actions

That creates a system that can gradually become the general Linux
desktop assistant originally envisioned without requiring the entire
system to be solved at once.

------------------------------------------------------------------------

## Recommended first build session

Keep the first session deliberately narrow:

1.  Install/configure a local model runtime.
2.  Write a Python script that sends it a prompt.
3.  Define one `pytest` tool.
4.  Let the model request that tool through structured output/tool
    calling.
5.  Execute pytest only inside a configured project directory.
6.  Feed the output back to the model.
7.  Ask the model to explain only the first failure.
8.  Add logging for the request, command, result, and response.

Do not add voice until this loop is reliable.

Once that works, voice becomes an interface to an already-useful agent
rather than another moving part that has to be debugged simultaneously.
