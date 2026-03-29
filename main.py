import os

from flask import Flask, render_template, request, redirect, url_for
from flask_login import LoginManager,UserMixin,login_user,logout_user,login_required,current_user
import sqlite3
from werkzeug.security import generate_password_hash,check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tapok'

login_manager = LoginManager(app)
login_manager.login_view = 'login'
class User(UserMixin):
    def __init__(self,id,username,password_hash):
        self.id = id
        self.username = username
        self.password_hash = password_hash
    def set_password(self,password):
        self.password_hash = generate_password_hash(method='pbkdf2:sha256')
    def password_chek(self,password):
        return check_password_hash(self.password_hash, password)
@login_manager.user_loader
def load_user(user_id):
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    user = cursor.execute('SELECT * FROM users WHERE id = ?', (user_id)).fetchone()
    if user is not None:
        return User(user[0],user[1],user[2])
    return None
def close_db(connection=None):
    if connection is not None:
        connection.close()
@app.teardown_appcontext
def close_connection(exception):
    close_db()

@app.route('/')
def index():
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    cursor.execute('''
        SELECT 
            posts.id,
            posts.title,
            posts.content, 
            posts.author_id,
            users.username,
            COUNT(likes.id) AS likes 
        FROM 
            posts 
        JOIN 
            users ON posts.author_id = users.id
        LEFT JOIN
          likes ON posts.id = likes.post_id 
        GROUP BY 
            posts.id, posts.title, posts.content, posts.author_id, users.username
    ''')
    result = cursor.fetchall()
    posts = []
    for post in reversed(result):
        posts.append({'id': post[0],'title': post[1], 'content': post[2], 'author_id': post[3], 'user': post[4], 'likes': post[5]})
        if current_user.is_authenticated:
            cursor.execute('SELECT post_id FROM likes WHERE user_id = ?',(str(current_user.id)))
            likes_result = cursor.fetchall()
            liked_posts = []
            for like in likes_result:
                liked_posts.append(like[0])
            posts[-1]['liked_posts'] = liked_posts
    context = {'posts':posts}

    return render_template('blog.html', **context)
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = set(['txt','pdf','png','jpg','jpeg','gif'])
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
@app.route('/add/', methods=['GET','POST'])
@login_required
def add_post():
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    print(request.form)
    if request.method == 'POST':
        print(1)
        title = request.form['title']
        content = request.form['content']
        file = request.files['image']
        print(file)
        file.save(os.path.join(UPLOAD_FOLDER, file.filename))
        cursor.execute(f"INSERT INTO posts(title,content,author_id,image) VALUES ('{title}','{content}',{current_user.id},'{file.filename}')")
        connection.commit()
        close_db(connection)
        return redirect(url_for('index'))
    return render_template('add_post.html' )
@app.route('/post/<post_id>')
def post (post_id):
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    post = cursor.execute(f'SELECT * from posts where id = {post_id}').fetchall()[0]
    user = cursor.execute(f'SELECT * from users where id = {post[3]}').fetchall()[0]
    post_dict = {'id': post[0], 'title': post[1], 'content': post[2], 'username': user[1], 'image': post[4]}
    return render_template('post.html',post=post_dict)
@app.route('/register', methods=['GET','POST'])
def register ():
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        try:
            cursor.execute('INSERT INTO users(email, username, password_hash)VALUES (?,?,?)',(email,username,generate_password_hash(password,method='pbkdf2:sha256')))
            connection.commit()
            cursor.close()
            connection.close()
            return render_template('login.html')
        except sqlite3.IntegrityError:
            cursor.close()
            connection.close()
            return render_template('register.html',message='username already exists')
    return render_template('register.html')
@app.route('/login', methods=['GET','POST'])
def login ():
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        try:
            user=cursor.execute('SELECT * FROM users WHERE username = ?',(username,)).fetchone()
            if user and User(user[0], user[1], user[2]).password_chek(password):
                login_user(User(user[0], user[1], user[2]))
                return redirect(url_for('index'))
            else:
                return render_template('login.html',message='Invalid username or password')
            cursor.close()
            connection.close()

        except sqlite3.IntegrityError:
            cursor.close()
            connection.close()
            return render_template('login.html',message='username already exists')
    return render_template('login.html')
@app.route('/delete/<int:post_id>',methods=['POST'])
@login_required
def delete_post(post_id):
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    print(post_id)
    post = cursor.execute(f'SELECT * FROM posts WHERE id = {post_id}').fetchone()
    if post and post[3] == current_user.id:
        cursor.execute(f'DELETE FROM posts WHERE id = {post_id}',)
        connection.commit()
        return redirect(url_for('index'))
    else:
        return redirect(url_for('index'))
def user_is_liking(user_id,post_id):
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    like = cursor.execute('SELECT * FROM likes where user_id = ? AND post_id = ?',(user_id,post_id)).fetchone()
    return bool (like)
@app.route('/like/<int:post_id>')
@login_required
def like_post(post_id):
    connection = sqlite3.connect('sqlite.db')
    cursor = connection.cursor()
    post = cursor.execute('SELECT * FROM posts WHERE id = ?',(post_id,)).fetchone()
    if post:
        if user_is_liking(current_user.id, post_id):
            cursor.execute('DELETE FROM likes WHERE user_id = ? AND post_id = ?',(current_user.id, post_id))
            connection.commit()
            print('You unliked this post.')
        elif not user_is_liking(current_user.id, post_id):
            cursor.execute('INSERT INTO likes(user_id,post_id) VALUES (?,?)',(current_user.id, post_id))
            connection.commit()
            print('You liked this post.')
        return redirect(url_for('index'))
    return redirect(url_for('index'))
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))
if __name__ == '__main__':
    app.run()
