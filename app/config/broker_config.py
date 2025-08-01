from pydantic import BaseModel

class BrokerConfig(BaseModel):
    """Defines the MQTT broker connection settings."""
    host: str
    port: int
    client_id: str  # Added client_id to match the new YAML structure