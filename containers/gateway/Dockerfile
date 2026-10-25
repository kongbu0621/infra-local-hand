# The caller must select and retain an exact official nginx Alpine image digest.
ARG NGINX_BASE_IMAGE
FROM ${NGINX_BASE_IMAGE}
USER 0:0
RUN test -x /usr/sbin/nginx \
    && apk add --no-cache 'python3>=3.12' py3-pip \
    && python3 -m venv /opt/local-hand/gateway
COPY wheels/ /opt/local-hand/wheels/
RUN /opt/local-hand/gateway/bin/python -m pip install --no-index --no-deps --no-compile /opt/local-hand/wheels/*.whl \
    && rm -rf /opt/local-hand/wheels
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
ENTRYPOINT ["/opt/local-hand/gateway/bin/python", "-B", "-m", "local_hand_mcp.gateway_guard"]
CMD ["--config", "/etc/local-hand/gateway.json"]
