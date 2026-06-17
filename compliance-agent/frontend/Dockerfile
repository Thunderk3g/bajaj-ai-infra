# compliance-agent/frontend/Dockerfile
FROM docker.io/library/node:20-alpine

WORKDIR /app

# Install dependencies first for better layer caching
COPY package.json ./
RUN npm install

# App code
COPY . .

EXPOSE 3000

# Placeholder start command — replace with your real frontend (e.g. Next.js).
CMD ["npm", "start"]
