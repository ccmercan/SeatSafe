from contextlib import asynccontextmanager

from fastapi import FastAPI

from seatsafe.api.correlation import CorrelationIdMiddleware
from seatsafe.api.problem_details import install_problem_handlers
from seatsafe.api.routes.health import router as health_router
from seatsafe.api.routes.holds import router as holds_router
from seatsafe.config import Settings, get_settings
from seatsafe.db.session import create_database_engine, create_session_factory


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    database_engine = create_database_engine(resolved_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await database_engine.dispose()

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database_engine = database_engine
    app.state.session_factory = create_session_factory(app.state.database_engine)

    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: resolved_settings

    app.add_middleware(CorrelationIdMiddleware)
    install_problem_handlers(app)
    app.include_router(health_router)
    app.include_router(holds_router)
    return app


app = create_app()
