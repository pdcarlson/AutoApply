"""The API routers; `server.app.create_app` mounts each module's `router` under /api."""
from server.routes import (account, agent, answers, applications, auth, files, jobs, live,
                           postings, questions, setup)

ROUTE_MODULES = [auth, setup, agent, jobs, postings, questions, applications, answers, account,
                 files, live]
