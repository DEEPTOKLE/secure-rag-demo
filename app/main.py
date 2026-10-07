from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routes import health_routes, auth_routes, ingest_routes, query_routes

app = FastAPI(
    title="SecureRAG Demo",
    description="Multi-Modal RAG with retrieval-layer access control enforced in PostgreSQL.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_routes.router)
app.include_router(auth_routes.router)
app.include_router(ingest_routes.router)
app.include_router(query_routes.router)
