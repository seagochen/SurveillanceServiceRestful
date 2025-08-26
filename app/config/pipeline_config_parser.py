import yaml
from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field
from app.config.broker_config import BrokerConfig

# --- Camera Configuration Model ---
class CameraConfig(BaseModel):
    camera_id: Optional[str] = None
    address: str
    port: Optional[int] = None
    path: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    
# --- Pipeline Inference Detail Model ---
class PipelineInferenceDetail(BaseModel):
    """Defines the settings for a single inference topic instance."""
    width: int
    height: int
    fps: int
    url: str
    alias: str
    use_camera: bool = False
    remote_support: bool = False
    camera_config: CameraConfig = None

    # 新增：可选的多检测区域，每个为 [x1, y1, x2, y2]
    detect_regions: Optional[List[List[int]]] = None

    # (可选)简单校验：确保每个框都是 4 个整数
    @classmethod
    def model_validate(cls, value):
        obj = super().model_validate(value)
        if obj.detect_regions is not None:
            for box in obj.detect_regions:
                if not (isinstance(box, list) and len(box) == 4 and all(isinstance(v, int) for v in box)):
                    raise ValueError("detect_regions must be a list of [x1, y1, x2, y2] integer lists")
        return obj

class EngineSettings(BaseModel):
    """Defines the paths and parameters for the inference engines."""
    library_path: str
    pose_engine_file: str
    pose_cls_threshold: float
    pose_iou_threshold: float
    pose_max_batch_size: int
    efficient_engine_path: str
    efficient_max_batch_size: int

class GeneralSettings(BaseModel):
    """Defines the paths and parameters for the inference engines."""
    debug_mode: bool
    window_title: str


class ClientPipelineConfig(BaseModel):
    """Main configuration block for the pipeline client."""
    # Updated fields to match the new YAML structure
    enable_sources: List[str] = Field(default_factory=list)     # ✅ 新增 2025/08/26
    disable_sources: List[str] = Field(default_factory=list)    # ✅ 新增 2025/08/26
    engine_settings: EngineSettings
    general_settings: GeneralSettings                           # ✅ 新增 2025/08/26

    # This dictionary will hold the 'pipeline_inference_*' sections
    inferences: Dict[str, PipelineInferenceDetail] = Field(default_factory=dict)
    reserved_inferences: Dict[str, PipelineInferenceDetail] = Field(default_factory=dict)

    class Config:
        extra = 'allow'

class PipelineConfig(BaseModel):
    """Top-level model for the entire pipeline configuration."""
    broker: BrokerConfig
    client_pipeline: ClientPipelineConfig


# ---- Converting to Dictionary ----

def dump_pipeline_config(cfg: PipelineConfig) -> Dict[str, Any]:
    """
    将 PipelineConfig 模型还原为“原始 YAML 结构”的 dict：
    - client_pipeline.inferences  ->  展开为若干 client_pipeline[pipeline_inference_*]
    - 其余顶层/子结构保持不变
    """
    # 先做一个“接近 YAML”的 dict
    d = cfg.model_dump(by_alias=False)  # pydantic v2

    # 拉平 inferences
    client_pipeline = d.get("client_pipeline", {})
    inf_map: Dict[str, Any] = client_pipeline.pop("inferences", {}) or {}

    # 注意：把 inferences 的每一项展开回 pipeline_inference_* 键
    for k, v in inf_map.items():
        client_pipeline[k] = v

    # 返回替换后的 dict
    d["client_pipeline"] = client_pipeline
    return d


# ---- Saving (new) ----

def save_pipeline_config(path: str, cfg: PipelineConfig) -> None:
    """
    将模型保存到给定 YAML 路径，保持原有文件结构（含 pipeline_inference_* 的扁平布局）。
    """
    import yaml
    raw = dump_pipeline_config(cfg)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False, allow_unicode=True)


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
        "enable_sources": pipeline_data.get("enable_sources", []),
        "disable_sources": pipeline_data.get("disable_sources", []),
        "engine_settings": pipeline_data.get("engine_settings", {}),
        "debug_mode": pipeline_data.get("debug_mode", False),
        "general_settings": pipeline_data.get("general_settings", {}),      # ✅ 新增 2025/08/26
        "window_title": pipeline_data.get("window_title", "Unified Pipeline"),
        "inferences": {}
    }

    # 解析全部的 pipeline_inference 配置信息
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
            print(f"  Output FPS: {inference_details.fps}")

    except FileNotFoundError:
        print(f"Error: The file '{config_path}' was not found.")
    except Exception as e:
        print(f"An error occurred while parsing the config: {e}")