# app/routes/magistrate.py
import json
from flask import Blueprint, render_template
from app import utils
from app.config.pipeline_config_parser import PipelineInferenceDetail, load_pipeline_config

bp_mag = Blueprint('magistrate', __name__)



@bp_mag.route('/panel/magistrate/<int:magistrate_id>')
def magistrate_panel(magistrate_id: int):
    """读取 pipeline_config 获取别名/IP，渲染面板抬头"""
    cfg = load_pipeline_config(utils.get_config("pipeline_config"))
    name = f"pipeline_inference_{magistrate_id}"
    inf: PipelineInferenceDetail = cfg.client_pipeline.inferences.get(name)
    if not inf:
        return f"Error: '{name}' not found in pipeline_config.yaml", 404

    alias = getattr(inf, 'alias', f"クライアント {magistrate_id}")
    ip_address = (inf.camera_config.address if inf.camera_config else "N/A")
    return render_template('panel.html', magistrate_id=magistrate_id,
                           alias=alias, ip_address=ip_address)


@bp_mag.route('/panel/magistrate/<int:magistrate_id>/toggle_button')
def get_toggle_button(magistrate_id: int):
    cfg = load_pipeline_config(utils.get_config("pipeline_config"))
    name = f"pipeline_inference_{magistrate_id}"
    is_enabled = name in cfg.client_pipeline.enable_sources
    return render_template('_magistrate_toggle_button.html',
                           magistrate_id=magistrate_id, is_enabled=is_enabled)


def _save_pipeline_enable_sources(magistrate_id: int, enable: bool):
    cfg_name = "pipeline_config"
    raw = utils.get_config(cfg_name, return_path=False)
    name = f"pipeline_inference_{magistrate_id}"
    # 简单就地改 list（可结合模型更严格校验）
    raw.setdefault('client_pipeline', {})
    raw['client_pipeline'].setdefault('enable_sources', [])
    raw['client_pipeline'].setdefault('disable_sources', [])
    if enable:
        if name in raw['client_pipeline']['disable_sources']:
            raw['client_pipeline']['disable_sources'].remove(name)
        if name not in raw['client_pipeline']['enable_sources']:
            raw['client_pipeline']['enable_sources'].append(name)
    else:
        if name in raw['client_pipeline']['enable_sources']:
            raw['client_pipeline']['enable_sources'].remove(name)
        if name not in raw['client_pipeline']['disable_sources']:
            raw['client_pipeline']['disable_sources'].append(name)
    utils.save_config(cfg_name, raw)


@bp_mag.route('/panel/magistrate/<int:magistrate_id>/start_source', methods=['POST'])
def start_source(magistrate_id: int):
    try:
        _save_pipeline_enable_sources(magistrate_id, True)
        return render_template('_magistrate_toggle_button.html',
                               magistrate_id=magistrate_id, is_enabled=True)
    except Exception as e:
        return f"<button disabled>Error: {e}</button>"


@bp_mag.route('/panel/magistrate/<int:magistrate_id>/stop_source', methods=['POST'])
def stop_source(magistrate_id: int):
    try:
        _save_pipeline_enable_sources(magistrate_id, False)
        return render_template('_magistrate_toggle_button.html',
                               magistrate_id=magistrate_id, is_enabled=False)
    except Exception as e:
        return f"<button disabled>Error: {e}</button>"
