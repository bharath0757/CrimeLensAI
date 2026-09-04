from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "neo4j_dev_password"
    GRAPH_BACKEND: str = "memory"
    SERVICE_NAME: str = "graph"
    SERVICE_VERSION: str = "0.1.0"

@lru_cache()
def get_settings():
    return Settings()
