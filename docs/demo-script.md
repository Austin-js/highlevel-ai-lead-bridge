# Five-minute demonstration script

1. Introduce the lead-intake problem and show the architecture diagram.
2. Start the API in demo mode and open `/health`.
3. Show `examples/new_lead.json` and post it with `python scripts/send_sample_event.py`.
4. Show the completed response, structured logs, and demo notification preview.
5. Post the same payload again and explain the duplicate response.
6. Show the provider configuration: `mock`, hosted OpenAI, Ollama, and OpenAI-compatible options.
7. Explain deterministic fallback and partial completion for failed notifications or HighLevel sync.
8. Run the automated test suite and point out the mocked HTTP client tests.
