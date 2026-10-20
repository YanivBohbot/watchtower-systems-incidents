FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /project/backend
COPY backend/pyproject.toml backend/requirements.lock ./
# CPU wheels keep the default build independent of NVIDIA drivers.
RUN pip install 'torch==2.14.1+cpu' 'torchvision==0.29.1+cpu' --index-url https://download.pytorch.org/whl/cpu
RUN pip install -r requirements.lock
COPY backend ./
RUN pip install --no-deps -e . && pip install 'ultralytics==8.4.182' 'lap==0.5.13'
COPY mcp_server /project/mcp_server
COPY skills /project/skills
COPY examples /project/examples
RUN useradd --uid 10001 --create-home app && mkdir -p /data && chown -R app:app /data /project
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
