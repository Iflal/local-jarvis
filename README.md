# Local Jarvis

Local Jarvis is an offline-first Windows desktop assistant designed for a
Lenovo Legion 5-class laptop with 16 GB RAM and a 4 GB NVIDIA GPU. Routine
commands use a fast deterministic router; conversation and webcam descriptions
use a local Ollama model. The assistant never sends model-generated commands to
PowerShell.

After the one-time model and package downloads, speech recognition, language
model inference, notes, reminders, and speech output can operate locally. Web
searches and websites naturally still require an internet connection.

## Components

- Faster-Whisper `base.en` for offline speech recognition
- Ollama with `qwen3.5:2b-q4_K_M` for local conversation and vision
- Windows SAPI through `pyttsx3` for fast offline speech output
- SQLite for local conversation history, notes, and reminders
- OpenCV for one-frame webcam inspection
- Allow-listed Python functions for desktop actions

## 1. Install Ollama and the model

Install Ollama for Windows from <https://ollama.com/download/windows>, then open
PowerShell and run:

```powershell
ollama pull qwen3.5:2b-q4_K_M
ollama run qwen3.5:2b-q4_K_M "Reply with: model ready"
ollama ps
```

`ollama ps` should ideally report `100% GPU`. Keep the context at 4096 on a
4 GB GPU. To guarantee that Ollama does not use cloud features, set this user
environment variable and restart Ollama:

```powershell
[Environment]::SetEnvironmentVariable("OLLAMA_NO_CLOUD", "1", "User")
```

## 2. Create the Miniconda environment

From this `local-jarvis` directory:

```powershell
conda env create -f environment.yml
conda activate local-jarvis
```

If the environment already exists:

```powershell
conda env update -f environment.yml --prune
conda activate local-jarvis
```

The first voice transcription downloads the Faster-Whisper `base.en` model.
After it has been cached, it can run offline.

## 3. Verify the installation

```powershell
python main.py --check
python -m unittest discover -s tests -v
```

Every dependency and Ollama should show `OK`.

## 4. Run Jarvis

Push-to-talk is the recommended mode:

```powershell
python main.py
```

Press Enter, speak, and pause. Press `q` and Enter to quit.

Text mode is useful for setup and testing:

```powershell
python main.py --text
```

Continuous voice mode listens for commands beginning with “Jarvis” or “Hey
Jarvis”:

```powershell
python main.py --continuous
```

Continuous mode performs speech recognition repeatedly, so it uses more CPU and
battery than push-to-talk. Stop it with `Ctrl+C`.

Run a single command without speech output:

```powershell
python main.py --once "what time is it" --no-tts
```

## Available commands

| Example | Result |
|---|---|
| `open calculator` | Opens an allow-listed application |
| `open YouTube` | Opens a configured website |
| `search the web for Python dataclasses` | Opens a browser search |
| `what time is it` | Reports local time |
| `system status` | Reports CPU, memory, and battery |
| `volume up`, `volume down`, `mute` | Sends Windows media keys |
| `remember that my appointment is Friday` | Saves a local note |
| `list notes` | Reads recent notes |
| `remind me in 10 minutes to stretch` | Saves a persistent reminder |
| `find file report` | Searches configured local folders |
| `what do you see` | Describes one webcam frame locally |
| `what did I ask before` | Recalls the previous local request |
| `list voices` | Lists installed Windows speech voices |
| `set voice to two` | Changes voice for the current session |
| `do you have internet access` | Explains local and browser connectivity |
| `explain recursion` | Uses the local Ollama model |
| `help` | Lists capabilities |

In continuous mode, prefix commands with the assistant name, for example:

```text
Jarvis, open calculator
Hey Jarvis, remind me in 20 minutes to check the oven
```

## Configuration

Edit `config.json` while Jarvis is stopped.

- `ollama.model`: local model name
- `ollama.context_length`: use `4096` for the GTX 1650's 4 GB VRAM
- `speech.silence_threshold`: raise it if background noise starts recordings;
  lower it if quiet speech is ignored
- `speech.model`: `tiny.en` is faster; `base.en` is the recommended balance;
  `small.en` is more accurate but slower
- `speech.beam_size`: higher values can improve recognition at the cost of speed
- `tts.enabled`: enables or disables speech output
- `tts.voice`: an installed Windows voice name for the default voice
- `apps`: the only applications Jarvis is permitted to launch
- `websites`: named website shortcuts
- `search_roots`: the only folders searched by `find file`
- `vision.camera_index`: change to `1` for a second camera

Application entries can contain an executable name or an absolute executable
path. If Chrome is not found, replace `chrome.exe` with its full installation
path. Do not add commands or arguments from untrusted sources to this list.

To use a private override without editing the default file, create a partial
JSON file and run:

```powershell
python main.py --config my-config.json
```

## Performance choices

For the fastest responses, retain:

```json
{
  "ollama": {
    "model": "qwen3.5:2b-q4_K_M",
    "context_length": 4096,
    "think": false
  },
  "speech": {
    "model": "base.en",
    "device": "cpu",
    "compute_type": "int8"
  }
}
```

Speech recognition runs on the CPU, leaving GPU memory available to Ollama.
Routine commands bypass the LLM entirely. Plug the laptop in and use Lenovo's
performance mode for the lowest latency.

## Privacy and safety

- Ollama is contacted only at `127.0.0.1` by default.
- Webcam images are JPEG-encoded in memory and are not saved.
- Notes, reminders, and short conversation history are stored in
  `data/jarvis.db`.
- The model cannot generate and execute arbitrary shell commands.
- Applications and file-search locations are explicitly allow-listed.
- Removing `data/jarvis.db` permanently removes the assistant's local memory.

Back up the database before deleting it if its notes or reminders matter.

## Troubleshooting

**Ollama is not reachable:** start Ollama from the Windows Start menu and run
`ollama ps`. Pull the exact model name shown in `config.json`.

**The model runs on CPU:** update the NVIDIA driver, close GPU-heavy programs,
restart Ollama, and keep context length at 4096.

**No microphone input:** allow microphone access for desktop applications in
Windows privacy settings. Confirm the correct input is the Windows default.

**Speech stops too early:** increase `speech.silence_seconds` to `1.2`.

**Speech never begins:** lower `speech.silence_threshold`, for example from
`0.015` to `0.008`.

**Camera unavailable:** close other webcam applications, grant camera access,
or change `vision.camera_index`.

**An app is not allow-listed:** add its display name and executable path to the
`apps` object in `config.json`. Jarvis intentionally refuses unknown programs.

## Project structure

```text
local-jarvis/
├── main.py
├── config.json
├── environment.yml
├── requirements.txt
├── jarvis/
│   ├── actions.py
│   ├── assistant.py
│   ├── cli.py
│   ├── config.py
│   ├── diagnostics.py
│   ├── llm.py
│   ├── memory.py
│   ├── router.py
│   ├── speech.py
│   ├── tts.py
│   └── vision.py
└── tests/
    └── test_core.py
```
