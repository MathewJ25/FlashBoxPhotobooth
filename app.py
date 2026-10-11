import os

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'flashbox_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///photobooth.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='customer')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    package = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('bookings', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered.', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password, role='customer')
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/customer/dashboard', methods=['GET', 'POST'])
@login_required
def customer_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
        
    if request.method == 'POST':
        package = request.form.get('package')
        event_date = request.form.get('event_date')
        location = request.form.get('location')
        
        if package and event_date and location:
            new_booking = Booking(user_id=current_user.id, package=package, event_date=event_date, location=location)
            db.session.add(new_booking)
            db.session.commit()
            flash('Booking submitted successfully!', 'success')
        else:
            flash('Please fill in all booking details.', 'danger')
            
        return redirect(url_for('customer_dashboard'))
        
    user_bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.timestamp.desc()).all()
    
    admin = User.query.filter_by(role='admin').first()
    unread_count = 0
    if admin:
        unread_count = Message.query.filter_by(sender_id=admin.id, receiver_id=current_user.id, is_read=False).count()

    return render_template('dashboard.html', bookings=user_bookings, unread_count=unread_count)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    bookings = Booking.query.order_by(Booking.timestamp.desc()).all()
    customers = User.query.filter_by(role='customer').all()
    
    unread_counts = {}
    for c in customers:
        count = Message.query.filter_by(sender_id=c.id, receiver_id=current_user.id, is_read=False).count()
        unread_counts[c.id] = count

    return render_template('admin.html', customers=customers, bookings=bookings, unread_counts=unread_counts)

@app.route('/admin/booking/accept/<int:booking_id>')
@login_required
def accept_booking(booking_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'Accepted'
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({'success': True, 'status': 'Accepted', 'booking_id': booking_id})
    
    flash('Booking accepted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/booking/decline/<int:booking_id>')
@login_required
def decline_booking(booking_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'Declined'
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({'success': True, 'status': 'Declined', 'booking_id': booking_id})
    
    flash('Booking declined.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/delete/booking/<int:booking_id>')
@login_required
def delete_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
        
    db.session.delete(booking)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({'success': True, 'booking_id': booking_id})
        
    flash('Booking deleted successfully!', 'success')
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('customer_dashboard'))

@app.route('/api/unread-count')
@login_required
def api_unread_count():
    if current_user.role == 'admin':
        customers = User.query.filter_by(role='customer').all()
        counts = {}
        for c in customers:
            counts[c.id] = Message.query.filter_by(sender_id=c.id, receiver_id=current_user.id, is_read=False).count()
        return jsonify(counts)
    else:
        admin = User.query.filter_by(role='admin').first()
        count = 0
        if admin:
            count = Message.query.filter_by(sender_id=admin.id, receiver_id=current_user.id, is_read=False).count()
        return jsonify({'unread_count': count})

@app.route('/delete-message/<int:message_id>')
@login_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    # Siguraduhing ang may-ari o ang admin lang ang pwedeng mag-delete
    if message.sender_id == current_user.id or current_user.role == 'admin':
        db.session.delete(message)
        db.session.commit()
    return redirect(request.referrer or url_for('chat'))

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
        
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        flash('Admin account not found.', 'danger')
        return redirect(url_for('index'))

    Message.query.filter_by(sender_id=admin.id, receiver_id=current_user.id, is_read=False).update({Message.is_read: True})
    db.session.commit()

    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            new_msg = Message(sender_id=current_user.id, receiver_id=admin.id, content=content, is_read=False)
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('chat'))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == admin.id)) |
        ((Message.sender_id == admin.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', messages=messages)

@app.route('/admin/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_chat(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    customer = User.query.get_or_404(user_id)

    Message.query.filter_by(sender_id=customer.id, receiver_id=current_user.id, is_read=False).update({Message.is_read: True})
    db.session.commit()

    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            new_msg = Message(sender_id=current_user.id, receiver_id=customer.id, content=content, is_read=False)
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('admin_chat', user_id=customer.id))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == customer.id)) |
        ((Message.sender_id == customer.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('admin_chat.html', messages=messages, customer=customer)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='admin@photobooth.com').first():
            hashed_pw = generate_password_hash('admin123')
            admin_user = User(name='Administrator', email='admin@photobooth.com', password=hashed_pw, role='admin')
            db.session.add(admin_user)
            db.session.commit()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)import os

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'flashbox_secret_key_123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///photobooth.db'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='customer')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    sender = db.relationship('User', foreign_keys=[sender_id])
    receiver = db.relationship('User', foreign_keys=[receiver_id])

