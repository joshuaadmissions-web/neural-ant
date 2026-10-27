FROM node:20-alpine AS web-build
WORKDIR /web
COPY package.json ./
COPY scripts ./scripts
COPY src ./src
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY api ./api
COPY --from=web-build /web/dist ./dist
RUN mkdir -p /data/resumes
EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
