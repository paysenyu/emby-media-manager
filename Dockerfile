FROM python:3.11-slim

WORKDIR /app

ENV TZ=Asia/Shanghai

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

EXPOSE 5000

CMD ["python", "run.py"]