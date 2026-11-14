# Intern (nace-ai/intern) needs Linux/macOS (fcntl, process groups). This image lets the Stego app call it from Windows.
# Build:  docker build -t stego-intern tools/intern
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv && uv tool install --python 3.12 "intern-agent @ git+https://github.com/nace-ai/intern"
ENV PATH="/root/.local/bin:${PATH}"
WORKDIR /work
