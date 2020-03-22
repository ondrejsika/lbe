FROM python:2.7-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
ENTRYPOINT [ "python", "lbe.py" ]
CMD [ "--help" ]
