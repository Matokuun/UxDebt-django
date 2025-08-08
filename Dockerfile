FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    git pkg-config gcc \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Matokuun/UxDebt-django.git src
WORKDIR /app/src

RUN pip install --upgrade pip
RUN pip install -r requirements.txt

RUN chmod 777 start.sh

EXPOSE 8000

CMD ["./start.sh"]