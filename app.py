import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'hellfire-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hell.db'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

# Kullanıcı modeli
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(150), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    theme = db.Column(db.String(50), default="fire")
    profile_pic = db.Column(db.String(150), default="default.jpg")

# Konu modeli
class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), nullable=False)
    likes = db.relationship("Like", backref="topic", lazy="dynamic")

# Yorum modeli
class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(100), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'), nullable=False)
    topic = db.relationship('Topic', backref=db.backref('comments', lazy=True))

# Beğeni modeli
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    topics = Topic.query.order_by(Topic.id.desc()).all()
    return render_template("index.html", topics=topics)

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_pw = generate_password_hash(password)

        if User.query.filter_by(username=username).first():
            flash("Bu kullanıcı adı zaten kullanılıyor.")
            return redirect(url_for("register"))

        new_user = User(username=username, password=hashed_pw)
        db.session.add(new_user)
        db.session.commit()
        flash("Kayıt başarılı! Giriş yapabilirsin.")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Giriş başarılı!")
            return redirect(url_for("home"))
        else:
            flash("Kullanıcı adı veya şifre hatalı.")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Çıkış yapıldı.")
    return redirect(url_for("home"))

@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        new_topic = Topic(title=title, content=content, author=current_user.username)
        db.session.add(new_topic)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("create.html")

@app.route("/topic/<int:id>")
def topic(id):
    topic = Topic.query.get_or_404(id)
    liked = False
    if current_user.is_authenticated:
        liked = Like.query.filter_by(user_id=current_user.id, topic_id=id).first() is not None
    return render_template("topic.html", topic=topic, liked=liked)

@app.route("/topic/<int:id>/comment", methods=["POST"])
@login_required
def comment(id):
    topic = Topic.query.get_or_404(id)
    content = request.form["content"]
    new_comment = Comment(content=content, author=current_user.username, topic=topic)
    db.session.add(new_comment)
    db.session.commit()
    return redirect(url_for("topic", id=id))

@app.route("/comment/<int:comment_id>/delete", methods=["POST"])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user.username:
        flash("Bu yorumu sadece yazan kişi silebilir!")
        return redirect(url_for("topic", id=comment.topic_id))
    db.session.delete(comment)
    db.session.commit()
    flash("Yorum silindi!")
    return redirect(url_for("topic", id=comment.topic_id))

@app.route("/like/<int:topic_id>", methods=["POST"])
@login_required
def like(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, topic_id=topic_id).first()

    if existing_like:
        db.session.delete(existing_like)
    else:
        new_like = Like(user_id=current_user.id, topic_id=topic_id)
        db.session.add(new_like)

    db.session.commit()
    return redirect(url_for("topic", id=topic_id))

@app.route("/admin")
@login_required
def admin():
    if not current_user.is_admin:
        flash("Bu sayfa sadece adminlere özel!")
        return redirect(url_for("home"))
    users = User.query.all()
    topics = Topic.query.all()
    return render_template("admin.html", users=users, topics=topics)

@app.route("/admin/delete_topic/<int:id>", methods=["POST"])
@login_required
def delete_topic(id):
    if not current_user.is_admin:
        flash("Yetkisiz giriş.")
        return redirect(url_for("home"))
    topic = Topic.query.get_or_404(id)
    db.session.delete(topic)
    db.session.commit()
    flash("Konu silindi.")
    return redirect(url_for("admin"))

@app.route("/admin/edit_topic/<int:id>", methods=["GET", "POST"])
@login_required
def edit_topic(id):
    if not current_user.is_admin:
        flash("Yetkisiz giriş.")
        return redirect(url_for("home"))

    topic = Topic.query.get_or_404(id)

    if request.method == "POST":
        topic.title = request.form["title"]
        topic.content = request.form["content"]
        db.session.commit()
        flash("Konu güncellendi.")
        return redirect(url_for("admin"))

    return render_template("edit_topic.html", topic=topic)

@app.route("/profile/<username>", methods=["GET", "POST"])
def profile(username):
    user = User.query.filter_by(username=username).first_or_404()

    if request.method == "POST" and current_user.username == username:
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                current_user.profile_pic = filename
                db.session.commit()
                flash("Profil fotoğrafı güncellendi!")

    topics = Topic.query.filter_by(author=username).all()
    return render_template("profile.html", user=user, topics=topics)

@app.route("/set_theme", methods=["POST"])
@login_required
def set_theme():
    theme = request.form.get("theme")
    current_user.theme = theme
    db.session.commit()
    flash("Tema güncellendi!")
    return redirect(url_for("profile", username=current_user.username))

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
