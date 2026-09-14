# Lambda container image for the API. Runs FastAPI under the AWS Lambda Web
# Adapter (LWA): a plain Python base runs uvicorn as the main process, and the
# LWA extension bridges Lambda's runtime API to that HTTP server. The managed
# public.ecr.aws/lambda/python base is deliberately NOT used — its entrypoint is
# the RIE bootstrap, which expects a function handler and never starts uvicorn.
FROM public.ecr.aws/docker/library/python:3.11-slim

# LWA: bridges Lambda's runtime API to a normal web server on $PORT. The
# readiness check must hit a real 2xx route so init completes before invokes.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8000 PORT=8000 AWS_LWA_READINESS_CHECK_PATH=/health

LABEL org.opencontainers.image.source="https://github.com/yjkong04/central-dogma"
LABEL org.opencontainers.image.description="Multi-modal RAG over scientific papers: cited answers over text and figures"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /var/task
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/

# LWA invokes this web server; uvicorn binds $PORT.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
