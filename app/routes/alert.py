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


# --- Routes ---

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
        return render_template('alert_config_panel.html', magistrate_id=magistrate_id, config=data)

    except Exception as e:
        logger.error_trace("get_alert_config_panel", f"Error loading alert config for magistrate {magistrate_id}")
        return f"Error loading alert config for magistrate {magistrate_id}: {e}", 404


@bp_alert.route('/panel/alert/<int:magistrate_id>/<string:area>/<string:strategy>/toggle', methods=['GET', 'POST'])
def toggle_alert_strategy(magistrate_id: int, area: str, strategy: str):
    """
    通用路由：返回按钮 HTML，并使用 OOB 同步更新本行两个 input（阈值/罚点）的 disabled 状态。
    - GET：用于 alert_config_panel.html 初次渲染时的 hx-get（不切状态，只读取配置）
    - POST：用于点按钮切换（需要 hx-include="closest tr" 带回本行两个 input 的当前值）
    """
    try:
        cfg_name = f"magistrate_config{magistrate_id}"
        cfg_path = utils.get_config(cfg_name, return_path=True)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)

        # 映射 normal_area/key_area -> 对象属性
        area_attribute_name = f"{area}_strategy"
        target_area = getattr(cfg.client_magistrate, area_attribute_name)
        target_strategy = getattr(target_area, strategy)

        # 如果是点击按钮（POST），翻转 enable 并保存
        if request.method == 'POST':
            target_strategy.enable = not bool(target_strategy.enable)
            save_magistrate_config(cfg_path, cfg)
            utils.sync_single_config(cfg_name)

        # 读取“新的”启用状态
        is_enabled = bool(target_strategy.enable)

        # 这两个 key 必须与 panel 里 <input id=... name=...> 完全一致
        th_key = f"{area}_{strategy}_threshold"
        ps_key = f"{area}_{strategy}_penalty_score"

        # 从请求里拿“本行输入框当前值”（POST 来自 hx-include="closest tr"；GET 为空就回落到配置）
        current_threshold = request.form.get(th_key)
        if current_threshold is None or current_threshold == "":
            current_threshold = getattr(target_strategy, "threshold", "")

        current_penalty_score = request.form.get(ps_key)
        if current_penalty_score is None or current_penalty_score == "":
            current_penalty_score = getattr(target_strategy, "penalty_score", "")

        # 返回：按钮自身 + 两个 OOB 输入框（在 _alert_toggle_button.html 内输出）
        return render_template(
            '_alert_toggle_button.html',
            magistrate_id=magistrate_id,
            area=area,
            strategy=strategy,
            is_enabled=is_enabled,
            current_threshold=current_threshold,
            current_penalty_score=current_penalty_score,
        )

    except AttributeError:
        logger.error_trace("toggle_alert_strategy", f"Invalid area or strategy: {area}.{strategy} for magistrate {magistrate_id}")
        return f"<button disabled>Error: Invalid Area/Strategy</button>"
    except Exception as e:
        logger.error_trace("toggle_alert_strategy", f"Error toggling {area}.{strategy} for magistrate {magistrate_id}: {e}")
        return f"<button disabled>Error: {e}</button>"
    

@bp_alert.route('/panel/alert/<int:magistrate_id>', methods=['POST'])
def update_alert_config_panel(magistrate_id: int):
    """
    提交表单 -> 写回 magistrate_config{id}.yaml -> 同步 ->
    返回上一级面板 panel.html，并用 OOB 在 1 秒后 hx-get /panel/magistrate/{id} + push URL
    """
    cfg_name = f"magistrate_config{magistrate_id}"
    try:
        # 1) 读取 & 解析
        cfg_path = utils.get_config(cfg_name, return_path=True)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)
        f = request.form

        # 2) 更新 normal_area / key_area（阈值/罚点）
        def update_strategy_field(area_key: str):
            form_prefix = area_key + "_"
            area_attr   = f"{area_key}_strategy"
            target_area = getattr(cfg.client_magistrate, area_attr)
            for key, value in f.items():
                if not key.startswith(form_prefix):
                    continue
                rest = key[len(form_prefix):]          # e.g. "look_around_threshold"
                if "_" not in rest:
                    continue
                strategy_name, field_name = rest.rsplit("_", 1)
                if field_name not in ("threshold", "penalty_score"):
                    continue
                if not hasattr(target_area, strategy_name):
                    continue
                target_strategy = getattr(target_area, strategy_name)
                try:
                    setattr(target_strategy, field_name, int(value))
                except ValueError:
                    pass

        update_strategy_field("normal_area")
        update_strategy_field("key_area")

        # 3) 更新 alert_settings_levelX
        for key, value in f.items():
            if not key.startswith("alert_settings_"):
                continue
            suffix = key[len("alert_settings_"):]   # "level0".. "level5"
            if suffix.startswith("level") and hasattr(cfg.client_magistrate.alert_settings, suffix):
                try:
                    setattr(cfg.client_magistrate.alert_settings, suffix, int(value))
                except ValueError:
                    pass

        # 4) 更新 general_settings（含 checkbox）
        bool_fields = {"use_enhanced_tracking"}
        for bf in bool_fields:
            html_name = f"general_settings_{bf}"
            setattr(cfg.general_settings, bf, html_name in f)     # 勾上才会出现在 form

        for key, value in f.items():
            if not key.startswith("general_settings_"):
                continue
            field = key[len("general_settings_"):]
            if field in bool_fields:
                continue
            try:
                setattr(cfg.general_settings, field, int(value))
            except ValueError:
                try:
                    setattr(cfg.general_settings, field, float(value))
                except ValueError:
                    setattr(cfg.general_settings, field, value)

        # 5) 保存 & 同步
        save_magistrate_config(cfg_path, cfg)
        utils.sync_single_config(cfg_name)

        # 6) 渲染回上一级面板（需要 alias/IP，和 cloud/camera 一样从 pipeline_config 取）
        from app.config.pipeline_config_parser import load_pipeline_config, PipelineConfig
        p_path = utils.get_config("pipeline_config", return_path=True)
        pcfg: PipelineConfig = load_pipeline_config(p_path)
        inf_name = f"pipeline_inference_{magistrate_id}"
        inf = pcfg.client_pipeline.inferences.get(inf_name)
        alias = getattr(inf, "alias", f"クライアント {magistrate_id}") if inf else f"クライアント {magistrate_id}"
        ip    = (inf.camera_config.address if (inf and inf.camera_config) else "N/A")

        panel_html = render_template('panel.html',
                                     magistrate_id=magistrate_id,
                                     alias=alias,
                                     ip_address=ip)

        # 7) OOB：1 秒后用 htmx 拉取 /panel/magistrate/{id} 到 #main-content，并 push URL
        redirect_oob = f'''
        <div id="alert-redirect-{magistrate_id}"
            hx-trigger="load delay:1s"
            hx-get="/panel/magistrate/{magistrate_id}"
            hx-target="#main-content"
            hx-swap="innerHTML"
            hx-push-url="true"
            hx-swap-oob="true"></div>
        '''

        resp = make_response(panel_html + redirect_oob)
        resp.headers['HX-Trigger'] = json.dumps({
            "showsuccessmodal": {"message": "アラート設定を保存しました", "delay": 1500}
        })
        return resp

    except Exception as e:
        logger.error_trace("update_alert_config_panel",
                           f"Error updating alert config for magistrate {magistrate_id}")
        return f"Error updating alert config for magistrate {magistrate_id}: {e}", 500
