# app/routes/camera.py
import json
from flask import Blueprint, make_response, render_template, request
from app import utils
from app.config.pipeline_config_parser import (
    load_pipeline_config, save_pipeline_config, PipelineConfig, CameraConfig
)
from pyengine.utils.logger import logger


bp_camera = Blueprint('camera', __name__)

@bp_camera.route('/panel/camera/<int:camera_id>', methods=['GET'])
def get_camera_config_panel(camera_id: int):
    config_name = "pipeline_config"
    try:
        pipeline_config = utils.get_config(config_name)
        magistrate_config = load_pipeline_config(pipeline_config)
        inference_name = f"pipeline_inference_{camera_id}"
        cam_cfg = magistrate_config.client_pipeline.inferences[inference_name]

        data = {
            "alias":     utils.normalize(cam_cfg.alias),
            "camera_id": utils.normalize(cam_cfg.camera_config.camera_id),
            "address":   utils.normalize(cam_cfg.camera_config.address),
            "port":      utils.normalize(cam_cfg.camera_config.port),
            "path":      utils.normalize(cam_cfg.camera_config.path),
            "username":  utils.normalize(cam_cfg.camera_config.username),
            "password":  utils.normalize(cam_cfg.camera_config.password),
        }
        return render_template('camera_config_panel.html', magistrate_id=camera_id, config=data)
    except Exception as e:
        return f"Error loading camera config for magistrate {camera_id}: {e}", 404


@bp_camera.route('/panel/camera/<int:camera_id>', methods=['POST'])
def update_camera_config_panel(camera_id: int):
    try:
        cfg_path = utils.get_config("pipeline_config", return_path=True)
        cfg: PipelineConfig = load_pipeline_config(cfg_path)

        name = f"pipeline_inference_{camera_id}"
        if name not in cfg.client_pipeline.inferences:
            return f"Error: '{name}' not found in pipeline_config.yaml", 404

        inf = cfg.client_pipeline.inferences[name]
        f = request.form

        # —— 修改模型（略，保持你现在的实现）——
        inf.alias = f.get('alias') or inf.alias
        if inf.camera_config is None:
            inf.camera_config = CameraConfig(
                camera_id = f.get('camera_id') or None,
                address   = f.get('address') or "",
                port      = int(f['port']) if f.get('port','').isdigit() else None,
                path      = f.get('path') or None,
                username  = f.get('username') or None,
                password  = f.get('password') or None,
            )
        else:
            cam = inf.camera_config
            cam.camera_id = f.get('camera_id') or None
            cam.address   = f.get('address') or ""
            cam.port      = int(f['port']) if f.get('port','').isdigit() else None
            cam.path      = f.get('path') or None
            cam.username  = f.get('username') or None
            cam.password  = f.get('password') or None

        # —— 保存并同步（保持不变）——
        save_pipeline_config(cfg_path, cfg)
        utils.sync_single_config("pipeline_config")

        # —— 仅回上一级面板，不再发送 HX-Trigger —— ★关键修改
        alias = inf.alias
        ip    = inf.camera_config.address if inf.camera_config else "N/A"

        panel_html = render_template('panel.html',
                                    magistrate_id=camera_id,
                                    alias=alias,
                                    ip_address=ip)

        # 用 OOB 片段做 1 秒后跳回面板”的 htmx 自动请求（push url）
        redirect_oob = f'''
        <div id="camera-redirect-{camera_id}"
            hx-trigger="load delay:1s"
            hx-get="/panel/magistrate/{camera_id}"
            hx-target="#main-content"
            hx-swap="innerHTML"
            hx-push-url="true"
            hx-swap-oob="true"></div>
        '''

        resp = make_response(panel_html + redirect_oob)

        # 仅提示信息；不带 redirect，避免默认跳首页
        resp.headers['HX-Trigger'] = json.dumps({
            "showsuccessmodal": {"message": "カメラ設定を保存しました", "delay": 1500}
        })
        return resp

    except Exception as e:
        logger.error_trace("update_camera_config_panel", f"Error updating camera config for magistrate {camera_id}")
        return f"Error updating camera config for magistrate {camera_id}: {e}", 500