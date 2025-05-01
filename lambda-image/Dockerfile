FROM public.ecr.aws/lambda/python:3.9

# Install Python deps
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy in your handler
COPY handler.py .

# Tell Lambda which function to invoke
CMD [ "handler.main" ]
