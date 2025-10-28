FROM node:22-slim
WORKDIR /usr/src/app

COPY package.json package-lock.json ./

RUN npm ci --production

RUN npm cache clean --force

ENV NODE_ENV="production"

ENV PORT=3000

COPY . .

CMD [ "npm", "start" ]
