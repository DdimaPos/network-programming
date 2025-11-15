FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
COPY tsconfig.json ./

RUN npm install

COPY src/ ./src/
COPY test/ ./test/
COPY boards/ ./boards/
COPY public/ ./public/

RUN npm run compile

EXPOSE 8080

CMD ["node", "dist/src/server.js", "8080", "boards/ab.txt"]
