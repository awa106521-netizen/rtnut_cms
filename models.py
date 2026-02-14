import pymysql
import hashlib
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

def get_db_connection():
    """获取数据库连接（通用函数）"""
    conn = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        charset='utf8mb4'
    )
    return conn

def init_database():
    """初始化数据库：自动创建所有表+默认管理员（admin/admin123）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 1. 管理员表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                password VARCHAR(128) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 2. Banner表（升级：富文本+位置配置）
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS banners (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(100) NOT NULL,  # 兼容旧数据
                title_html TEXT,  # 富文本标题（字体/大小/样式）
                image_path VARCHAR(255) NOT NULL,
                link VARCHAR(255),
                button_text VARCHAR(50) DEFAULT 'View More',
                button_link VARCHAR(255),
                position_top VARCHAR(20) DEFAULT '50px',  # 文字顶部距离
                position_left VARCHAR(20) DEFAULT '50px', # 文字左侧距离
                button_position_top VARCHAR(20) DEFAULT '100px', # 按钮顶部距离
                button_position_left VARCHAR(20) DEFAULT '50px', # 按钮左侧距离
                sort INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 3. 产品表（含详情字段，移除TEXT字段默认值）
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(100) NOT NULL,
                description TEXT,
                detail TEXT,
                price DECIMAL(10,2) DEFAULT 0.00,
                image_path VARCHAR(255) NOT NULL,
                sort INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 4. 留言表
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(50) NOT NULL,
                email VARCHAR(100) NOT NULL,
                phone VARCHAR(20),
                content TEXT NOT NULL,
                is_read TINYINT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 5. 网站设置表（配色/页脚）
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS site_settings (
                id INT AUTO_INCREMENT PRIMARY KEY,
                key_name VARCHAR(50) NOT NULL UNIQUE,
                key_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 6. 厂容厂貌表（图片+视频）
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS factory_assets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(100) NOT NULL,
                type ENUM('image', 'video') DEFAULT 'image',
                file_path VARCHAR(255) NOT NULL,
                sort INT DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # 默认管理员：账号admin，密码admin123（已加密）
            cursor.execute("SELECT * FROM admins WHERE username = 'admin'")
            if cursor.rowcount == 0:
                password_hash = hashlib.sha256('admin123'.encode()).hexdigest()
                cursor.execute(
                    "INSERT INTO admins (username, password) VALUES (%s, %s)",
                    ('admin', password_hash)
                )
        
        conn.commit()
        print("✅ 数据库初始化成功！默认管理员：admin / admin123")
    except Exception as e:
        print(f"❌ 数据库初始化失败：{e}")
    finally:
        conn.close()

def verify_user(username, password):
    """验证管理员账号密码"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            cursor.execute(
                "SELECT * FROM admins WHERE username = %s AND password = %s",
                (username, password_hash)
            )
            return cursor.fetchone()
    finally:
        conn.close()
