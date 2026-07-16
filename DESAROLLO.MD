SGIMI TECNOGAS/
│
├── main.py
├── config.py
├── requirements.txt
│
├── core/
│   ├── event_bus.py
│   ├── database.py
│   ├── settings.py
│
├── models/
│   ├── product.py
│   ├── branch.py
│   ├── inventory.py
│   ├── movement.py
│   ├── user.py
│
├── modules/
│   ├── products/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │
│   ├── branches/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │
│   ├── inventory/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── handlers.py
│   │
│   ├── movements/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── repository.py
│   │   ├── handlers.py
│   │
│   ├── dashboard/
│   │   ├── routes.py
│   │   ├── service.py
│   │   ├── handlers.py
│   │
│   ├── alerts/
│   │   ├── service.py
│   │   ├── handlers.py
│   │
│   ├── reports/
│   │   ├── service.py
│   │
│   ├── history/
│       ├── service.py
│       ├── handlers.py
│
├── database/
│   ├── migrations/
│
├── utils/
│   ├── validators.py
│   ├── helpers.py
│
└── tests/
