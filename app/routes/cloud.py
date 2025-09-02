# app/routes/cloud.py
import json
from flask import Blueprint, make_response, render_template, request
from app.utils import file_utils
from pyengine.utils.logger import logger

from pyengine.config.magistrate_config_parser import (
    load_magistrate_config,
    save_magistrate_config,
    MagistrateConfig,
)

from pyengine.config.pipeline_config_parser import (
    load_pipeline_config,
    PipelineConfig,
)

bp_cloud = Blueprint('cloud', __name__)


@bp_cloud.route('/panel/cloud/<int:magistrate_id>', methods=['GET'])
def get_cloud_config_panel(magistrate_id: int):
    """
    显示云配置面板：用模型读取 magistrate_config{id}.yaml，并把 cloud.* 渲染到表单
    """
    cfg_name = f"magistrate_config{magistrate_id}"
    try:
        cfg_path = file_utils.get_config(cfg_name)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)

        cloud = cfg.client_magistrate.cloud
        data = {
            "sceptical_image": {
                "device_id":   file_utils.normalize(cloud.sceptical_image.device_id),
                "action_code": file_utils.normalize(cloud.sceptical_image.action_code),
            },
            "patrol_image": {
                "device_id":   file_utils.normalize(cloud.patrol_image.device_id),
                "action_code": file_utils.normalize(cloud.patrol_image.action_code),
            },
            # 其它字段若将来要加到表单，直接在此处补充
            "enable":            file_utils.normalize(cloud.enable),
            "blocking_duration": file_utils.normalize(cloud.blocking_duration),
            "upload_level":      file_utils.normalize(cloud.upload_level),
        }
        return render_template('cloud_config_panel.html', magistrate_id=magistrate_id, config=data)

    except Exception as e:
        logger.error_trace("get_cloud_config_panel", f"Error loading cloud config for magistrate {magistrate_id}")
        return f"Error loading cloud config for magistrate {magistrate_id}: {e}", 404


@bp_cloud.route('/panel/cloud/<int:magistrate_id>', methods=['POST'])
def update_cloud_config_panel(magistrate_id: int):
    """
    更新云配置：
      1) 用解析器读取 magistrate_config{id}.yaml 为模型
      2) 修改 cloud.sceptical_image / cloud.patrol_image
      3) save_magistrate_config() 写回 YAML，file_utils.sync_single_config() 同步
      4) 渲染回上一级面板（/panel/magistrate/{id} 的 HTML 片段），不再发送 HX-Trigger
    """
    cfg_name = f"magistrate_config{magistrate_id}"
    try:
        # 1) 读取为模型
        cfg_path = file_utils.get_config(cfg_name)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)

        f = request.form
        cloud = cfg.client_magistrate.cloud

        # 2) 修改模型（当前表单仅包含这四个字段）
        cloud.sceptical_image.device_id = f.get("sceptical_device_id") or cloud.sceptical_image.device_id
        cloud.sceptical_image.action_code = f.get("sceptical_action_code") or cloud.sceptical_image.action_code
        cloud.patrol_image.device_id = f.get("patrol_device_id") or cloud.patrol_image.device_id
        cloud.patrol_image.action_code = f.get("patrol_action_code") or cloud.patrol_image.action_code

        # blocking_duration: 尝试转 int；失败则保留原值
        bd_raw = f.get("blocking_duration", "").strip()
        if bd_raw.isdigit():
            cloud.blocking_duration = int(bd_raw)

        # upload_level: 同样转 int；失败则保留原值
        ul_raw = f.get("upload_level", "").strip()
        if ul_raw.isdigit():
            cloud.upload_level = int(ul_raw)

        # 3) 写回并同步
        save_magistrate_config(cfg_path, cfg)
        file_utils.copy_single_config(cfg_name)

        # 4) 渲染回上一级面板（alias/IP 从 pipeline_config 读取）
        p_path = file_utils.get_config("pipeline_config")
        pcfg: PipelineConfig = load_pipeline_config(p_path)
        inf_name = f"pipeline_inference_{magistrate_id}"
        inf = pcfg.client_pipeline.inferences.get(inf_name)
        alias = getattr(inf, "alias", f"クライアント {magistrate_id}") if inf else f"クライアント {magistrate_id}"
        ip = (inf.camera_config.address if (inf and inf.camera_config) else "N/A")

        panel_html = render_template('panel.html',
                                     magistrate_id=magistrate_id,
                                     alias=alias,
                                     ip_address=ip)

        # OOB 触发器：响应加载后等待 1 秒，再用 htmx 拉取面板并 push 到浏览器地址
        redirect_oob = f'''
        <div id="cloud-redirect-{magistrate_id}"
            hx-trigger="load delay:1s"
            hx-get="/panel/magistrate/{magistrate_id}"
            hx-target="#main-content"
            hx-swap="innerHTML"
            hx-push-url="true"
            hx-swap-oob="true"></div>
        '''

        resp = make_response(panel_html + redirect_oob)

        # 只弹窗提示，不带 redirect，避免默认跳首页
        resp.headers['HX-Trigger'] = json.dumps({
            "showsuccessmodal": {"message": "クラウド設定を保存しました", "delay": 1500}
        })
        return resp

    except Exception as e:
        logger.error_trace("update_cloud_config_panel", f"Error updating cloud config for magistrate {magistrate_id}")
        return f"Error updating cloud config for magistrate {magistrate_id}: {e}", 500
    

