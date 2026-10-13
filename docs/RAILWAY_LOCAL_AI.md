# Private AI service on Railway

The web application sends prompts only to Ollama over Railway's private network. Create an Ollama service in the **same Railway project and environment** as the web app; do not generate a public domain for Ollama.

## Create the Ollama service

1. Add another service from the same GitHub repository.
2. Set its Dockerfile path to `railway-ollama/Dockerfile` and keep the repository root as the build context.
3. Set `OLLAMA_MODEL=qwen2.5:3b` on that service.
4. Attach a Railway Volume at `/root/.ollama` so downloaded model files survive redeploys.
5. Leave public networking disabled. The service listens on port `11434` for private service-to-service traffic.

## Configure the web service

Set these variables on the FastAPI service:

```text
USE_LOCAL_LLM=true
OLLAMA_API_URL=http://ollama.railway.internal:11434/api/generate
OLLAMA_MODEL=qwen2.5:3b
```

The hostname uses Railway's private DNS label. If the Ollama service has a different name, update the hostname to `<service-name>.railway.internal`. The web service's code rejects non-private Ollama URLs to prevent sending office data to a public model endpoint.

The first Ollama start downloads the configured model into the persistent volume. Ensure the Railway service has enough memory and CPU for the chosen model. The local development Compose file starts the same service and connects the app to `http://ollama:11434/api/generate`.
