from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from debrief_agent.core.config import DATABASE_URL

# --- Create async engine ---
engine = create_async_engine(
    DATABASE_URL,  # where to connect
    echo=False,  # logs all SQL to stdout — useful during development
    future=True,  # use new async features
    pool_pre_ping=True,  # check connection health before using it
)

# --- Session factory ---
AsyncSessionLocal = async_sessionmaker(
    bind=engine,  # which engine/database to talk to
    class_=AsyncSession,  # what type of session to create
    expire_on_commit=False,  # keep data accessible after commit
)


# --- Declarative base (all ORM models inherit from this) ---
class Base(DeclarativeBase):
    pass


# --- FastAPI dependency ---
async def get_db() -> AsyncSession:
    """
    Yields an async database session for use in FastAPI route dependencies.

    Usage in a route:
        @router.get("/example")
        async def example(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
