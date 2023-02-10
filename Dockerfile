FROM alpine:3.7
EXPOSE 3031
VOLUME /usr/src/app/public
WORKDIR /usr/src/app
RUN apk add --no-cache \
        uwsgi-python \
        python \
        git \
        py-pip
COPY . .
RUN rm -rf instance/
RUN pip install --no-cache-dir -r requirements.txt
ENTRYPOINT ["./entrypoint.sh"]
CMD [ "uwsgi", "--socket", "0.0.0.0:3031", \
               "--uid", "uwsgi", \
               "--plugins", "python", \
               "--protocol", "uwsgi", \
               "--wsgi", "runquery:app" ]