# 获取 toggle 按钮（根据当前 cloud.enable 渲染）
@bp_cloud.route('/panel/cloud/<int:magistrate_id>/toggle_button', methods=['GET'])
def get_cloud_toggle_button(magistrate_id: int):
    try:
        cfg_name = f"magistrate_config{magistrate_id}"
        cfg_path = file_utils.get_config(cfg_name)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)
        is_enabled = bool(cfg.client_magistrate.cloud.enable)
        return render_template('_cloud_toggle_button.html',
                               magistrate_id=magistrate_id,
                               is_enabled=is_enabled)
    except Exception as e:
        return f"<button disabled>Error: {e}</button>"


# 启用上载
@bp_cloud.route('/panel/cloud/<int:magistrate_id>/enable_upload', methods=['POST'])
def enable_cloud_upload(magistrate_id: int):
    try:
        cfg_name = f"magistrate_config{magistrate_id}"
        cfg_path = file_utils.get_config(cfg_name)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)
        cfg.client_magistrate.cloud.enable = True
        save_magistrate_config(cfg_path, cfg)
        file_utils.copy_single_config(cfg_name)

        # 重新渲染并返回整个云配置面板
        cloud = cfg.client_magistrate.cloud
        data = {
            "sceptical_image": {
                "device_id":   file_utils.normalize(cloud.sceptical_image.device_id),
                "action_code": file_utils.normalize(cloud.sceptical_image.action_code),
            },
            "patrol_image": {
                "device_id":   file_utils.normalize(cloud.patrol_image.device_id),
                "action_code": file_utils.normalize(cloud.patrol_image.action_code),
            },
            "enable":            file_utils.normalize(cloud.enable),
            "blocking_duration": file_utils.normalize(cloud.blocking_duration),
            "upload_level":      file_utils.normalize(cloud.upload_level),
        }
        return render_template('cloud_config_panel.html',
                               magistrate_id=magistrate_id,
                               config=data)
    except Exception as e:
        return f"Error: {e}", 500


# 关闭上载
@bp_cloud.route('/panel/cloud/<int:magistrate_id>/disable_upload', methods=['POST'])
def disable_cloud_upload(magistrate_id: int):
    try:
        cfg_name = f"magistrate_config{magistrate_id}"
        cfg_path = file_utils.get_config(cfg_name)
        cfg: MagistrateConfig = load_magistrate_config(cfg_path)
        cfg.client_magistrate.cloud.enable = False
        save_magistrate_config(cfg_path, cfg)
        file_utils.copy_single_config(cfg_name)

        # 重新渲染并返回整个云配置面板
        cloud = cfg.client_magistrate.cloud
        data = {
            "sceptical_image": {
                "device_id":   file_utils.normalize(cloud.sceptical_image.device_id),
                "action_code": file_utils.normalize(cloud.sceptical_image.action_code),
            },
            "patrol_image": {
                "device_id":   file_utils.normalize(cloud.patrol_image.device_id),
                "action_code": file_utils.normalize(cloud.patrol_image.action_code),
            },
            "enable":            file_utils.normalize(cloud.enable),
            "blocking_duration": file_utils.normalize(cloud.blocking_duration),
            "upload_level":      file_utils.normalize(cloud.upload_level),
        }
        return render_template('cloud_config_panel.html',
                               magistrate_id=magistrate_id,
                               config=data)
    except Exception as e:
        return f"Error: {e}", 500