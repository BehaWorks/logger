FROM continuumio/miniconda3
ENV port 8000
ENV db_host 172.17.0.1
ENV db_port 27017
ENV redis_host 172.17.0.1
ENV redis_port 6379
ENV registration_expire 600
ENV PYTHONPATH "${PYTHONPATH}:/logger/"
ARG copy=.
COPY ${copy} /logger/
WORKDIR /logger
RUN pip install -r requirements.txt
RUN conda install faiss-cpu -c pytorch
RUN pip install gunicorn
EXPOSE ${port}
CMD gunicorn -w 3 --timeout 300 --reload --bind=0.0.0.0:${port} logger:app