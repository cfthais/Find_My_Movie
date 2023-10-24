from flask import Flask, render_template, redirect, url_for, request, flash
from flask_bootstrap import Bootstrap5
import requests
from forms import LoginForm, RegisterForm
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
import os

# Global variables
DATA = []

# APIs urls and headers
url_api_movie = "https://api.themoviedb.org/3/search/movie"
headers_api_movie = {
    "accept": "application/json",
    "Authorization": os.environ.get("API_MOV_KEY")
}

url_streaming = "https://streaming-availability.p.rapidapi.com/search/title"
headers_streaming = {
    "X-RapidAPI-Key": os.environ.get("API_STR_KEY"),
    "X-RapidAPI-Host": "streaming-availability.p.rapidapi.com"
}

# Set up of DB, flask app, login manager
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
Bootstrap5(app)

db = SQLAlchemy()
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///movies_personal_project.db")
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

# Construction of table with Many to Many relationship (user->many movies | movie->many users)
user_movie = db.Table('user_movie',
                      db.Column('user_id', db.Integer, db.ForeignKey("user.id")),
                      db.Column('movie_id', db.Integer, db.ForeignKey("movie.id")),
                      )


class User(UserMixin, db.Model):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    movies = relationship("Movie", secondary=user_movie, backref="user")


class Movie(db.Model):
    __tablename__ = "movie"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String, unique=True)
    year = db.Column(db.Integer)
    description = db.Column(db.String)
    img_url = db.Column(db.String)
    link = db.Column(db.String)
    streaming = db.Column(db.String)


with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    return db.session.execute(db.select(User).where(User.id == user_id)).scalar()


@app.route("/")
def first_page():
    return render_template("first_page.html")


@app.route("/login", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user is None:
            flash('Invalid User, please try again')
        else:
            if check_password_hash(user.password, form.password.data):
                login_user(user)
                return redirect(url_for('home'))
            else:
                flash("Invalid password, please try again")

    return render_template("login.html", form=form)


@app.route("/register", methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = db.session.execute(db.select(User).where(User.email == form.email.data)).scalar()
        if user is not None:
            flash("This email is already being used")
            return redirect(url_for('login'))
        else:
            new_user = User(
                email=form.email.data,
                password=generate_password_hash(form.password.data, method='pbkdf2', salt_length=8),
                name=form.name.data
            )

            db.session.add(new_user)
            db.session.commit()
            login_user(new_user)
            return redirect(url_for('home'))
    return render_template("register.html", form=form)


@app.route("/home")
@login_required
def home():
    with app.app_context():
        all_movies = current_user.movies
        all_movies_list = []
        all_streaming_list = []
        all_links_list = []
        for movie in all_movies:
            all_movies_list.append(movie.__dict__)
            all_streaming_list.append(movie.__dict__['streaming'][:-1].split())
            all_links_list.append(movie.__dict__['link'][:-1].split())
    return render_template("index.html", movies=all_movies_list, services=all_streaming_list, links=all_links_list,
                           logged_in=current_user.is_authenticated)



@app.route('/delete/id=<id_num>', methods=['GET', 'POST'])
@login_required
def delete_movie(id_num):
    movie_to_delete = db.session.execute(db.select(Movie).where(Movie.id == id_num)).scalar()
    db.session.delete(movie_to_delete)
    db.session.commit()
    return redirect(url_for('home'))


@app.route("/add", methods=['GET', 'POST'])
@login_required
def add_movie():
    if request.method == 'POST':
        new_title = request.form['title']
        params = {
            "query": new_title
        }
        response = requests.get(url_api_movie, headers=headers_api_movie, params=params)
        data = response.json()['results']
        DATA.append(data)
        return redirect(url_for('select_movie'))
    return render_template('add.html', logged_in=current_user.is_authenticated)


@app.route("/select", methods=['GET', 'POST'])
@login_required
def select_movie():
    if request.method == 'POST':

        id_movie = request.form['movie']
        url2 = "https://api.themoviedb.org/3/movie/" + str(id_movie)
        response = requests.get(url2, headers=headers_api_movie)
        data = response.json()
        new_title = data['title']
        new_overview = data['overview']
        new_year = data['release_date'][0:4]
        try:
            new_img_url = "https://image.tmdb.org/t/p/w500/" + data['poster_path']
        except:
            try:
                new_img_url = "https://image.tmdb.org/t/p/w500/" + data['backdrop_path']
            except:
                try:
                    new_img_url = "https://image.tmdb.org/t/p/w500/" + data['belongs_to_collection']['poster_path']
                except:
                    new_img_url = None
        querystring = {"title": new_title, "country": "us", "show_type": "all", "output_language": "en",
                       "series_granularity": "show"}
        response_streaming = requests.get(url_streaming, headers=headers_streaming, params=querystring)
        list_streaming = ""
        list_links = ""
        try:
            data = response_streaming.json()['result'][0]['streamingInfo']['us']
            for el in data:
                if el['service'].capitalize() not in list_streaming:
                    list_streaming += el['service'].capitalize() + ' '
                    list_links += el['link'] + ' '
        except:
            pass
        searched_movie = db.session.execute(db.select(Movie).where(Movie.title == new_title)).scalar()
        if searched_movie is None:
            searched_movie = Movie(
                title=new_title,
                year=new_year,
                description=new_overview,
                img_url=new_img_url,
                link=list_links,
                streaming=list_streaming
            )

            db.session.add(searched_movie)
            db.session.commit()

        current_user.movies.append(searched_movie)
        db.session.commit()

        return redirect(url_for('home'))

    return render_template('select.html', data=DATA[-1], logged_in=current_user.is_authenticated)


@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('first_page'))


if __name__ == '__main__':
    app.run(debug=False)
