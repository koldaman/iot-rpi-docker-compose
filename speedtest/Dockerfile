FROM python:alpine

ADD . /src
WORKDIR /src

RUN pip install -r requirements.txt

CMD ["python", "/src/InfluxdbSpeedtest.py"]
