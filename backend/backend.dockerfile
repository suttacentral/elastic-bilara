FROM python:3.11.3

ENV PYTHONUNBUFFERED 1

# Upgrade pip and install Poetry
RUN pip install --upgrade pip && \
    pip install poetry

# Copy poetry.lock* in case it doesn't exist in the repo
COPY ./app/pyproject.toml ./app/poetry.lock* /app/

WORKDIR /app/
RUN /usr/local/bin/poetry install
RUN /usr/local/bin/poetry add package_name



COPY ./app ./.

RUN apt-get update && \
    apt-get install -y git && \
    mkdir -p /app/checkouts

RUN chmod +x /app/scripts/entrypoint.sh

CMD ["/app/scripts/entrypoint.sh"]