import yaml
from typing import List, Dict, Any
from pydantic import BaseModel, Field

from app.config.broker_config import BrokerConfig


# --- Camera Configuration Model ---
class CameraConfig(BaseModel):
    camera_id: str
    address: str
    port: int
    path: str
    username: str
    password: str

# --- Pipeline Inference Detail Model ---
class PipelineInferenceDetail(BaseModel):
    """Defines the settings for a single inference topic instance."""
    output_width: int
    output_height: int
    output_format: int
    output_fps: int
    url: str
    use_camera: bool = False
    camera_config: CameraConfig = None

class EngineSettings(BaseModel):
    """Defines the paths and parameters for the inference engines."""
    library_path: str
    pose_engine_file: str
    pose_cls_threshold: float
    pose_iou_threshold: float
    pose_max_batch_size: int
    efficient_engine_path: str
    efficient_max_batch_size: int

class ClientPipelineConfig(BaseModel):
    """Main configuration block for the pipeline client."""
    # Updated fields to match the new YAML structure
    output_topic: str
    enable_sources: List[str]
    engine_settings: EngineSettings
    debug_mode: bool
    window_title: str
    # This dictionary will hold the 'pipeline_inference_*' sections
    inferences: Dict[str, PipelineInferenceDetail] = Field(default_factory=dict)

    class Config:
        extra = 'allow'

class PipelineConfig(BaseModel):
    """Top-level model for the entire pipeline configuration."""
    broker: BrokerConfig
    client_pipeline: ClientPipelineConfig

# ---- Loading Function ----

def load_pipeline_config(path: str) -> PipelineConfig:
    """
    Loads and validates the updated pipeline_config.yaml file.
    """
    with open(path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)

    # --- Adjust special handling for the new structure ---
    pipeline_data = raw_config.get('client_pipeline', {})
    parsed_pipeline_data = {
        "output_topic": pipeline_data.get("output_topic", ""),
        "enable_sources": pipeline_data.get("enable_sources", []),
        "engine_settings": pipeline_data.get("engine_settings", {}),
        "debug_mode": pipeline_data.get("debug_mode", False),
        "window_title": pipeline_data.get("window_title", "Unified Pipeline"),
        "inferences": {}
    }
    
    for key, value in pipeline_data.items():
        # Updated prefix check
        if key.startswith('pipeline_inference'):
            parsed_pipeline_data['inferences'][key] = value
            
    raw_config['client_pipeline'] = parsed_pipeline_data

    return PipelineConfig.model_validate(raw_config)

# ---- Example Usage ----

if __name__ == "__main__":
    try:
        config_path = 'pipeline_config.yaml'
        config = load_pipeline_config(config_path)

        print("--- Pipeline Config Loaded Successfully ---")
        
        print(f"MQTT Broker Host: {config.broker.host}")
        print(f"Pipeline Client ID: {config.broker.client_id}")

        if config.client_pipeline.enable_sources:
            first_enabled_topic_name = config.client_pipeline.enable_sources[0]
            inference_details = config.client_pipeline.inferences[first_enabled_topic_name]
            print(f"\nDetails for first enabled topic ('{first_enabled_topic_name}'):")
            print(f"  URL: {inference_details.url}")
            print(f"  Output FPS: {inference_details.output_fps}")

    except FileNotFoundError:
        print(f"Error: The file '{config_path}' was not found.")
    except Exception as e:
        print(f"An error occurred while parsing the config: {e}")