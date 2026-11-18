"""Gunicorn settings for the container image, read from the environment.

The image has no shell, so the variables that the old shell CMD expanded
are read here instead:

    gunicorn -c python:puppetboard.gunicorn_conf puppetboard.asgi:app
"""
import os

worker_class = 'asgi'
bind = f"{os.getenv('PUPPETBOARD_HOST', '0.0.0.0')}:{os.getenv('PUPPETBOARD_PORT', '8080')}"  # nosec B104
workers = int(os.getenv('PUPPETBOARD_WORKERS', '1'))
root_path = os.getenv('PUPPETBOARD_URL_PREFIX', '')
preload_app = True
accesslog = '-'
