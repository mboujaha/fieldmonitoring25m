FROM node:22-alpine

WORKDIR /workspace/apps/web

COPY apps/web/package*.json /workspace/apps/web/
COPY packages/shared-types /workspace/packages/shared-types

RUN npm install

COPY apps/web /workspace/apps/web

CMD ["npm", "run", "dev"]
