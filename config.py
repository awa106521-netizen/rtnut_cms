# 数据库配置（修改为你的数据库信息）
DB_HOST = 'localhost'
DB_USER = 'root'
DB_PASSWORD = 'Yitong1210'  # 重点修改！
DB_NAME = 'rtnut_cms'

# Flask核心配置
SECRET_KEY = 'rtnut-2026-secret-key-123456'  # 可自定义
UPLOAD_FOLDER = 'uploads'  # 上传文件目录
MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 最大上传100MB（支持视频）

# 允许的上传文件类型
ALLOWED_EXTENSIONS = {
    'image': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
    'video': {'mp4', 'avi', 'mov', 'wmv', 'flv', 'webm'}
}

# 运行配置
HOST = '0.0.0.0'  # 允许外网访问
PORT = 8000       # 运行端口
DEBUG = True      # 开发模式（上线改False）

def allowed_file(filename, file_type=None):
    """检查文件是否允许上传"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if file_type == 'image':
        return ext in ALLOWED_EXTENSIONS['image']
    elif file_type == 'video':
        return ext in ALLOWED_EXTENSIONS['video']
    else:
        return ext in ALLOWED_EXTENSIONS['image'] or ext in ALLOWED_EXTENSIONS['video']
