from flask import Flask, render_template, request, redirect, url_for
from mongoengine import connect, Document, StringField, ListField, ReferenceField,IntField
from hashlib import md5

is_log_in=False
current_user_id='673826e6720d6a253277342a'

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
        'db_alias': 'forum_db'  # Specify the database for this model
    }

    def __str__(self):
        return f'Post(title={self.title}, content={self.content})'


class Reply(Document):
    content = StringField(required=True)
    post = ReferenceField('Post', required=True) 
    
    meta = {
        'db_alias': 'forum_db'  # Specify the database for this model
    }

    def __str__(self):
        return f'Reply(content={self.content}, post={self.post.title})'


class user_data(Document):
    username = StringField(required=True)
    password = StringField(required=True)
    post_liked = ListField(ReferenceField('Post'))

    meta = {
        'db_alias': 'user_db'  # Specify the database for this model
    }


app = Flask(__name__)

@app.route('/')
def index():
    if not is_log_in:
        return redirect(url_for('login'))
    # Get all posts from the database
    posts = Post.objects()
    return render_template('index.html', posts=posts)


@app.route('/dashboard',methods=["GET","POST"])
def dashboard():
    total_posts = Post.objects.count()
    total_replies = Reply.objects.count()
    active_users_count = user_data.objects.filter(post_liked__exists=True).count()
    
    # Get top liked posts
    most_liked_posts = Post.objects.order_by('-no_likes')[:5]  # Top 5 liked posts
    most_commented_posts = Post.objects.order_by('-replies__size')[:5]  # Top 5 commented posts
    
    return render_template('dashboard.html', 
                           total_posts=total_posts, 
                           total_replies=total_replies, 
                           active_users=active_users_count,
                           most_liked=most_liked_posts,
                           most_commented=most_commented_posts)


# Route for the login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    global is_log_in,current_user_id
    if request.method == 'POST':
        username = request.form['username'].lower()
        password = request.form['password']
        db_password = user_data.objects(username=username).first()
        if not db_password:
            return render_template('login.html',msg="Username not found Register")
        current_user_id=db_password.id
        # Control flow using if-else
        if md5(password.encode()).hexdigest() == db_password.password:
            is_log_in=True
            return redirect('/')
            
        else:
            return render_template('login.html',msg='Invalid Username or Password')
    return render_template('login.html',msg="")

@app.route("/logout",methods=["post"])
def logout():
    global is_log_in
    is_log_in=False
    return redirect(url_for("login"))

@app.route('/register',methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form['username'].lower()
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        name=user_data.objects(username=username).first()
        if name:
            return render_template("register.html",msg="username already exists")
        
        if password!=confirm_password:
            return render_template("register.html",msg="The passwords don't match")

        new=user_data(username=username,password=md5(password.encode()).hexdigest())
        new.save()
        return redirect(url_for('login'))
    
    return render_template("register.html",msg="")

@app.route('/create_post', methods=['POST'])
def create_post():

    if request.method=='POST':
        title = request.form.get('title')
        content = request.form.get('content')
        
        # Create a new post and save to the database
        new_post = Post(title=title, content=content)
        new_post.save()
        
        return redirect('/')

@app.route('/reply/<post_id>', methods=['POST'])
def reply(post_id):
    content = request.form.get('content')
    post = Post.objects.get(id=post_id)  # Find the post to reply to
    
    # Create a new reply and link it to the post
    new_reply = Reply(content=content, post=post)
    new_reply.save()

    # Add the reply to the post's list of replies
    post.update(push__replies=new_reply)
    
    return redirect(url_for('index'))

@app.route('/like/<post_id>',methods=['POST','get'])
def like(post_id):
    post = Post.objects.get(id=post_id)
    user=user_data.objects.get(id=current_user_id)
    if user in post.users_liked:
        user.update(pull__post_liked=post)
        post.update(pull__users_liked=user)
        post.update(inc__no_likes=-1)
        return redirect(url_for('index')+"#"+post_id)

    user.update(push__post_liked=post)
    post.update(push__users_liked=user)
    post.update(inc__no_likes=1)
    return redirect(url_for('index')+"#"+post_id)

if __name__ == '__main__':
    app.run(debug=True)
