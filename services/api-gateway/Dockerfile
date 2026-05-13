# Stage 1: Build (Compilar TypeScript)
FROM node:20-alpine AS builder
 
# Instalar GDAL
RUN apk add --no-cache gdal gdal-tools

WORKDIR /app
 
# Copiar package files
COPY package*.json ./
COPY tsconfig*.json ./
COPY nest-cli.json .
 
# Instalar TODAS las dependencias (incluyendo devDependencies para compilar)
RUN npm install
 
# Copiar código fuente
COPY src ./src
 
# Compilar TypeScript → JavaScript
RUN npm run build
 
# Verificar que el build fue exitoso
RUN test -f dist/main.js && echo "✅ Build exitoso: dist/main.js existe" || (echo "❌ ERROR: dist/main.js no fue generado" && exit 1)
 
# Stage 2: Runtime (Ejecutar aplicación)
FROM node:20-alpine

RUN apk add --no-cache gdal gdal-tools
 
WORKDIR /app
 
# Copiar package files
COPY package*.json ./
 
# Instalar SOLO dependencias de producción
RUN npm install --omit=dev
 
# Copiar el código compilado del stage anterior
COPY --from=builder /app/dist ./dist
 
# Crear usuario no-root por seguridad
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nestjs -u 1001 && \
    chown -R nestjs:nodejs /app
 
USER nestjs
 
# Puerto (debe coincidir con lo que escucha NestJS)
EXPOSE 3000
 
# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})" || exit 1
 
# Comando final: ejecutar el JavaScript compilado
CMD ["node", "dist/main.js"]
