import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date

app = Flask(__name__)
app.secret_key = 'ff_secret_secure_key_2026'

# إعداد قاعدة البيانات المحلية SQLite
app.config['SQLALCHEMY_DATABASE_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# --- جداول قاعدة البيانات ---

# جدول المستخدمين واللاعبين
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    points = db.Column(db.Float, default=0.0)
    last_claim_date = db.Column(db.String(20), nullable=True)
    is_admin = db.Column(db.Boolean, default=False)

# جدول طلبات الشحن المنتظرة
class RedeemRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    player_id = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), default='قيد الانتظار')

# إنشاء قاعدة البيانات تلقائياً عند التشغيل الأول
with app.app_context():
    db.create_all()

# --- المسارات البرمجية للموقع ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    return render_template('index.html', user=user, max_points=2.0)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        if User.query.filter_by(username=username).first():
            flash('اسم المستخدم هذا مسجل بالفعل!', 'danger')
            return redirect(url_for('register'))
        
        # تشفير كلمة المرور لحماية البيانات
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        
        # أول حساب يتم تسجيله في الموقع يصبح الأدمن تلقائياً لتسهيل التحكم
        is_first_user = User.query.count() == 0
        
        new_user = User(username=username, password=hashed_password, is_admin=is_first_user)
        db.session.add(new_user)
        db.session.commit()
        
        flash('تم إنشاء الحساب بنجاح! يمكنك الآن تسجيل الدخول.', 'success')
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            return redirect(url_for('index'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور!', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/daily-claim', methods=['POST'])
def daily_claim():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    today_str = str(date.today())
    
    if user.last_claim_date == today_str:
        flash('لقد قمت بجمع نقاط اليوم بالفعل! عد غداً بعد الـتحديث الإعلاني.', 'warning')
    elif user.points >= 2.0:
        flash('لقد وصلت بالفعل إلى الحد الأقصى (2 نقطة)، يرجى استبدال نقاطك الآن!', 'info')
    else:
        user.points = min(user.points + 0.5, 2.0)
        user.last_claim_date = today_str
        db.session.commit()
        flash('تمت إضافة 0.5 نقطة إلى رصيدك بنجاح! 🎉', 'success')
        
    return redirect(url_for('index'))

@app.route('/redeem', methods=['POST'])
def redeem():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    player_id = request.form.get('player_id').strip()
    
    if not player_id:
        flash('يرجى إدخال معرف اللاعب (ID) بشكل صحيح!', 'danger')
    elif user.points < 2.0:
        flash('عذراً، تحتاج إلى 2 نقطة كاملة لتتمكن من الشحن!', 'danger')
    else:
        # إضافة الطلب لجدول الأدمن
        new_request = RedeemRequest(username=user.username, player_id=player_id)
        db.session.add(new_request)
        
        # خصم وتصفير النقاط
        user.points = 0.0
        db.session.commit()
        
        flash('تم إرسال طلب الشحن إلى الإدارة بنجاح! سيتم التحقق والشحن خلال 24 ساعة. 💎', 'success')
        
    return redirect(url_for('index'))

# لوحة تحكم الإدارة (الأدمن) لرؤية الـ IDs
@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('غير مصرح لك بدخول هذه الصفحة!', 'danger')
        return redirect(url_for('index'))
        
    requests_list = RedeemRequest.query.filter_by(status='قيد الانتظار').all()
    return render_template('admin.html', requests=requests_list)

@app.route('/admin/complete/<int:req_id>', methods=['POST'])
def complete_request(req_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect(url_for('index'))
        
    req = RedeemRequest.query.get(req_id)
    if req:
        req.status = 'تم الشحن'
        db.session.commit()
        flash(f'تم تعيين الطلب الخاص بالمستخدم {req.username} كمكتمل.', 'success')
    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True)
