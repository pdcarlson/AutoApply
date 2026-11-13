"""API routers, one module per api.md section. Each module exposes `router`.

Add new modules to ROUTE_MODULES; `server.app.create_app` mounts each under /api.
"""
from server.routes import (account, agent, answers, applications, auth, extension, files, jobs,
                           questions, setup)

ROUTE_MODULES = [auth, setup, agent, jobs, questions, applications, answers, account, files,
                 extension]
