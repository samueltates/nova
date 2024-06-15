FROM --platform=linux/amd64 python:3.9 AS base

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONFAULTHANDLER 1


FROM base AS python-deps
RUN pip install pipenv 

RUN apt-get update && apt-get install ffmpeg -y
# RUN redis-server --port 6379 &
COPY Pipfile .
COPY Pipfile.lock .

RUN PIPENV_VENV_IN_PROJECT=1 pipenv sync

# RUN set -a && . /.env && set +a


FROM base AS runtime

COPY --from=python-deps /.venv /.venv
ENV PATH="/.venv/bin:$PATH"

RUN mkdir -p /app

ARG APP_ENV=local
ENV APP_ENV=${APP_ENV}
COPY ${APP_ENV}.env .env
WORKDIR /app
COPY . .
RUN prisma generate
RUN apt-get update && apt-get install ffmpeg -y

# RUN set -a && . /.env && set +a
# RUN echo $DATABASE_URL
# RUN echo $DATABASE_URL

EXPOSE 5500
CMD ["sleep", "infinity"]
# CMD ["python", "-m","main.py"]

# sudo docker build -t nova-multi -f dockerfilemulti/Dockerfile . 

#sudo docker build --no-cache -t oz/123:0.1 .
