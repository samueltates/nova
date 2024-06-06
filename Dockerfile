FROM --platform=linux/amd64 python:3.9
RUN mkdir -p /app
WORKDIR /app
COPY . .
ENV PIPENV_VENV_IN_PROJECT=1
RUN apt-get update && apt-get install redis -y
RUN pip install pipenv 
RUN pipenv install --deploy --ignore-pipfile
# RUN pipenv sync
RUN pipenv run prisma generate
EXPOSE 5500
ENV NAME World
CMD [ "pipenv", "run", "python", "./main.py"]


