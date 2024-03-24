FROM python:3.10 AS build
ENV APP_HOME /app
WORKDIR $APP_HOME
COPY . .
RUN pip install -r requirements.txt

FROM python:3.10-slim AS runtime
COPY --from=build . .
WORKDIR /app
EXPOSE 3000
ENTRYPOINT ["python", "main.py"]
