"""API routers, one module per api.md section. Each module exposes `router`.

Add new modules to ROUTE_MODULES; `server.app.create_app` mounts each under /api.
"""
from server.routes import account, agent, auth, files, setup

ROUTE_MODULES = [auth, setup, agent, account, files]
