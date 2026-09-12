from api.routers import (health, config, legacy, evaluate, database,
                         conversation, case, game, mediation, innovation, research)

ALL_ROUTERS = [health.router, config.router, legacy.router, evaluate.router,
               database.router, conversation.router, case.router, game.router,
               mediation.router, innovation.router, research.router]
