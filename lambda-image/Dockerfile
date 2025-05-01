FROM public.ecr.aws/lambda/python:3.9-arm64

# Set working directory
WORKDIR /var/task

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy in handler code
COPY handler.py .

# Specify Lambda entrypoint
CMD [ "handler.main" ]
