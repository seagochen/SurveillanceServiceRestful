# app/routes/alert.py
import json
from flask import Blueprint, render_template, request, make_response
from app import utils
from pyengine.utils.logger import logger

from app.config.magistrate_config_parser import (
    load_magistrate_config,
    save_magistrate_config,
    MagistrateConfig,
)

bp_alert = Blueprint('alert', __name__)

@bp_alert.route('/panel/alert/<int:magistrate_id>', methods=['GET'])
def get_alert_config_panel(magistrate_id: int):
    """
    加载并渲染警报配置面板。
    """
    cfg_name = f"magistrate_config{magistrate_id}"
    try:
        cfg_path = utils.get_config(cfg_name, return_path=True)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)

        low_area = cfg.client_magistrate.normal_area_strategy
        high_area = cfg.client_magistrate.key_area_strategy
        alert_settings = cfg.client_magistrate.alert_settings
        settings = cfg.general_settings

        data = {
            "normal_area": {
                "look_around":       { "enable": low_area.look_around.enable,       "threshold": low_area.look_around.threshold,       "penalty_score": low_area.look_around.penalty_score }, 
                "theft_detection":   { "enable": low_area.theft_detection.enable,   "threshold": low_area.theft_detection.threshold,   "penalty_score": low_area.theft_detection.penalty_score },
                "long_time_squat":   { "enable": low_area.long_time_squat.enable,   "threshold": low_area.long_time_squat.threshold,   "penalty_score": low_area.long_time_squat.penalty_score },
                "loitering_distance":{ "enable": low_area.loitering_distance.enable,"threshold": low_area.loitering_distance.threshold,"penalty_score": low_area.loitering_distance.penalty_score },
                "loitering_reentry": { "enable": low_area.loitering_reentry.enable, "threshold": low_area.loitering_reentry.threshold, "penalty_score": low_area.loitering_reentry.penalty_score },
                "loitering_enter_area":{ "enable": low_area.loitering_enter_area.enable, "threshold": low_area.loitering_enter_area.threshold, "penalty_score": low_area.loitering_enter_area.penalty_score }
            },
            "key_area": {
                "look_around":       { "enable": high_area.look_around.enable,       "threshold": high_area.look_around.threshold,       "penalty_score": high_area.look_around.penalty_score }, 
                "theft_detection":   { "enable": high_area.theft_detection.enable,   "threshold": high_area.theft_detection.threshold,   "penalty_score": high_area.theft_detection.penalty_score },
                "long_time_squat":   { "enable": high_area.long_time_squat.enable,   "threshold": high_area.long_time_squat.threshold,   "penalty_score": high_area.long_time_squat.penalty_score },
                "loitering_distance":{ "enable": high_area.loitering_distance.enable,"threshold": high_area.loitering_distance.threshold,"penalty_score": high_area.loitering_distance.penalty_score },
                "loitering_reentry": { "enable": high_area.loitering_reentry.enable, "threshold": high_area.loitering_reentry.threshold, "penalty_score": high_area.loitering_reentry.penalty_score },
                "loitering_enter_area":{ "enable": high_area.loitering_enter_area.enable, "threshold": high_area.loitering_enter_area.threshold, "penalty_score": high_area.loitering_enter_area.penalty_score }
            },
            "alert_settings": {
                "level0": utils.normalize(alert_settings.level0),
                "level1": utils.normalize(alert_settings.level1),
                "level2": utils.normalize(alert_settings.level2),
                "level3": utils.normalize(alert_settings.level3),
                "level4": utils.normalize(alert_settings.level4),
                "level5": utils.normalize(alert_settings.level5),
            },
            "general_settings": {
                "cache_retention_duration": utils.normalize(settings.cache_retention_duration),
                "use_enhanced_tracking": utils.normalize(settings.use_enhanced_tracking),
                "sma_window_size": utils.normalize(settings.sma_window_size),
                "delta_duration_threshold": utils.normalize(settings.delta_duration_threshold),
                "delta_distance_threshold": utils.normalize(settings.delta_distance_threshold),
                "reentry_angle_threshold": utils.normalize(settings.reentry_angle_threshold),
                "min_consecutive_count": utils.normalize(settings.min_consecutive_count),
                "min_keypoint_distance": utils.normalize(settings.min_keypoint_distance)
            }
        }
        return render_template('magistrate_alert_panel.html', magistrate_id=magistrate_id, config=data)

    except Exception as e:
        logger.error_trace("get_alert_config_panel", f"Error loading alert config for magistrate {magistrate_id}")
        return f"Error loading alert config for magistrate {magistrate_id}: {e}", 404


