FROM python:3.13-slim

WORKDIR /app

RUN adduser \
    --disabled-password \
    --gecos "" \
    appuser

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

USER appuser

CMD ["python", "generator.py"]