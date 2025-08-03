FROM alpine:latest

RUN apk add git hugo
RUN git clone --recursive https://github.com/Nelyah/website /website
WORKDIR /website

EXPOSE 1313

CMD ["hugo", "serve", "--bind", "0.0.0.0"]
