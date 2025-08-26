import yaml
from typing import List
from pydantic import BaseModel
from app.config.broker_config import BrokerConfig

# ---- 区域空间配置模型 ----

class KeyAreaConfig(BaseModel):
    """Defines the virtual fence settings."""
    alpha: float
    area: List[List[int]]
    color: str
    real_width: int
    real_height: int


# ---- 处罚决策配置模型 ----

class PenaltyConfig(BaseModel):
    """Defines the structure for a single penalty rule."""
    enable: bool
    threshold: int
    penalty_score: int

class PenaltyDecisionConfig(BaseModel):
    """Container for all penalty decision rules."""
    look_around: PenaltyConfig
    theft_detection: PenaltyConfig
    long_time_squat: PenaltyConfig
    loitering_distance: PenaltyConfig
    loitering_reentry: PenaltyConfig
    loitering_enter_area: PenaltyConfig

class AlertConfig(BaseModel):
    level0: int
    level1: int
    level2: int
    level3: int
    level4: int
    level5: int

# ---- 云服务配置模型 ----

class CloudServConfig(BaseModel):
    script: str
    device_id: str
    action_code: str

class CloudConfig(BaseModel):
    enable: bool
    blocking_duration: int
    upload_level: int
    sceptical_image: CloudServConfig
    patrol_image: CloudServConfig

# ---- ClientMagistrate 配置模型 ----

class ClientMagistrateConfig(BaseModel):
    """
    Defines the settings for the magistrate client.
    This model is now static, reflecting the simpler YAML structure.
    """
    input_topic: str
    subscribe_source: str
    key_area_settings: KeyAreaConfig            # 重点区域设置
    key_area_strategy: PenaltyDecisionConfig    # 重点区域策略
    normal_area_strategy: PenaltyDecisionConfig # 普通区域策略
    alert_settings: AlertConfig                 # 警告配置
    cloud: CloudConfig                          # 云服务配置

# ---- General Settings 配置 ----
class GeneralSettingsConfig(BaseModel):
    cache_retention_duration: int               # 数据缓存保留时间，单位为秒
    schema_config: str                          # 绘图方案
    use_enhanced_tracking: bool                 # 是否使用DeepSORT
    enable_debug_mode: bool                     # 是否启动debug模式
    display_width: int                          # 显示画面的宽
    display_height: int                         # 显示画面的高
    sma_window_size: int                        # SMA平滑窗口大小
    delta_duration_threshold: float             # 判断有效数据的最小时间
    delta_distance_threshold: float             # 判断有效数据的最小移动距离
    reentry_angle_threshold: float              # 折返角度
    min_consecutive_count: int                  # 最少连续数
    min_keypoint_distance: float                # 最小关键点距离

# ---- YAML ----
class MagistrateConfig(BaseModel):
    """Top-level model for the entire magistrate configuration."""
    broker: BrokerConfig
    client_magistrate: ClientMagistrateConfig
    general_settings: GeneralSettingsConfig

# ---- Loading Function ----

def load_magistrate_config(path: str) -> MagistrateConfig:
    """
    Loads and validates the simplified magistrate_config.yaml file.
    """
    with open(path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)
    
    # No special handling is needed anymore due to the static structure.
    # Pydantic can parse this directly.
    return MagistrateConfig.model_validate(raw_config)

# ---- Saving (NEW) ----
def save_magistrate_config(path: str, cfg: MagistrateConfig) -> None:
    import yaml
    raw = cfg.model_dump()
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(raw, f, sort_keys=False, allow_unicode=True)

# ---- Example Usage ----

if __name__ == "__main__":
    config_path=None
    try:
        config_path = 'magistrate_config.yaml'
        config = load_magistrate_config(config_path)

        print("--- Magistrate Config Loaded Successfully ---")

        # Accessing data is now more direct
        magistrate_settings = config.client_magistrate
        
        print(f"  Input Topic: {magistrate_settings.input_topic}")
        
        loitering_penalty_score = magistrate_settings.penalty_decision.loitering_duration.penalty_score
        print(f"  Loitering Duration Penalty Score: {loitering_penalty_score}")

    except FileNotFoundError:
        print(f"Error: The file '{config_path}' was not found.")
    except Exception as e:
        print(f"An error occurred while parsing the config: {e}")