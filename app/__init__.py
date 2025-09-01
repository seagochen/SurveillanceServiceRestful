from flask import Flask
from flask_cors import CORS # 1. 从 flask_cors 导入 CORS


def create_app():
    """创建并配置 Flask 应用程序实例。"""
    app = Flask(__name__)

    # 精细化配置CORS
    # 为 /config/  /monitor/ 下的所有路由开启CORS
    # resources 参数接受一个字典，key 是正则表达式，匹配路由
    # CORS(app, resources={r"/config/*": {"origins": "*"}, r"/monitor/*": {"origins": "*"}})
    # "origins" 也可以指定具体的来源，例如:
    # {"origins": ["http://localhost:3000", "http://your-frontend-domain.com"]}

    # 启用 CORS，为所有路由开启 CORS
    CORS(app)

    # 可以从这里加载配置，例如从 config.py 文件或环境变量
    # app.config.from_object('app.config.Config') # 如果有 config.py
    # 或者直接在这里设置一些基本配置
    app.config['DEBUG'] = True
    app.config['SECRET_KEY'] = 'your_super_secret_key' # 生产环境请使用更复杂的密钥

    # 导入并注册蓝图
    # 显式注册每个蓝图（URL 保持不变，无需调整前端）
    from .routes.index import bp_index
    from .routes.panel import bp_panel
    from .routes.camera import bp_camera
    from .routes.cloud import bp_cloud
    from .routes.monitor import bp_monitor
    from .routes.ops import bp_ops
    from .routes.alert import bp_alert
    from .routes.keyarea import bp_keyarea

    app.register_blueprint(bp_index)    # '/'
    app.register_blueprint(bp_panel)    # '/panel/magistrate/*'
    app.register_blueprint(bp_camera)   # '/panel/camera/*'
    app.register_blueprint(bp_cloud)    # '/panel/cloud/*'
    app.register_blueprint(bp_monitor)  # '/get-*'
    app.register_blueprint(bp_ops)      # '/panel/sync/*', '/config/*', '/system/*'
    app.register_blueprint(bp_alert)    # '/panel/alert/*'
    app.register_blueprint(bp_keyarea)  # '/panel/keyarea/*'

    return app
