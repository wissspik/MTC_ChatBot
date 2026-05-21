FROM node:20-alpine AS build

WORKDIR /app

ARG VITE_API_BASE_URL=http://localhost:8000
ARG VITE_APP_TITLE=Progressors WebApp
ARG VITE_ALLOWED_HOSTS=.ngrok-free.dev,.ngrok-free.app
ARG VITE_DEV_TELEGRAM_ID=123

ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
ENV VITE_APP_TITLE=$VITE_APP_TITLE
ENV VITE_ALLOWED_HOSTS=$VITE_ALLOWED_HOSTS
ENV VITE_DEV_TELEGRAM_ID=$VITE_DEV_TELEGRAM_ID

COPY frontend/web/package*.json ./
RUN npm ci

COPY frontend/web ./
RUN npm run build

FROM node:20-alpine

WORKDIR /app
RUN npm install -g vite@6.4.2

COPY --from=build /app/dist ./dist

EXPOSE 5173

CMD ["vite", "preview", "--host", "0.0.0.0", "--port", "5173"]
