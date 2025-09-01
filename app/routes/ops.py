# app/routes/ops.py
import json, os
from flask import Blueprint, make_response, render_template
from app import utils

bp_ops = Blueprint('ops', __name__)


@bp_ops.route('/panel/sync/<int:magistrate_id>', methods=['POST'])
def sync_config(magistrate_id: int):
    cfg = f"magistrate_config{magistrate_id}"
    utils.copy_single_config(cfg)

    # 【关键修改】使用 HX-Redirect 头部，让 HTMX 自己处理跳转
    resp = make_response("") # 可以发送空响应，因为 hx-swap="none"
    
    # 将成功的消息放在 HX-Trigger 中，供 JS 弹窗使用
    success_message = f"設定が同期されました ({cfg}.yaml)"
    resp.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": success_message})
    
    # 告诉 HTMX 在收到响应后重定向到根路径
    resp.headers['HX-Redirect'] = "/"
    
    return resp


@bp_ops.route('/config/sync_all', methods=['POST'])
def sync_all_configs():
    # 分别同步各文件
    for i in range(1, 9):
        utils.copy_single_config(f"magistrate_config{i}")
    utils.copy_single_config("pipeline_config")

    # 生成回复信息
    resp = make_response("")
    resp.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": "すべての設定ファイルが同期されました！"})
    
    # 增加 HX-Redirect 头部，指示 HTMX 重定向到主页
    resp.headers['HX-Redirect'] = "/"
    return resp


@bp_ops.route('/config/reset', methods=['POST'])
def reset_configs():
    utils.copy_configs(os.path.join("configs", "defaults"), "configs")
    resp = make_response("")
    resp.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": "初期設定が読み込まれました"})

    # 增加 HX-Redirect 头部，指示 HTMX 重定向到主页
    resp.headers['HX-Redirect'] = "/"
    return resp


@bp_ops.route('/config/load_all', methods=['POST'])
def load_all_configs():
    # utils.load_configs_from_device()
    utils.copy_configs(src_folder="/opt/SurveillanceService/configs",
                       dest_folder="configs")
    resp = make_response("")
    resp.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": "デバイスから設定が読み込まれました"})

    # 增加 HX-Redirect 头部，指示 HTMX 重定向到主页
    resp.headers['HX-Redirect'] = "/"
    return resp


@bp_ops.route('/system/restart', methods=['POST'])
def restart_system():
    # TODO: 真正的重启逻辑
    resp = make_response("")
    resp.headers['HX-Trigger'] = json.dumps({"showsuccessmodal": "システムは正常に再起動されました！"})
    return resp
