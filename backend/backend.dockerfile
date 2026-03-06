FROM python:3.11.3

ENV PYTHONUNBUFFERED 1

# Upgrade pip and install Poetry
RUN pip install --upgrade pip && \
    pip install "virtualenv<20.27.0" poetry==1.8.5

RUN poetry config virtualenvs.create false

# Copy poetry.lock* in case it doesn't exist in the repo
COPY ./pyproject.toml ./poetry.lock* /app/

WORKDIR /app/
RUN poetry lock --no-update && poetry install --no-interaction --no-ansi --no-root

RUN apt-get update && \
    apt-get install -y git && \
    mkdir -p checkouts/

COPY . .

RUN chmod +x /app/scripts/entrypoint.sh
RUN chmod g+w /app/certs

CMD ["/app/scripts/entrypoint.sh"]
