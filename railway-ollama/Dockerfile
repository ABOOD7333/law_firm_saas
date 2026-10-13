FROM ollama/ollama:latest

ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_MODEL=qwen2.5:3b

COPY railway-ollama/start.sh /usr/local/bin/ollama-start
RUN chmod 0755 /usr/local/bin/ollama-start

EXPOSE 11434
ENTRYPOINT ["/bin/sh", "/usr/local/bin/ollama-start"]
