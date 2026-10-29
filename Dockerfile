FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY ai08 ./ai08
COPY database ./database
COPY tests ./tests
COPY tools ./tools
CMD ["python","-m","uvicorn","ai08.api:app","--host","0.0.0.0","--port","8001"]
