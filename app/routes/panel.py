# app/routes/panel.py
import json
from flask import Blueprint, make_response, render_template, request
from app import utils
from app.config.pipeline_config_parser import PipelineInferenceDetail, load_pipeline_config

bp_panel = Blueprint('panel', __name__)



# @bp_panel.route('/panel/magistrate/<int:magistrate_id>')
# def magistrate_panel(magistrate_id: int):
#     """读取 pipeline_config 获取别名/IP，渲染面板抬头"""
#     cfg = load_pipeline_config(utils.get_config("pipeline_config"))
#     name = f"pipeline_inference_{magistrate_id}"
#     inf: PipelineInferenceDetail = cfg.client_pipeline.inferences.get(name)
#     if not inf:
#         return f"Error: '{name}' not found in pipeline_config.yaml", 404

#     alias = getattr(inf, 'alias', f"クライアント {magistrate_id}")
#     ip_address = (inf.camera_config.address if inf.camera_config else "N/A")
#     return render_template('panel.html', magistrate_id=magistrate_id,
#                            alias=alias, ip_address=ip_address)

@bp_panel.route('/panel/magistrate/<int:magistrate_id>')
def magistrate_panel(magistrate_id: int):
    """读取 pipeline_config 获取别名/IP，渲染面板抬头；支持直链 & HTMX 两种入口。"""
    cfg = load_pipeline_config(utils.get_config("pipeline_config"))
    name = f"pipeline_inference_{magistrate_id}"
    inf: PipelineInferenceDetail = cfg.client_pipeline.inferences.get(name)
    if not inf:
        return f"Error: '{name}' not found in pipeline_config.yaml", 404

    alias = getattr(inf, 'alias', f"クライアント {magistrate_id}")
    ip_address = (inf.camera_config.address if inf.camera_config else "N/A")

    # 1) HTMX 片段请求：只返回 panel.html（保持原行为）
    if request.headers.get('HX-Request') == 'true':
        return render_template('panel.html',
                               magistrate_id=magistrate_id,
                               alias=alias, ip_address=ip_address)

    # 2) 直链访问：返回完整 index.html + 一个一次性自动加载器，把面板装进 #main-content
    panel_loader = f'''
    <div
      hx-trigger="load"
      hx-get="/panel/magistrate/{magistrate_id}"
      hx-target="#main-content"
      hx-swap="innerHTML"
      hx-push-url="true">
    </div>
    '''
    # 先把 index.html 发给浏览器以加载全局 JS/CSS，再让 loader 拉取面板
    resp = make_response(render_template('index.html') + panel_loader)
    return resp


@bp_panel.route('/panel/magistrate/<int:magistrate_id>/toggle_button')
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


@bp_panel.route('/panel/magistrate/<int:magistrate_id>/start_source', methods=['POST'])
def start_source(magistrate_id: int):
    try:
        _save_pipeline_enable_sources(magistrate_id, True)
        return render_template('_magistrate_toggle_button.html',
                               magistrate_id=magistrate_id, is_enabled=True)
    except Exception as e:
        return f"<button disabled>Error: {e}</button>"


@bp_panel.route('/panel/magistrate/<int:magistrate_id>/stop_source', methods=['POST'])
def stop_source(magistrate_id: int):
    try:
        _save_pipeline_enable_sources(magistrate_id, False)
        return render_template('_magistrate_toggle_button.html',
                               magistrate_id=magistrate_id, is_enabled=False)
    except Exception as e:
        return f"<button disabled>Error: {e}</button>"
