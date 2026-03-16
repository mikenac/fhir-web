# frontend/frontend/Dockerfile
# Builds the React / Vite frontend image for local Docker Compose development.
#
# Build context is `frontend/frontend/` (set in docker-compose.yml).
# This runs the *development* Vite server, NOT a static production build.
# That means hot-module replacement (HMR) works for a smooth dev experience.

# ---- Base image -------------------------------------------------------------
# node:22-slim is a minimal Debian image with Node 22 LTS pre-installed.
FROM node:22-slim

# ---- Working directory -------------------------------------------------------
WORKDIR /app

# ---- Dependency files first (layer caching) ---------------------------------
# Copying only package.json (and package-lock.json if present) before the
# source code lets Docker cache the `npm install` layer.  The layer is only
# rebuilt when package.json changes, not on every source-code change.
COPY package.json .
# If you have a lock file tracked in git, copy it here too:
# COPY package-lock.json .

# ---- Install dependencies ---------------------------------------------------
# npm install reads package.json and downloads all dependencies into
# node_modules/ inside the container.  The .dockerignore file ensures we do
# NOT copy the host's node_modules/ into the build context.
RUN npm install

# ---- Copy source code -------------------------------------------------------
# Comes after npm install so code changes don't bust the dependency cache.
COPY . .

# ---- Network port -----------------------------------------------------------
# Vite dev server listens on 5173 by default.
EXPOSE 5173

# ---- Start the Vite dev server ----------------------------------------------
# --host 0.0.0.0  makes Vite listen on all network interfaces so Docker can
#                 forward traffic from the host machine to the container.
#                 Without this, Vite only listens on 127.0.0.1 inside the
#                 container and the port mapping in docker-compose.yml has no
#                 effect.
CMD ["npx", "vite", "--host", "0.0.0.0"]
