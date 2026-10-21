# Contributing to WAVoice

Thank you for your interest in contributing to **WAVoice**! WAVoice is an open-source bootstrap accelerator and telephony plumbing engine connecting WhatsApp Voice Calling to conversational voice AI ecosystems.

We welcome contributions of all kinds: bug reports, documentation improvements, new provider adapters, and performance optimizations.

---

## Code of Conduct

We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please treat all contributors and maintainers with respect, empathy, and constructive feedback.

---

## Getting Started

### Prerequisites
- **Python**: Version `>= 3.12`
- **Package Manager**: [`uv`](https://github.com/astral-sh/uv) (recommended) or standard `pip`
- **Git**

### Local Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/<your-username>/wavoice.git
   cd wavoice
   ```

2. Create a virtual environment and install dependencies with `uv`:
   ```bash
   uv sync --all-groups
   ```

3. Copy the example environment variables:
   ```bash
   cp .env.example .env
   ```

---

## Development Guidelines

### Repository Architecture & Invariants

Before modifying code, please review [`AGENTS.md`](./AGENTS.md) for detailed architecture invariants:
* **Provider Isolation**: Third-party voice runtimes (Pipecat, LiveKit, Retell, Vapi, Dograh) live exclusively under `src/wavoice/providers/<provider_name>/` and must inherit from `BaseProvider` (`validate_credentials`, `setup`, `doctor`). Core networking and Meta Graph API logic remain in `src/wavoice/core/`.
* **Safe Secrets Handling**: Never hardcode, commit, or log credentials. Secrets must load dynamically via `wavoice.core.config.Settings` from `.env`.
* **Deterministic Deduplication**: Inbound calls are claim-locked using `CallLifecycleManager` in `src/wavoice/core/lifecycle.py` to prevent duplicate parallel WebRTC peer connections.

### Running Tests

WAVoice maintains an automated test suite verifying HMAC verification, SDP offer/answer translations, client API schemas, and provider routing.

Run all tests using `uv`:
```bash
uv run pytest
```

To run a specific test suite:
```bash
uv run pytest tests/test_wavoice.py
uv run pytest tests/test_livekit.py
uv run pytest tests/test_vapi.py
```

All pull requests must pass the complete test suite before merging.

### Adding a New Provider

To add a new voice AI provider or transport:
1. Create a dedicated folder: `src/wavoice/providers/<provider_name>/`
2. Implement `BaseProvider` in `provider.py`.
3. Provide a REST client in `client.py` if interacting with the provider's API.
4. Add automated test coverage in `tests/test_<provider_name>.py`.
5. Register the provider CLI commands in `src/wavoice/cli.py`.

---

## Submitting Pull Requests

1. **Branch Naming**: Use descriptive branch names:
   * `feat/add-provider-name`
   * `fix/sdp-media-attribute`
   * `docs/update-pipecat-guide`
2. **Commit Messages**: Follow standard conventional commits (e.g., `feat: support custom ICE servers`, `fix: handle expired webhook token gracefully`).
3. **Run Tests**: Verify that `uv run pytest` passes cleanly.
4. **Open a PR**: Submit a pull request against `main`. Provide a clear description of the problem solved, testing performed, and any breaking changes.

---

## Reporting Issues & Security

* **Bug Reports & Feature Requests**: Please use the [GitHub Issue Tracker](https://github.com/amitbhakt/wavoice/issues) to report bugs or suggest enhancements.
* **Security Vulnerabilities**: If you discover a security vulnerability (such as a credential exposure or cryptographic issue with HMAC verification), please do not open a public issue. Contact the maintainers directly at `yashubhakt@gmail.com`.
