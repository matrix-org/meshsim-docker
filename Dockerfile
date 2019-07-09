ARG PYTHON_VERSION=3

###
### Stage 0: python builder
###
FROM docker.io/python:${PYTHON_VERSION}-slim-stretch as python-builder

# install the OS build deps

RUN apt-get update && apt-get install -y \
        build-essential \
        libffi-dev \
        sqlite3 \
        libssl-dev \
        libjpeg-dev \
        libxslt1-dev \
        libxml2-dev \
        libpq-dev

# for ksm_preload
RUN apt-get install -y \
        git \
        cmake

# build things which have slow build steps, before we copy synapse, so that
# the layer can be cached.
#
# (we really just care about caching a wheel here, as the "pip install" below
# will install them again.)

RUN pip install --prefix="/install" --no-warn-script-location \
        cryptography \
        msgpack-python \
        pillow \
        pynacl

# N.B. to work, this needs:
# echo 1 > /sys/kernel/mm/ksm/run
# echo 31250 > /sys/kernel/mm/ksm/pages_to_scan # 128MB of 4KB pages at a time
# echo 10000 > /sys/kernel/mm/ksm/pages_to_scan # 40MB of pages at a time
# ...to be run in the Docker host

RUN git clone https://github.com/unbrice/ksm_preload && \
    cd ksm_preload && \
    cmake . && \
    make && \
    cp libksm_preload.so /install/lib

# now install synapse and all of the python deps to /install.

COPY synapse/ /synapse
RUN pip install --prefix="/install" --no-warn-script-location \
        lxml \
        psycopg2-binary \
        /synapse

# for topologiser
RUN pip install --prefix="/install" --no-warn-script-location flask


###
### Stage 1: Go build
###

FROM docker.io/golang:1.12-stretch as go-builder

COPY coap-proxy /build
WORKDIR /build

RUN go build

###
### Stage 2: runtime
###

FROM docker.io/python:${PYTHON_VERSION}-slim-stretch

RUN apt-get update && apt-get install -y \
    procps \
    net-tools \
    iproute2 \
    tcpdump \
    traceroute \
    mtr-tiny \
    inetutils-ping \
    less \
    lsof \
    supervisor \
    netcat \
    python-psycopg2 \
    libpq-dev

COPY --from=python-builder /install /usr/local

COPY --from=go-builder /build/coap-proxy /proxy/bin/
COPY coap-proxy/maps /proxy/maps

COPY ./meshsim/topologiser /topologiser

COPY ./meshsim-docker/start.sh /
COPY ./meshsim-docker/start-synapse.py /
COPY ./meshsim-docker/conf /conf
COPY ./meshsim-docker/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

VOLUME ["/data"]

EXPOSE 8008/tcp 8448/tcp 3000/tcp 5683/udp

ENV LD_PRELOAD=/usr/local/lib/libksm_preload.so

# default is 32768 (8 4KB pages)
ENV KSMP_MERGE_THRESHOLD=16384

ENTRYPOINT ["/start.sh"]
