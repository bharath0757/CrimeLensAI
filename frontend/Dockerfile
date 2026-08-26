# ---- CrimeLensAI: Web Frontend ----
# Dev server for Docker Compose — uses npm run dev
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

EXPOSE 5173

# Vite dev server bound to 0.0.0.0 for Docker access
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