@bp_alert.route('/panel/alert/<int:magistrate_id>/<string:area>/<string:strategy>/toggle', methods=['GET', 'POST'])
def toggle_alert_strategy(magistrate_id: int, area: str, strategy: str):
    """
    通用路由，用于切换任何警报策略的启用/禁用状态。
    """
    try:
        cfg_name = f"magistrate_config{magistrate_id}"
        cfg_path = utils.get_config(cfg_name, return_path=True)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)
        
        # ✨ 新增：将URL中的 area 映射到正确的属性名
        area_attribute_name = f"{area}_strategy"

        # 使用映射后的属性名动态访问配置对象
        target_area = getattr(cfg.client_magistrate, area_attribute_name)
        target_strategy = getattr(target_area, strategy)

        # 切换 enable 状态
        if request.method == 'POST':
            target_strategy.enable = not target_strategy.enable
            save_magistrate_config(cfg_path, cfg)
            utils.sync_single_config(cfg_name)

        is_enabled = bool(target_strategy.enable)
        return render_template('_alert_toggle_button.html',
                               magistrate_id=magistrate_id,
                               area=area,
                               strategy=strategy,
                               is_enabled=is_enabled)
    except AttributeError:
        # 增加一个更明确的错误处理，以防未来出现类似问题
        logger.error_trace("toggle_alert_strategy", f"Invalid area or strategy: {area}.{strategy} for magistrate {magistrate_id}")
        return f"<button disabled>Error: Invalid Area/Strategy</button>"
    except Exception as e:
        logger.error_trace("toggle_alert_strategy", f"Error toggling {area}.{strategy} for magistrate {magistrate_id}")
        return f"<button disabled>Error: {e}</button>"
    

@bp_alert.route('/panel/alert/<int:magistrate_id>', methods=['POST'])
def update_alert_config_panel(magistrate_id: int):
    """
    处理整个表单的提交，更新所有配置字段。
    """
    cfg_name = f"magistrate_config{magistrate_id}"
    try:
        cfg_path = utils.get_config(cfg_name, return_path=True)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)
        
        # 遍历表单数据并更新配置
        form_data = request.form
        for key, value in form_data.items():
            parts = key.split('_')
            
            # 处理 nested keys like 'normal_area_look_around_threshold'
            if len(parts) >= 3:
                area_name = parts[0] + '_' + parts[1] # e.g., 'normal_area'
                strategy_name = parts[2] # e.g., 'look_around'
                field_name = parts[3] # e.g., 'threshold'

                if hasattr(cfg.client_magistrate, area_name):
                    target_area = getattr(cfg.client_magistrate, area_name)
                    if hasattr(target_area, strategy_name):
                        target_strategy = getattr(target_area, strategy_name)
                        
                        # 特殊处理 enable, 其它为 threshold/penalty_score
                        if field_name == 'enable':
                            setattr(target_strategy, field_name, value == 'true')
                        elif field_name in ['threshold', 'penalty_score', 'loitering_distance']:
                            try:
                                setattr(target_strategy, field_name, int(value))
                            except ValueError:
                                pass # ignore invalid numbers
                        elif field_name == 'cache_retention_duration':
                            try:
                                setattr(cfg.client_magistrate, field_name, int(value))
                            except ValueError:
                                pass
                        elif field_name in ['use_enhanced_tracking', 'enable_debug_mode']:
                            setattr(cfg.general_settings, field_name, value == 'on')
                        else: # for other general settings
                            try:
                                setattr(cfg.general_settings, field_name, int(value))
                            except ValueError:
                                try:
                                    setattr(cfg.general_settings, field_name, float(value))
                                except ValueError:
                                    setattr(cfg.general_settings, field_name, value)
        
        save_magistrate_config(cfg_path, cfg)
        utils.sync_single_config(cfg_name)

        resp = make_response(render_template('panel.html', magistrate_id=magistrate_id))
        resp.headers['HX-Trigger'] = json.dumps({
            "showsuccessmodal": {"message": "設定を保存しました", "delay": 1500}
        })
        return resp
    
    except Exception as e:
        logger.error_trace("update_alert_config_panel", f"Error updating alert config for magistrate {magistrate_id}")
        return f"Error updating alert config for magistrate {magistrate_id}: {e}", 500
