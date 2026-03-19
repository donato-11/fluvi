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
│  │  │  ├─ regions
│  │  │  │  ├─ dto
│  │  │  │  │  └─ create-region.dto.ts
│  │  │  │  ├─ regions.controller.spec.ts
│  │  │  │  ├─ regions.controller.ts
│  │  │  │  ├─ regions.module.ts
│  │  │  │  ├─ regions.service.spec.ts
│  │  │  │  └─ regions.service.ts
│  │  │  ├─ scenarios
│  │  │  │  └─ scenarios.module.ts
│  │  │  └─ streaming
│  │  │     ├─ streaming.controller.spec.ts
│  │  │     ├─ streaming.controller.ts
│  │  │     ├─ streaming.gateway.spec.ts
│  │  │     ├─ streaming.gateway.ts
│  │  │     └─ streaming.module.ts
│  │  ├─ test
│  │  │  ├─ app.e2e-spec.ts
│  │  │  └─ jest-e2e.json
│  │  ├─ tsconfig.build.json
│  │  ├─ tsconfig.json
│  │  └─ uploads
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
│  │  │  │  ├─ dto
│  │  │  │  │  └─ request-imagery.dto.ts
│  │  │  │  ├─ imagery.controller.spec.ts
│  │  │  │  ├─ imagery.controller.ts
│  │  │  │  ├─ imagery.module.ts
│  │  │  │  ├─ imagery.service.spec.ts
│  │  │  │  ├─ imagery.service.ts
│  │  │  │  ├─ processing.service.ts
│  │  │  │  └─ sentinel-hub.client.ts
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
│     │  │  ├─ scenarios.py
│     │  │  └─ __init__.py
│     │  ├─ core
│     │  │  ├─ config.py
│     │  │  ├─ database.py
│     │  │  ├─ hydrology.py
│     │  │  ├─ lstm_model
│     │  │  ├─ lstm_predictor.py
│     │  │  ├─ physics.py
│     │  │  ├─ state.py
│     │  │  └─ __init__.py
│     │  ├─ db
│     │  │  ├─ session.py
│     │  │  └─ __init__.py
│     │  ├─ main.py
│     │  ├─ models
│     │  │  ├─ rain_dto.py
│     │  │  ├─ schemas.py
│     │  │  └─ __init__.py
│     │  ├─ rain-simulator
│     │  │  └─ main.py
│     │  ├─ scripts
│     │  │  └─ train_lstm.py
│     │  └─ __init__.py
│     ├─ Dockerfile
│     └─ requirements.txt
└─ shared

```