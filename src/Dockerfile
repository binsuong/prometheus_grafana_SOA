FROM python:3-slim

WORKDIR /src

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY . .

EXPOSE 9000

CMD [ "python", "./main.py" ]