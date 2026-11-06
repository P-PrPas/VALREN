FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VALREN_HOME=/app PYTHONPATH=/app/src
WORKDIR /app
COPY src ./src
COPY config ./config
USER 1000:1000
ENTRYPOINT ["python", "-m", "valren.cli"]
CMD ["doctor"]
