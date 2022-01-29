FROM python:3.10.2-slim-buster

WORKDIR /CODE
COPY . /CODE

RUN python -m pip install --upgrade pip
RUN pip install requests

EXPOSE 80
