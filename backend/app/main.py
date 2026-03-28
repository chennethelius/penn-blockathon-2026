from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(
    title="TronTrust API",
    description="Trust layer for the Tron agent economy",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import routers
from app.routers import trust, token, review, commercial, sentinel, passport, sunpoints, x402, wallet, arena

app.include_router(trust.router, prefix="/api/v1", tags=["trust"])
app.include_router(token.router, prefix="/api/v1", tags=["token"])
app.include_router(review.router, prefix="/api/v1", tags=["review"])
app.include_router(commercial.router, prefix="/api/v1", tags=["commercial"])
app.include_router(sentinel.router, prefix="/api/v1", tags=["sentinel"])
app.include_router(passport.router, prefix="/api/v1", tags=["passport"])
app.include_router(sunpoints.router, prefix="/api/v1", tags=["sunpoints"])
app.include_router(x402.router, prefix="/api/x402", tags=["x402"])
app.include_router(wallet.router, prefix="/api/v1", tags=["wallet"])
app.include_router(arena.router, prefix="/api/v1", tags=["arena"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "trontrust-api"}
