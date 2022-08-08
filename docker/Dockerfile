FROM python:3.10

# app workdir
WORKDIR /app

# copy app dependencies
COPY pyproject.toml ./
COPY poetry.lock ./
COPY docker/*.sh ./

# install dependecies
RUN set -ex \
    # install system dependencies
    && apt-get update \
	&& apt-get install -y build-essential libssl-dev libffi-dev wget \
	\
    # install app dependencies
    && rm -rf /var/lib/apt/lists/* \
    && pip install poetry \
    && poetry install \
    \
    # clean pip cache
    && rm -rf /root/.cache/pip/* \
    \
    # clean system dependencies
    && apt-get clean

# build app source code
COPY . ./

# Default runtime configs
ENTRYPOINT ["./start.sh"]
CMD ["run"]