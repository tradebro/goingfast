FROM python:3.8-slim

# app workdir
WORKDIR /app

# copy app dependencies
COPY requirements.txt docker/*.sh ./

# install dependecies
RUN set -ex \
    # install system dependencies
    && apt-get update \
	&& apt-get install -y build-essential libssl-dev libffi-dev wget \
	\
    # install app dependencies
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install -r ./requirements.txt --upgrade \
    \
    # clean pip cache
    && rm -rf /root/.cache/pip/* \
    \
    # clean system dependencies
    && apt-get clean

# build app source code
COPY . ./

# Default runtime configs
EXPOSE 8080
ENTRYPOINT ["./start.sh"]
CMD ["run"]