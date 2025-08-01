import yaml
from pydantic import BaseModel


# ---- Pydantic Models for recorder_config.yaml ----

class ClientRecordDetail(BaseModel):
    """Defines the video recording settings."""
    filename_base: str
    format: str
    input_width: int
    input_height: int
    input_fps: int
    url: str


class RecorderConfig(BaseModel):
    """Top-level model for the recorder configuration."""
    client_record: ClientRecordDetail


# ---- Loading Function ----

def load_recorder_config(path: str) -> RecorderConfig:
    """
    Loads and validates the recorder_config.yaml file using Pydantic models.
    """
    with open(path, 'r', encoding='utf-8') as f:
        raw_config = yaml.safe_load(f)

    # No special handling needed as the structure is static
    return RecorderConfig.model_validate(raw_config)


# ---- Example Usage ----

if __name__ == "__main__":
    try:
        # Replace with the actual path to your file
        config_path = 'recorder_config.yaml'
        config = load_recorder_config(config_path)

        print("--- Recorder Config Loaded Successfully ---")

        # Accessing data
        record_settings = config.client_record
        print(f"Recording Enabled: {record_settings.enable_recording}")
        print(f"Output Filename Base: {record_settings.filename_base}")
        print(f"Input FPS for Recording: {record_settings.input_fps}")

    except FileNotFoundError:
        print(f"Error: The file '{config_path}' was not found.")
    except Exception as e:
        print(f"An error occurred while parsing the config: {e}")