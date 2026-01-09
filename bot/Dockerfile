FROM node:24-slim

WORKDIR /usr/src/app

COPY package.json package-lock.json ./

RUN npm ci

COPY . .

RUN npm run build

RUN npm prune --production && npm cache clean --force

ENV NODE_ENV="production"
ENV PORT=3000

CMD [ "npm", "start" ]
