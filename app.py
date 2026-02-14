import os
import json
import time
from flask import Flask, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.utils import secure_filename
from models import get_db_connection, init_database, verify_user
from config import *
from PIL import Image  # 导入图片处理库

# 初始化Flask应用
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# 确保上传目录存在
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ====================== 工具函数 ======================
def compress_image(file_path, max_width=800, max_height=800):
    """压缩图片到指定尺寸（保持比例）"""
    try:
        with Image.open(file_path) as img:
            # 获取原图尺寸
            width, height = img.size
            # 计算缩放比例
            scale = min(max_width/width, max_height/height, 1)
            if scale < 1:
                new_width = int(width * scale)
                new_height = int(height * scale)
                # 缩放图片
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                # 保存压缩后的图片（覆盖原文件）
                img.save(file_path, quality=85)  # 质量85%
        return True
    except Exception as e:
        print(f"图片压缩失败：{e}")
        return False

def generate_unique_filename(filename):
    """生成唯一文件名（避免覆盖）"""
    ext = filename.rsplit('.', 1)[1].lower()
    unique_name = f"{int(time.time())}_{secure_filename(filename.rsplit('.', 1)[0])}.{ext}"
    return unique_name

# ====================== 全局函数（模板共用） ======================
@app.context_processor
def inject_site_settings():
    """向所有模板注入主题色、页脚信息"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取主题色（默认黑色，贴合rtnut.com）
            cursor.execute("SELECT key_value FROM site_settings WHERE key_name = 'theme_color'")
            theme_color = cursor.fetchone()['key_value'] if cursor.rowcount > 0 else '#000000'
            
            # 获取页脚信息
            cursor.execute("SELECT key_value FROM site_settings WHERE key_name = 'footer_info'")
            footer_info = cursor.fetchone()['key_value'] if cursor.rowcount > 0 else '{}'
            footer_info = json.loads(footer_info)
        
        return dict(theme_color=theme_color, footer_info=footer_info)
    finally:
        conn.close()

# ====================== 前台路由（完全复刻rtnut.com） ======================
@app.route('/')
def index():
    """首页：Banner+产品+厂容厂貌"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        # 获取Banner（带富文本+位置配置）
        cursor.execute("SELECT * FROM banners ORDER BY sort ASC")
        banners = cursor.fetchall()
        
        # 获取产品
        cursor.execute("SELECT * FROM products ORDER BY sort ASC")
        products = cursor.fetchall()
        
        # 获取厂容厂貌（首页展示前4张）
        cursor.execute("SELECT * FROM factory_assets WHERE type='image' ORDER BY sort ASC LIMIT 4")
        factory_assets = cursor.fetchall()
        
        return render_template('front/index.html', 
                               banners=banners, 
                               products=products,
                               factory_assets=factory_assets)
    finally:
        conn.close()

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    """产品详情页"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 获取当前产品
            cursor.execute("SELECT * FROM products WHERE id = %s", (product_id,))
            product = cursor.fetchone()
            
            if not product:
                flash('产品不存在！', 'danger')
                return redirect(url_for('index'))
            
            # 相关产品（排除当前产品）
            cursor.execute("SELECT * FROM products WHERE id != %s ORDER BY sort ASC LIMIT 3", (product_id,))
            related_products = cursor.fetchall()
        
        return render_template('front/product_detail.html', 
                               product=product,
                               related_products=related_products)
    finally:
        conn.close()

@app.route('/factory')
def factory_page():
    """厂容厂貌详情页（图片+视频）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 图片资源
            cursor.execute("SELECT * FROM factory_assets WHERE type='image' ORDER BY sort ASC")
            factory_images = cursor.fetchall()
            
            # 视频资源
            cursor.execute("SELECT * FROM factory_assets WHERE type='video' ORDER BY sort ASC")
            factory_videos = cursor.fetchall()
        
        return render_template('front/factory.html', 
                               factory_images=factory_images,
                               factory_videos=factory_videos)
    finally:
        conn.close()

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    """联系我们（留言功能）"""
    if request.method == 'POST':
        try:
            name = request.form['name'].strip()
            email = request.form['email'].strip()
            phone = request.form.get('phone', '').strip()
            content = request.form['content'].strip()
            
            # 基础校验
            if not name or not email or not content:
                flash('姓名、邮箱、留言内容不能为空！', 'danger')
                return redirect(url_for('contact'))
            
            conn = get_db_connection()
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO messages (name, email, phone, content) VALUES (%s, %s, %s, %s)",
                    (name, email, phone, content)
                )
            conn.commit()
            flash('留言提交成功！我们会尽快回复你', 'success')
        except Exception as e:
            flash(f'提交失败：{str(e)}', 'danger')
        finally:
            if 'conn' in locals():
                conn.close()
        return redirect(url_for('contact'))
    
    return render_template('front/contact.html')

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    """提供上传文件访问"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ====================== 后台路由 ======================
# 登录验证装饰器
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'admin' not in session:
            flash('请先登录！', 'danger')
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    """后台登录"""
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        user = verify_user(username, password)
        if user:
            session['admin'] = user['username']
            flash('登录成功！', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('用户名或密码错误！', 'danger')
    return render_template('admin/login.html')

@app.route('/admin/logout')
@login_required
def admin_logout():
    """后台登出"""
    session.pop('admin', None)
    flash('已成功登出！', 'success')
    return redirect(url_for('admin_login'))

@app.route('/admin/')
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    """后台仪表盘（数据统计）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 统计数据
            cursor.execute("SELECT COUNT(*) as msg_count FROM messages")
            msg_count = cursor.fetchone()['msg_count']
            
            cursor.execute("SELECT COUNT(*) as unread_msg FROM messages WHERE is_read = 0")
            unread_msg = cursor.fetchone()['unread_msg']
            
            cursor.execute("SELECT COUNT(*) as product_count FROM products")
            product_count = cursor.fetchone()['product_count']
            
            cursor.execute("SELECT COUNT(*) as banner_count FROM banners")
            banner_count = cursor.fetchone()['banner_count']
            
            cursor.execute("SELECT COUNT(*) as factory_count FROM factory_assets")
            factory_count = cursor.fetchone()['factory_count']
            
            # 最近5条留言
            cursor.execute("SELECT * FROM messages ORDER BY created_at DESC LIMIT 5")
            messages = cursor.fetchall()
        
        return render_template('admin/dashboard.html', 
                               msg_count=msg_count, unread_msg=unread_msg,
                               product_count=product_count, banner_count=banner_count,
                               factory_count=factory_count, messages=messages)
    finally:
        conn.close()

