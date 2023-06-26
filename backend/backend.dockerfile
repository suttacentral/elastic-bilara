FROM python:3.11.3

# Upgrade pip and install Poetry
RUN pip install --upgrade pip && \
    pip install poetry

# Copy poetry.lock* in case it doesn't exist in the repo
COPY ./app/pyproject.toml ./app/poetry.lock* /app/

WORKDIR /app/
RUN /usr/local/bin/poetry install

COPY ./app ./.

CMD ["poetry", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]