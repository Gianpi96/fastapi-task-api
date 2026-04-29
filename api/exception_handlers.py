import logging
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Registra tutti gli exception handler personalizzati sull'app."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        422 — ValidationError con messaggio chiaro e leggibile.

        FastAPI di default restituisce un JSON tecnico con 'loc', 'msg', 'type'.
        Qui lo trasformiamo in errori leggibili anche da un frontend.
        """
        errors = []
        for error in exc.errors():
            # 'loc' è una tupla tipo ('body', 'title') — prendiamo l'ultimo elemento
            field = error["loc"][-1] if error["loc"] else "campo sconosciuto"
            message = error["msg"]
            errors.append({"campo": str(field), "problema": message})

        logger.warning(
            "Validation error on %s %s: %s",
            request.method,
            request.url.path,
            errors,
        )

        return JSONResponse(
            status_code=422,
            content={
                "errore": "Dati non validi",
                "dettagli": errors,
            },
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """
        Handler unificato per tutti gli HTTPException.

        - 404: messaggio personalizzato
        - 401/403: messaggio generico
        - 500: log completo server-side, messaggio generico al client
        - Tutti gli altri: passano il detail originale
        """
        if exc.status_code == 404:
            return JSONResponse(
                status_code=404,
                content={
                    "errore": "Risorsa non trovata",
                    "percorso": request.url.path,
                },
            )

        if exc.status_code == 500:
            logger.error(
                "Internal server error on %s %s: %s",
                request.method,
                request.url.path,
                exc.detail,
            )
            return JSONResponse(
                status_code=500,
                content={
                    "errore": "Errore interno del server",
                    "messaggio": "Qualcosa è andato storto. Riprova più tardi.",
                },
            )

        # 400, 401, 403, 422 — passa il detail originale
        return JSONResponse(
            status_code=exc.status_code,
            content={"errore": exc.detail},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        """
        Catch-all per eccezioni non gestite (bug, errori imprevisti).

        Logga il traceback completo server-side ma non espone
        nulla di sensibile al client.
        """
        logger.exception(
            "Unhandled exception on %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "errore": "Errore interno del server",
                "messaggio": "Qualcosa è andato storto. Riprova più tardi.",
            },
        )
