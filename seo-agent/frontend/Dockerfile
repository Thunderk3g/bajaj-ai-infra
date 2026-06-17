# seo-agent/frontend/Dockerfile
FROM docker.io/library/node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

EXPOSE 3002

# Placeholder start command — replace with your real frontend (e.g. Next.js).
CMD ["npm", "start"]
