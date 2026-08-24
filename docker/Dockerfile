FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5545
CMD ["gunicorn", "--bind", "0.0.0.0:5545", "--workers", "2", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "--access-logformat", "%(h)s \"%(r)s\" %(s)s %(D)sus", \
     "wsgi:app"]
