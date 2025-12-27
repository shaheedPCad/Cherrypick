FROM node:20-alpine

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install pnpm
RUN npm install -g pnpm

# Install dependencies (when package.json has content)
# RUN pnpm install

# Copy application code
COPY . .

# Expose port
EXPOSE 3000

# Development command (placeholder until Next.js is initialized)
CMD ["echo", "Frontend not yet initialized. Run pnpm create next-app to initialize."]
