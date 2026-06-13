# Sunny fleet collector — dependency-free Python stdlib server.
FROM python:3.12-alpine

# Run as an unprivileged user (least privilege). The named volume at /data
# inherits this ownership on first creation, so the non-root process can write
# the token + run snapshots.
RUN addgroup -S sunny && adduser -S -G sunny -h /app sunny

WORKDIR /app
COPY collector.py global.html ./

ENV DATA_DIR=/data \
    PORT=8080 \
    STALE_AFTER_MIN=15 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /data && chown -R sunny:sunny /app /data

USER sunny

VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1

CMD ["python", "collector.py"]
