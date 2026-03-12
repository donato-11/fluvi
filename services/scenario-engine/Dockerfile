FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install torch==2.6.0+cpu --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir -r requirements.txt

COPY app app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# uvicorn app.main:app --reload --port 8000 to run in development mode with hot reload