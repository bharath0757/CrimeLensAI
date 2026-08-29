import re
with open('services/graph-service/app/main.py', 'r') as f:
    content = f.read()

lifespan_new = '''async def lifespan(application: FastAPI):
    """Startup/shutdown lifecycle for Neo4j connection."""
    settings = get_settings()
    if settings.GRAPH_BACKEND.lower() == "neo4j":
        try:
            neo4j_manager.connect()
            logger.info("Neo4j connected at %s", settings.NEO4J_URI)
            from app.api.routes import store
            if hasattr(store, "hydrate"):
                store.hydrate()
        except Exception as exc:
            logger.warning("Neo4j connection failed at startup: %s", exc)
    yield
    if settings.GRAPH_BACKEND.lower() == "neo4j":
        neo4j_manager.close()
        logger.info("Neo4j connection closed")'''

content = re.sub(r'async def lifespan\(application: FastAPI\):.*?logger\.info\("Neo4j connection closed"\)', lifespan_new, content, flags=re.DOTALL)
with open('services/graph-service/app/main.py', 'w') as f:
    f.write(content)