@app.route('/admin/messages')
@login_required
def admin_messages():
    """留言管理（标记已读）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 标记已读
            mark_read_id = request.args.get('mark_read')
            if mark_read_id and mark_read_id.isdigit():
                cursor.execute("UPDATE messages SET is_read = 1 WHERE id = %s", (mark_read_id,))
                conn.commit()
                flash('留言已标记为已读！', 'success')
                return redirect(url_for('admin_messages'))
            
            # 获取所有留言
            cursor.execute("SELECT * FROM messages ORDER BY created_at DESC")
            messages = cursor.fetchall()
        
        return render_template('admin/messages.html', messages=messages)
    finally:
        conn.close()

@app.route('/admin/banners', methods=['GET', 'POST'])
@login_required
def admin_banners():
    """Banner管理：新增/编辑/删除（富文本+位置配置）"""
    edit_banner = None
    conn = get_db_connection()
    
    try:
        # 1. 判断操作类型：编辑（edit参数）/新增（add参数）
        edit_id = request.args.get('edit')
        add_flag = request.args.get('add')
        
        # 编辑Banner：获取要编辑的记录
        if edit_id and edit_id.isdigit():
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM banners WHERE id = %s", (edit_id,))
                edit_banner = cursor.fetchone()
        # 新增Banner：初始化空对象（用于表单渲染）
        elif add_flag:
            edit_banner = {}
        
        # 2. 保存Banner（新增/编辑）
        if request.method == 'POST':
            title = request.form['title'].strip()
            title_html = request.form.get('title_html', '').strip()
            link = request.form.get('link', '').strip()
            button_text = request.form.get('button_text', 'View More').strip()
            button_link = request.form.get('button_link', '').strip()
            position_top = request.form.get('position_top', '50px').strip()
            position_left = request.form.get('position_left', '50px').strip()
            button_position_top = request.form.get('button_position_top', '100px').strip()
            button_position_left = request.form.get('button_position_left', '50px').strip()
            sort = request.form.get('sort', 0)
            banner_id = request.form.get('banner_id', '')
            image_path = ''
            
            # 图片上传+压缩
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename, 'image'):
                    filename = generate_unique_filename(file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    compress_image(file_path)
                    image_path = f"uploads/{filename}"
            
            with conn.cursor() as cursor:
                # 编辑逻辑
                if banner_id and banner_id.isdigit():
                    # 有图片则更新图片，无则不更
                    if image_path:
                        cursor.execute("""
                            UPDATE banners SET 
                                title=%s, title_html=%s, link=%s, button_text=%s, button_link=%s,
                                position_top=%s, position_left=%s, button_position_top=%s, button_position_left=%s,
                                sort=%s, image_path=%s 
                            WHERE id=%s
                        """, (
                            title, title_html, link, button_text, button_link,
                            position_top, position_left, button_position_top, button_position_left,
                            sort, image_path, banner_id
                        ))
                        flash('Banner更新成功（含图片）！', 'success')
                    else:
                        cursor.execute("""
                            UPDATE banners SET 
                                title=%s, title_html=%s, link=%s, button_text=%s, button_link=%s,
                                position_top=%s, position_left=%s, button_position_top=%s, button_position_left=%s,
                                sort=%s 
                            WHERE id=%s
                        """, (
                            title, title_html, link, button_text, button_link,
                            position_top, position_left, button_position_top, button_position_left,
                            sort, banner_id
                        ))
                        flash('Banner更新成功！', 'success')
                # 新增逻辑（必须有图片）
                elif image_path:
                    cursor.execute("""
                        INSERT INTO banners (
                            title, title_html, link, button_text, button_link,
                            position_top, position_left, button_position_top, button_position_left,
                            sort, image_path
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        title, title_html, link, button_text, button_link,
                        position_top, position_left, button_position_top, button_position_left,
                        sort, image_path
                    ))
                    flash('Banner添加成功！', 'success')
                else:
                    flash('请上传Banner图片！', 'danger')
                    return redirect(url_for('admin_banners', add=1))
            
            conn.commit()
            return redirect(url_for('admin_banners'))
        
        # 3. 获取所有Banner（列表展示）
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM banners ORDER BY sort ASC")
            banners = cursor.fetchall()
        
        return render_template('admin/banners.html', banners=banners, edit_banner=edit_banner)
    finally:
        conn.close()

