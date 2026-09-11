# Lambda container image for the API. Runs FastAPI under the AWS Lambda Web
# Adapter (LWA) so the same uvicorn app serves both Lambda invokes and local runs.
FROM public.ecr.aws/lambda/python:3.11

# LWA: bridges Lambda's runtime API to a normal web server on $PORT.
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8000 PORT=8000

LABEL org.opencontainers.image.source="https://github.com/yjkong04/central-dogma"
LABEL org.opencontainers.image.description="Multi-modal RAG over scientific papers: cited answers over text and figures"
LABEL org.opencontainers.image.licenses="MIT"

WORKDIR /var/task
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ ./api/

# LWA invokes this web server; uvicorn binds $PORT.
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
