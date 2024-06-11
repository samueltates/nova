FROM --platform=linux/amd64 python:3.9
RUN mkdir -p /app
WORKDIR /app
COPY . .
ENV PIPENV_VENV_IN_PROJECT=1
RUN apt-get update && apt-get install ffmpeg -y
# RUN redis-server --port 6379 &

RUN pip install pipenv 
RUN pipenv install --deploy --ignore-pipfile
# RUN pipenv sync
RUN pipenv run prisma generate
EXPOSE 5500
# EXPOSE 6379

ENV NAME World
CMD [ "bash", "startup.sh"]

# docker build -t nova . 
# aws configure sso --profile samazon
# aws ecr get-login-password --region us-east-1 --profile samazon | docker login --username AWS --password-stdin 914796322262.dkr.ecr.us-east-1.amazonaws.com 
# docker tag nova 914796322262.dkr.ecr.us-east-1.amazonaws.com/nova:latest
# docker push 914796322262.dkr.ecr.us-east-1.amazonaws.com/nova:latest


##attempt at multi stage
# FROM docker.io/oz123/pipenv:3.11-v2023-6-26 AS builder
# ENV PIPENV_VENV_IN_PROJECT=1
# ADD Pipfile.lock Pipfile /usr/src/
# WORKDIR /usr/src

# RUN /root/.local/bin/pipenv sync
# RUN pipenv run prisma generate
# RUN /usr/src/.venv/bin/python -c "import requests; print(requests.__version__)"
# FROM --platform=linux/amd64 docker.io/python:3.11 AS runtime
# COPY --from=builder /usr/src/.venv/ /usr/src/.venv/
# RUN /usr/src/.venv/bin/python -c "import requests; print(requests.__version__)"
# RUN mkdir -p /app
# WORKDIR /app
# EXPOSE 5500
# COPY . .
# CMD [ "bash", "startup.sh"]
