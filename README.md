```
fluvi
├─ infra
│  └─ docker-compose.yml
├─ README.md
├─ services
│  ├─ api-gateway
│  │  ├─ .prettierrc
│  │  ├─ Dockerfile
│  │  ├─ eslint.config.mjs
│  │  ├─ nest-cli.json
│  │  ├─ package-lock.json
│  │  ├─ package.json
│  │  ├─ persistence
│  │  │  ├─ persistence.module.ts
│  │  │  ├─ repositories
│  │  │  │  └─ water-level.repository.ts
│  │  │  └─ supabase.client.ts
│  │  ├─ README.md
│  │  ├─ src
│  │  │  ├─ app.controller.spec.ts
│  │  │  ├─ app.controller.ts
│  │  │  ├─ app.module.ts
│  │  │  ├─ app.service.ts
│  │  │  ├─ auth
│  │  │  │  └─ auth.module.ts
│  │  │  ├─ main.ts
│  │  │  ├─ scenarios
│  │  │  │  └─ scenarios.module.ts
│  │  │  └─ streaming
│  │  │     └─ streaming.module.ts
│  │  ├─ test
│  │  │  ├─ app.e2e-spec.ts
│  │  │  └─ jest-e2e.json
│  │  ├─ tsconfig.build.json
│  │  └─ tsconfig.json
│  ├─ climate-ingestor
│  │  ├─ .prettierrc
│  │  ├─ Dockerfile
│  │  ├─ eslint.config.mjs
│  │  ├─ nest-cli.json
│  │  ├─ package-lock.json
│  │  ├─ package.json
│  │  ├─ README.md
│  │  ├─ src
│  │  │  ├─ app.controller.spec.ts
│  │  │  ├─ app.controller.ts
│  │  │  ├─ app.module.ts
│  │  │  ├─ app.service.ts
│  │  │  ├─ main.ts
│  │  │  └─ rainfall
│  │  │     ├─ rainfall.gateway.spec.ts
│  │  │     ├─ rainfall.gateway.ts
│  │  │     ├─ rainfall.module.ts
│  │  │     ├─ rainfall.service.spec.ts
│  │  │     └─ rainfall.service.ts
│  │  ├─ test
│  │  │  ├─ app.e2e-spec.ts
│  │  │  └─ jest-e2e.json
│  │  ├─ tsconfig.build.json
│  │  └─ tsconfig.json
│  ├─ satellite-imagery
│  │  ├─ .prettierrc
│  │  ├─ data
│  │  ├─ dockerfile
│  │  ├─ eslint.config.mjs
│  │  ├─ nest-cli.json
│  │  ├─ package-lock.json
│  │  ├─ package.json
│  │  ├─ README.md
│  │  ├─ src
│  │  │  ├─ app.controller.spec.ts
│  │  │  ├─ app.controller.ts
│  │  │  ├─ app.module.ts
│  │  │  ├─ app.service.ts
│  │  │  ├─ imagery
│  │  │  │  ├─ copernicus.client.ts
│  │  │  │  ├─ dto
│  │  │  │  │  └─ request-imagery.dto.ts
│  │  │  │  ├─ imagery.controller.spec.ts
│  │  │  │  ├─ imagery.controller.ts
│  │  │  │  ├─ imagery.module.ts
│  │  │  │  ├─ imagery.service.spec.ts
│  │  │  │  ├─ imagery.service.ts
│  │  │  │  └─ processing.service.ts
│  │  │  └─ main.ts
│  │  ├─ test
│  │  │  ├─ app.e2e-spec.ts
│  │  │  └─ jest-e2e.json
│  │  ├─ tsconfig.build.json
│  │  └─ tsconfig.json
│  └─ scenario-engine
│     ├─ app
│     │  ├─ api
│     │  │  ├─ basins.py
│     │  │  ├─ ingest.py
│     │  │  └─ __init__.py
│     │  ├─ core
│     │  │  ├─ config.py
│     │  │  ├─ database.py
│     │  │  ├─ hydrology.py
│     │  │  ├─ physics.py
│     │  │  └─ __init__.py
│     │  ├─ db
│     │  │  ├─ session.py
│     │  │  └─ __init__.py
│     │  ├─ main.py
│     │  ├─ models
│     │  │  ├─ rain_dto.py
│     │  │  ├─ schemas.py
│     │  │  └─ __init__.py
│     │  └─ __init__.py
│     ├─ Dockerfile
│     └─ requirements.txt
└─ shared

```