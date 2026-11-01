# Chess Coach: API + worker + built phone app, with the pinned Stockfish 18 (spec §8.5). Build context: repo root.
FROM gcc:13-bookworm AS stockfish
RUN git clone --depth 1 --branch sf_18 https://github.com/official-stockfish/Stockfish /sf \
 && test "$(git -C /sf rev-parse HEAD)" = "cb3d4ee9b47d0c5aae855b12379378ea1439675c"
WORKDIR /sf/src
RUN curl -sSfLo nn-c288c895ea92.nnue https://media.githubusercontent.com/media/official-stockfish/networks/master/nn-c288c895ea92.nnue \
 && curl -sSfLo nn-37f18f62d772.nnue https://raw.githubusercontent.com/official-stockfish/networks/master/nn-37f18f62d772.nnue \
 && echo "c288c895ea924429ea9092e3f36b2b3c1f00f2a3a4c759ff7e57e79e3b43e4a7  nn-c288c895ea92.nnue" | sha256sum -c \
 && echo "37f18f62d772f3107e1d6aaca3898c130c3c86f2ab63e6555fbbca20635a899d  nn-37f18f62d772.nnue" | sha256sum -c
# ARCH=native: optimized for the computer that builds the image (your home computer)
RUN make -j"$(nproc)" profile-build ARCH=native COMP=gcc && strip stockfish

FROM node:22-slim AS web
WORKDIR /web
COPY web/app/package.json web/app/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/app ./
RUN npm run build

FROM python:3.12-slim
COPY --from=stockfish /sf/src/stockfish /usr/local/bin/stockfish
WORKDIR /app
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/config ./config
COPY server/coach ./coach
COPY --from=web /web/dist /web
ENV STOCKFISH=/usr/local/bin/stockfish COACH_WEB_DIST=/web PYTHONUNBUFFERED=1
CMD ["uvicorn", "coach.api:app", "--host", "0.0.0.0", "--port", "8000"]