class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    package = db.Column(db.String(100), nullable=False)
    event_date = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='Pending')
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('bookings', lazy=True))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email address already registered.', 'danger')
            return redirect(url_for('register'))
            
        hashed_password = generate_password_hash(password)
        new_user = User(name=name, email=email, password=hashed_password, role='customer')
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/customer/dashboard', methods=['GET', 'POST'])
@login_required
def customer_dashboard():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
        
    if request.method == 'POST':
        package = request.form.get('package')
        event_date = request.form.get('event_date')
        location = request.form.get('location')
        
        if package and event_date and location:
            new_booking = Booking(user_id=current_user.id, package=package, event_date=event_date, location=location)
            db.session.add(new_booking)
            db.session.commit()
            flash('Booking submitted successfully!', 'success')
        else:
            flash('Please fill in all booking details.', 'danger')
            
        return redirect(url_for('customer_dashboard'))
        
    user_bookings = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.timestamp.desc()).all()
    
    admin = User.query.filter_by(role='admin').first()
    unread_count = 0
    if admin:
        unread_count = Message.query.filter_by(sender_id=admin.id, receiver_id=current_user.id, is_read=False).count()

    return render_template('dashboard.html', bookings=user_bookings, unread_count=unread_count)

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    bookings = Booking.query.order_by(Booking.timestamp.desc()).all()
    customers = User.query.filter_by(role='customer').all()
    
    unread_counts = {}
    for c in customers:
        count = Message.query.filter_by(sender_id=c.id, receiver_id=current_user.id, is_read=False).count()
        unread_counts[c.id] = count

    return render_template('admin.html', customers=customers, bookings=bookings, unread_counts=unread_counts)

@app.route('/admin/booking/accept/<int:booking_id>')
@login_required
def accept_booking(booking_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'Accepted'
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({'success': True, 'status': 'Accepted', 'booking_id': booking_id})
    
    flash('Booking accepted successfully!', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/booking/decline/<int:booking_id>')
@login_required
def decline_booking(booking_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
    booking = Booking.query.get_or_404(booking_id)
    booking.status = 'Declined'
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({'success': True, 'status': 'Declined', 'booking_id': booking_id})
    
    flash('Booking declined.', 'info')
    return redirect(url_for('admin_dashboard'))

@app.route('/delete/booking/<int:booking_id>')
@login_required
def delete_booking(booking_id):
    booking = Booking.query.get_or_404(booking_id)
    if booking.user_id != current_user.id and current_user.role != 'admin':
        return jsonify({'success': False, 'error': 'Access denied'}), 403
        
    db.session.delete(booking)
    db.session.commit()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or 'application/json' in request.accept_mimetypes:
        return jsonify({'success': True, 'booking_id': booking_id})
        
    flash('Booking deleted successfully!', 'success')
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('customer_dashboard'))

@app.route('/api/unread-count')
@login_required
def api_unread_count():
    if current_user.role == 'admin':
        customers = User.query.filter_by(role='customer').all()
        counts = {}
        for c in customers:
            counts[c.id] = Message.query.filter_by(sender_id=c.id, receiver_id=current_user.id, is_read=False).count()
        return jsonify(counts)
    else:
        admin = User.query.filter_by(role='admin').first()
        count = 0
        if admin:
            count = Message.query.filter_by(sender_id=admin.id, receiver_id=current_user.id, is_read=False).count()
        return jsonify({'unread_count': count})

@app.route('/delete-message/<int:message_id>')
@login_required
def delete_message(message_id):
    message = Message.query.get_or_404(message_id)
    # Siguraduhing ang may-ari o ang admin lang ang pwedeng mag-delete
    if message.sender_id == current_user.id or current_user.role == 'admin':
        db.session.delete(message)
        db.session.commit()
    return redirect(request.referrer or url_for('chat'))

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
        
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        flash('Admin account not found.', 'danger')
        return redirect(url_for('index'))

    Message.query.filter_by(sender_id=admin.id, receiver_id=current_user.id, is_read=False).update({Message.is_read: True})
    db.session.commit()

    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            new_msg = Message(sender_id=current_user.id, receiver_id=admin.id, content=content, is_read=False)
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('chat'))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == admin.id)) |
        ((Message.sender_id == admin.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('chat.html', messages=messages)

@app.route('/admin/chat/<int:user_id>', methods=['GET', 'POST'])
@login_required
def admin_chat(user_id):
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    customer = User.query.get_or_404(user_id)

    Message.query.filter_by(sender_id=customer.id, receiver_id=current_user.id, is_read=False).update({Message.is_read: True})
    db.session.commit()

    if request.method == 'POST':
        content = request.form.get('content')
        if content:
            new_msg = Message(sender_id=current_user.id, receiver_id=customer.id, content=content, is_read=False)
            db.session.add(new_msg)
            db.session.commit()
            return redirect(url_for('admin_chat', user_id=customer.id))

    messages = Message.query.filter(
        ((Message.sender_id == current_user.id) & (Message.receiver_id == customer.id)) |
        ((Message.sender_id == customer.id) & (Message.receiver_id == current_user.id))
    ).order_by(Message.timestamp.asc()).all()

    return render_template('admin_chat.html', messages=messages, customer=customer)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='admin@photobooth.com').first():
            hashed_pw = generate_password_hash('admin123')
            admin_user = User(name='Administrator', email='admin@photobooth.com', password=hashed_pw, role='admin')
            db.session.add(admin_user)
            db.session.commit()
    
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
