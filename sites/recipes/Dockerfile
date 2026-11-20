FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY site/ /usr/share/nginx/html/
RUN chmod -R a+rX /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=5s --timeout=3s --retries=3 \
    CMD wget -q -O /dev/null http://127.0.0.1/healthz || exit 1
