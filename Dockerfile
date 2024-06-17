# FROM --platform=linux/amd64 python:3.9 AS base

# ENV LANG C.UTF-8
# ENV LC_ALL C.UTF-8
# ENV PYTHONDONTWRITEBYTECODE 1
# ENV PYTHONFAULTHANDLER 1


# FROM base AS python-deps
# RUN pip install pipenv 

# # RUN apt-get update && apt-get install ffmpeg -y
# # RUN redis-server --port 6379 &
# COPY Pipfile .
# COPY Pipfile.lock .

# RUN PIPENV_VENV_IN_PROJECT=1 pipenv sync

# # RUN set -a && . /.env && set +a


# FROM base AS runtime

# COPY --from=python-deps /.venv /.venv
# ENV PATH="/.venv/bin:$PATH"

# RUN mkdir -p /app

# ARG APP_ENV=local
# ENV APP_ENV=${APP_ENV}
# COPY ${APP_ENV}.env /app/.env
# WORKDIR /app
# COPY . .
# RUN prisma generate
# RUN apt-get update && apt-get install ffmpeg -y

# # RUN set -a && . /.env && set +a
# # RUN echo $DATABASE_URL
# # RUN echo $DATABASE_URL

# EXPOSE 5500
# # CMD ["sleep", "infinity"]
# CMD ["python", "main.py"]

# # sudo docker build -t nova-multi -f dockerfilemulti/Dockerfile . 

# #sudo docker build --no-cache -t oz/123:0.1 .



# SINGLE LAYER APPROACH

FROM --platform=linux/amd64 python:3.9


## DEBUG echo contentsof env file
# RUN cat .env 

RUN mkdir -p /app

ARG APP_ENV=local
ENV APP_ENV=${APP_ENV}
COPY ${APP_ENV}.env /app/.env
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
# CMD [ "bash", "startup.sh"]
CMD [ "pipenv", "run", "python", "./main.py"]

# docker build -t nova . 
# aws configure sso --profile samazon
# aws ecr get-login-password --region us-east-1 --profile samazon | docker login --username AWS --password-stdin 914796322262.dkr.ecr.us-east-1.amazonaws.com 
# docker tag nova 914796322262.dkr.ecr.us-east-1.amazonaws.com/nova:latest
# docker push 914796322262.dkr.ecr.us-east-1.amazonaws.com/nova:latest

# staging
# docker build -t nova-staging . --build-arg APP_ENV=staging
# docker tag nova-staging 914796322262.dkr.ecr.us-east-1.amazonaws.com/nova:latest
# docker push 914796322262.dkr.ecr.us-east-1.amazonaws.com/nova:latest


