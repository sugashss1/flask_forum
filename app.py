from flask import Flask, render_template, request, redirect, url_for, make_response
from mongoengine import connect, Document, StringField, ListField, ReferenceField, IntField
from hashlib import md5
from functools import wraps
import secrets

# Database connections
connect('forum_database', host='localhost', port=27017, alias='forum_db')
connect('user_data', host='localhost', port=27017, alias='user_db')

# Define your models with metadata
class Post(Document):
    title = StringField(required=True)
    content = StringField(required=True)
    replies = ListField(ReferenceField('Reply'))
    users_liked = ListField(ReferenceField('user_data'))
    no_likes = IntField(default=0)

    meta = {
        'db_alias': 'forum_db'
    }

    def __str__(self):
        return f'Post(title={self.title}, content={self.content})'

class Reply(Document):
    content = StringField(required=True)
    post = ReferenceField('Post', required=True) 
    
    meta = {
        'db_alias': 'forum_db'
    }

    def __str__(self):
        return f'Reply(content={self.content}, post={self.post.title})'

class user_data(Document):
    username = StringField(required=True)
    password = StringField(required=True)
    post_liked = ListField(ReferenceField('Post'))
    session_token = StringField()  # Added field for session management

    meta = {
        'db_alias': 'user_db'
    }

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)  # Generate a secure secret key

# Login decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_token = request.cookies.get('session_token')
        if not session_token:
            return redirect(url_for('login'))
        
        user = user_data.objects(session_token=session_token).first()
        if not user:
            return redirect(url_for('login'))
            
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    session_token = request.cookies.get('session_token')
    if session_token:
        return user_data.objects(session_token=session_token).first()
    return None

@app.route('/')
@login_required
def index():
    posts = Post.objects()
    return render_template('index.html', posts=posts)

@app.route('/dashboard', methods=["GET", "POST"])
@login_required
def dashboard():
    total_posts = Post.objects.count()
    total_replies = Reply.objects.count()
    active_users_count = user_data.objects.filter(post_liked__exists=True).count()
    
    most_liked_posts = Post.objects.order_by('-no_likes')[:5]
    most_commented_posts = Post.objects.order_by('-replies__size')[:5]
    
    return render_template('dashboard.html', 
                         total_posts=total_posts, 
                         total_replies=total_replies, 
                         active_users=active_users_count,
                         most_liked=most_liked_posts,
                         most_commented=most_commented_posts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        user = user_data.objects(username=username).first()
        
        if not user:
            return render_template('login.html', msg="Username not found Register")
        
        if md5(password.encode()).hexdigest() == user.password:
            # Generate and store session token
            session_token = secrets.token_hex(16)
            user.update(session_token=session_token)
            
            # Create response with redirect
            response = make_response(redirect('/'))
            # Set secure cookie with session token
            response.set_cookie('session_token', 
                              session_token, 
                              httponly=True, 
                              secure=True,  # Enable in production with HTTPS
                              samesite='Strict',
                              max_age=3600)  # 1 hour expiration
            return response
        else:
            return render_template('login.html', msg='Invalid Username or Password')
    
    return render_template('login.html', msg="")

@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session_token = request.cookies.get('session_token')
    if session_token:
        user = user_data.objects(session_token=session_token).first()
        if user:
            user.update(unset__session_token=1)
    
    response = make_response(redirect(url_for('login')))
    response.delete_cookie('session_token')
    return response

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if user_data.objects(username=username).first():
            return render_template("register.html", msg="username already exists")
        
        if password != confirm_password:
            return render_template("register.html", msg="The passwords don't match")

        new_user = user_data(username=username, 
                           password=md5(password.encode()).hexdigest())
        new_user.save()
        return redirect(url_for('login'))
    
    return render_template("register.html", msg="")

@app.route('/create_post', methods=['POST'])
@login_required
def create_post():
    title = request.form.get('title')
    content = request.form.get('content')
    
    new_post = Post(title=title, content=content)
    new_post.save()
    
    return redirect('/')

@app.route('/reply/<post_id>', methods=['POST'])
@login_required
def reply(post_id):
    content = request.form.get('content')
    post = Post.objects.get(id=post_id)
    
    new_reply = Reply(content=content, post=post)
    new_reply.save()
    
    post.update(push__replies=new_reply)
    return redirect(url_for('index'))

@app.route('/like/<post_id>', methods=['POST', 'GET'])
@login_required
def like(post_id):
    post = Post.objects.get(id=post_id)
    user = get_current_user()
    
    if user in post.users_liked:
        user.update(pull__post_liked=post)
        post.update(pull__users_liked=user)
        post.update(inc__no_likes=-1)
    else:
        user.update(push__post_liked=post)
        post.update(push__users_liked=user)
        post.update(inc__no_likes=1)
    
    return redirect(url_for('index') + "#" + str(post_id))

if __name__ == '__main__':
    app.run(debug=True)
