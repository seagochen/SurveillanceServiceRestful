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
    from .routes import main_bp

    # 2. 导入 mqtt_status 模块，这会执行其中的代码，
    #    从而将其中的路由注册到上面导入的 main_bp 上
    from . import mqtt_status

    app.register_blueprint(main_bp)

    return app
