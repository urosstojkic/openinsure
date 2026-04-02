FROM node:20 AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN node ./node_modules/typescript/bin/tsc -b && node ./node_modules/vite/bin/vite.js build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf.template

RUN addgroup --system appuser && adduser --system --ingroup appuser appuser \
    && mkdir -p /var/cache/nginx /var/run /var/log/nginx \
    && chown -R appuser:appuser /var/cache/nginx /var/run /var/log/nginx /etc/nginx/conf.d /usr/share/nginx/html
USER appuser

EXPOSE 80
CMD ["/bin/sh", "-c", "envsubst '$OPENINSURE_API_KEY' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
