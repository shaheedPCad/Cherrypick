FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies and Typst
RUN apt-get update && apt-get install -y \
    curl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Typst binary
RUN curl -fsSL https://github.com/typst/typst/releases/download/v0.12.0/typst-x86_64-unknown-linux-musl.tar.xz \
    | tar -xJ --strip-components=1 -C /usr/local/bin

# Install Poetry
RUN pip install --no-cache-dir poetry==2.2.1

# Copy poetry files
COPY pyproject.toml ./

# Configure poetry to not create virtual environment (we're already in a container)
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