@app.route('/admin/banners/delete/<int:banner_id>')
@login_required
def delete_banner(banner_id):
    """删除Banner（含文件）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 删除图片文件
            cursor.execute("SELECT image_path FROM banners WHERE id = %s", (banner_id,))
            banner = cursor.fetchone()
            if banner and banner['image_path']:
                file_path = os.path.join(os.path.dirname(__file__), banner['image_path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                # 删除数据库记录
                cursor.execute("DELETE FROM banners WHERE id = %s", (banner_id,))
                conn.commit()
                flash('Banner删除成功！', 'success')
    finally:
        conn.close()
    return redirect(url_for('admin_banners'))

# ========== 产品管理（升级：图片压缩+尺寸管控） ==========
@app.route('/admin/products', methods=['GET', 'POST'])
@login_required
def admin_products():
    """产品管理：新增/编辑/删除（含详情字段+图片压缩）"""
    edit_product = None
    conn = get_db_connection()
    
    try:
        # 编辑产品
        edit_id = request.args.get('edit')
        if edit_id and edit_id.isdigit():
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM products WHERE id = %s", (edit_id,))
                edit_product = cursor.fetchone()
        
        # 保存产品
        if request.method == 'POST':
            title = request.form['title'].strip()
            description = request.form.get('description', '').strip()
            detail = request.form.get('detail', '').strip()
            price = request.form.get('price', 0)
            sort = request.form.get('sort', 0)
            product_id = request.form.get('product_id', '')
            image_path = ''
            
            # 图片上传+压缩
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename, 'image'):
                    # 生成唯一文件名
                    filename = generate_unique_filename(file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    # 压缩图片到800x800（前台卡片最佳尺寸）
                    compress_image(file_path, max_width=800, max_height=800)
                    image_path = f"uploads/{filename}"
            
            with conn.cursor() as cursor:
                if product_id and product_id.isdigit():
                    # 编辑逻辑
                    if image_path:
                        # 更新图片
                        cursor.execute(
                            "UPDATE products SET title=%s, description=%s, detail=%s, price=%s, sort=%s, image_path=%s WHERE id=%s",
                            (title, description, detail, price, sort, image_path, product_id)
                        )
                        flash('产品更新成功（含图片）！', 'success')
                    else:
                        # 不更新图片
                        cursor.execute(
                            "UPDATE products SET title=%s, description=%s, detail=%s, price=%s, sort=%s WHERE id=%s",
                            (title, description, detail, price, sort, product_id)
                        )
                        flash('产品更新成功！', 'success')
                elif image_path:
                    # 新增逻辑
                    cursor.execute(
                        "INSERT INTO products (title, description, detail, price, sort, image_path) VALUES (%s, %s, %s, %s, %s, %s)",
                        (title, description, detail, price, sort, image_path)
                    )
                    flash('产品添加成功！', 'success')
                else:
                    flash('请上传产品图片！', 'danger')
                    return redirect(url_for('admin_products'))
            
            conn.commit()
            return redirect(url_for('admin_products'))
        
        # 获取所有产品
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM products ORDER BY sort ASC")
            products = cursor.fetchall()
        
        return render_template('admin/products.html', products=products, edit_product=edit_product)
    finally:
        conn.close()

@app.route('/admin/products/delete/<int:product_id>')
@login_required
def delete_product(product_id):
    """删除产品（含文件）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 删除图片文件
            cursor.execute("SELECT image_path FROM products WHERE id = %s", (product_id,))
            product = cursor.fetchone()
            if product and product['image_path']:
                file_path = os.path.join(os.path.dirname(__file__), product['image_path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                # 删除数据库记录
                cursor.execute("DELETE FROM products WHERE id = %s", (product_id,))
                conn.commit()
                flash('产品删除成功！', 'success')
    finally:
        conn.close()
    return redirect(url_for('admin_products'))

# ========== 厂容厂貌管理 ==========
@app.route('/admin/factory', methods=['GET', 'POST'])
@login_required
def admin_factory():
    """厂容厂貌管理：图片/视频上传+编辑+删除"""
    edit_asset = None
    conn = get_db_connection()
    
    try:
        # 编辑资源
        edit_id = request.args.get('edit')
        if edit_id and edit_id.isdigit():
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM factory_assets WHERE id = %s", (edit_id,))
                edit_asset = cursor.fetchone()
        
        # 保存资源
        if request.method == 'POST':
            title = request.form['title'].strip()
            asset_type = request.form.get('type', 'image')
            sort = request.form.get('sort', 0)
            asset_id = request.form.get('asset_id', '')
            file_path = ''
            
            # 文件上传（图片/视频）
            if 'file' in request.files:
                file = request.files['file']
                if file and allowed_file(file.filename, asset_type):
                    # 生成唯一文件名
                    filename = generate_unique_filename(file.filename)
                    file_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(file_path)
                    # 图片压缩（视频不处理）
                    if asset_type == 'image':
                        compress_image(file_path)
                    file_path = f"uploads/{filename}"
            
            with conn.cursor() as cursor:
                if asset_id and asset_id.isdigit():
                    # 编辑逻辑
                    if file_path:
                        # 更新文件
                        cursor.execute(
                            "UPDATE factory_assets SET title=%s, type=%s, sort=%s, file_path=%s WHERE id=%s",
                            (title, asset_type, sort, file_path, asset_id)
                        )
                        flash('资源更新成功（含文件）！', 'success')
                    else:
                        # 不更新文件
                        cursor.execute(
                            "UPDATE factory_assets SET title=%s, type=%s, sort=%s WHERE id=%s",
                            (title, asset_type, sort, asset_id)
                        )
                        flash('资源更新成功！', 'success')
                elif file_path:
                    # 新增逻辑
                    cursor.execute(
                        "INSERT INTO factory_assets (title, type, sort, file_path) VALUES (%s, %s, %s, %s)",
                        (title, asset_type, sort, file_path)
                    )
                    flash('资源添加成功！', 'success')
                else:
                    flash('请上传图片/视频文件！', 'danger')
                    return redirect(url_for('admin_factory'))
            
            conn.commit()
            return redirect(url_for('admin_factory'))
        
        # 获取所有资源
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM factory_assets ORDER BY sort ASC")
            factory_assets = cursor.fetchall()
        
        return render_template('admin/factory.html', factory_assets=factory_assets, edit_asset=edit_asset)
    finally:
        conn.close()

@app.route('/admin/factory/delete/<int:asset_id>')
@login_required
def delete_factory_asset(asset_id):
    """删除厂容厂貌资源（含文件）"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 删除文件
            cursor.execute("SELECT file_path, type FROM factory_assets WHERE id = %s", (asset_id,))
            asset = cursor.fetchone()
            if asset and asset['file_path']:
                file_path = os.path.join(os.path.dirname(__file__), asset['file_path'])
                if os.path.exists(file_path):
                    os.remove(file_path)
                # 删除数据库记录
                cursor.execute("DELETE FROM factory_assets WHERE id = %s", (asset_id,))
                conn.commit()
                flash('资源删除成功！', 'success')
    finally:
        conn.close()
    return redirect(url_for('admin_factory'))

# ========== 配色管理 ==========
@app.route('/admin/colors', methods=['GET', 'POST'])
@login_required
def admin_colors():
    """配色管理（修复cursor未定义）"""
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            # 保存主题色
            theme_color = request.form['theme_color'].strip()
            with conn.cursor() as cursor:
                cursor.execute(
                    "REPLACE INTO site_settings (key_name, key_value) VALUES (%s, %s)",
                    ('theme_color', theme_color)
                )
            conn.commit()
            flash('主题色修改成功！', 'success')
            return redirect(url_for('admin_colors'))
        
        # 获取当前主题色
        with conn.cursor() as cursor:
            cursor.execute("SELECT key_value FROM site_settings WHERE key_name = 'theme_color'")
            result = cursor.fetchone()
            theme_color = result['key_value'] if result else '#000000'
        
        return render_template('admin/colors.html', theme_color=theme_color)
    finally:
        conn.close()

# ========== 页脚管理 ==========
@app.route('/admin/footer', methods=['GET', 'POST'])
@login_required
def admin_footer():
    """页脚/联系信息管理"""
    conn = get_db_connection()
    try:
        if request.method == 'POST':
            # 保存页脚信息
            footer_info = json.dumps({
                "address": request.form['address'].strip(),
                "phone": request.form['phone'].strip(),
                "wechat": request.form['wechat'].strip(),
                "weibo": request.form['weibo'].strip(),
                "email": request.form['email'].strip()
            })
            with conn.cursor() as cursor:
                cursor.execute(
                    "REPLACE INTO site_settings (key_name, key_value) VALUES (%s, %s)",
                    ('footer_info', footer_info)
                )
            conn.commit()
            flash('页脚信息修改成功！', 'success')
            return redirect(url_for('admin_footer'))
        
        # 获取当前页脚信息
        with conn.cursor() as cursor:
            cursor.execute("SELECT key_value FROM site_settings WHERE key_name = 'footer_info'")
            result = cursor.fetchone()
            footer_info = json.loads(result['key_value']) if result else {
                "address": "北京市朝阳区某某大厦1001室",
                "phone": "010-12345678",
                "wechat": "rtnut_official",
                "weibo": "https://weibo.com/rtnut",
                "email": "contact@rtnut.com"
            }
        
        return render_template('admin/footer.html', footer_info=footer_info)
    finally:
        conn.close()

# ====================== 启动入口 ======================
if __name__ == '__main__':
    # 初始化数据库（首次运行自动创建表）
    init_database()
    # 启动应用
    app.run(host=HOST, port=PORT, debug=DEBUG)
