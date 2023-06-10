import json
import requests
from flask import Flask, redirect, request, render_template, session
from oauthlib import oauth2
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

CLIENT_ID = "343497600283-7nubuspfvloeovhiamn7smnrcuc2mge4.apps.googleusercontent.com"
CLIENT_SECRET = "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"

DATA = {
    'response_type': "code",
    'redirect_uri': "https://localhost:5001/home",
    'scope': 'https://www.googleapis.com/auth/userinfo.email',
    'client_id': CLIENT_ID,
    'prompt': 'consent'
}

URL_DICT = {
    'google_oauth': 'https://accounts.google.com/o/oauth2/v2/auth',
    'token_gen': 'https://oauth2.googleapis.com/token',
    'get_user_info': 'https://www.googleapis.com/oauth2/v3/userinfo'
}

CLIENT = oauth2.WebApplicationClient(CLIENT_ID)
REQ_URI = CLIENT.prepare_request_uri(
    uri=URL_DICT['google_oauth'],
    redirect_uri=DATA['redirect_uri'],
    scope=DATA['scope'],
    prompt=DATA['prompt']
)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    posts = db.relationship('Post', backref='author', lazy=True)
    votes = db.relationship('Vote', backref='user', lazy=True)


class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    content = db.Column(db.Text, nullable=False)
    upvotes = db.Column(db.Integer, default=0)
    downvotes = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    votes = db.relationship('Vote', backref='post', lazy=True)


class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    vote_type = db.Column(db.String(10), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


@app.route('/')
def index():
    return render_template('home.html')


@app.route('/login')
def login():
    return redirect(REQ_URI)


@app.route('/home')
def home():
    code = request.args.get('code')
    token_url, headers, body = CLIENT.prepare_token_request(
        URL_DICT['token_gen'],
        authorization_response=request.url,
        redirect_url=request.base_url,
        code=code
    )
    token_response = requests.post(
        token_url,
        headers=headers,
        data=body,
        auth=(CLIENT_ID, CLIENT_SECRET)
    )
    CLIENT.parse_request_body_response(json.dumps(token_response.json()))
    uri, headers, body = CLIENT.add_token(URL_DICT['get_user_info'])
    response_user_info = requests.get(uri, headers=headers, data=body)
    info = response_user_info.json()

    with app.app_context():
        user = User.query.filter_by(email=info['email']).first()
        print("User Response: ")
        print(info)
        if not user:
            user = User(email=info['email'])
            db.session.add(user)
            db.session.commit()

        session['user_id'] = user.id

    return redirect('/dashboard')


@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    user = User.query.get(user_id)

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        post = Post(title=title, content=content, user_id=user_id)
        db.session.add(post)
        db.session.commit()

    posts = Post.query.all()

    return render_template('dashboard.html', user=user, posts=posts)


@app.route('/post/<int:post_id>/upvote', methods=['POST'])
def upvote(post_id):
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    post = Post.query.get(post_id)

    # Check if the user has already upvoted the post
    existing_vote = Vote.query.filter_by(post_id=post_id, user_id=user_id).first()

    if existing_vote:
        # If the user had previously upvoted, do nothing
        if existing_vote.vote_type == 'upvote':
            return redirect('/dashboard')
        # If the user had previously downvoted, remove the downvote
        else:
            post.downvotes -= 1
            existing_vote.vote_type = 'upvote'
    else:
        post.upvotes += 1
        vote = Vote(post_id=post_id, user_id=user_id, vote_type='upvote')
        db.session.add(vote)

    db.session.commit()

    return redirect('/dashboard')


@app.route('/post/<int:post_id>/downvote', methods=['POST'])
def downvote(post_id):
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    post = Post.query.get(post_id)
    user = User.query.get(user_id)

    # Check if the user has already downvoted the post
    existing_vote = Vote.query.filter_by(post_id=post_id, user_id=user_id).first()

    if existing_vote:
        # If the user had previously downvoted, do nothing
        if existing_vote.vote_type == 'downvote':
            return redirect('/dashboard')
        # If the user had previously upvoted, remove the upvote
        else:
            post.upvotes -= 1
            existing_vote.vote_type = 'downvote'
    else:
        post.downvotes += 1
        vote = Vote(post_id=post_id, user_id=user_id, vote_type='downvote')
        db.session.add(vote)

    db.session.commit()

    return redirect('/dashboard')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect('/')


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5001, ssl_context='adhoc')
