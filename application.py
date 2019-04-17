import os, sys, requests, json

from flask import Flask, session, render_template, request, flash, redirect, jsonify
from flask.ext.session import Session
from sqlalchemy import create_engine, Table, Column, Integer, String, Sequence, MetaData
from sqlalchemy.orm import scoped_session, sessionmaker

from werkzeug.security import check_password_hash, generate_password_hash

from helpers import login_required

from datetime import datetime

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'


# Check for environment variable
if not os.getenv("DATABASE_URL"):
    raise RuntimeError("DATABASE_URL is not set")

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine(os.getenv("DATABASE_URL"))
db = scoped_session(sessionmaker(bind=engine))

# Set API key
API_key = 'AdAd1Bho00xaLVfj7ntoRA'

@app.route("/", methods = ['GET','POST'])
@login_required
def index():
    return render_template("index.html")

@app.route("/login", methods = ['GET','POST'])
def login():
    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Query database for username

        username = request.form.get("username")
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          {"username": username})

        result = rows.fetchone()
        # Ensure username exists and password is correct
        if result == None or not check_password_hash(result[2], request.form.get("password")):
            return render_template("error.html", message = "username and/or password is incorrect")


        # Remember which user has logged in
        session["user_id"] = result[0]
        session["user_name"] = result[1]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/register", methods = ['POST','GET'])
def register():

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # check database for entered user_name
        newUser = db.execute("SELECT * FROM users WHERE username =:username",
                            {"username":request.form.get("username")}).fetchone()
        # User exists
        if newUser:
            return render_template("error.html", message = "username already exists")

        # check password match
        elif not request.form.get("password1") == request.form.get("password2"):
            return render_template("error.html",message = "passwords must match")

        # hash & store user password
        hashedPassword = generate_password_hash(request.form.get("password1"),method = 'pbkdf2:sha1', salt_length=8)

        # insert hash into database
        db.execute("INSERT INTO users (username,hash) VALUES (:username,:password)",
                    {"username":request.form.get("username"),
                    "password":hashedPassword})
        db.commit()

        flash('Account successfully created','info')
        return redirect("/login")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("register.html")

@app.route("/search", methods=["GET"])
@login_required
def search():
    """ Get books results """

    # Take input and add a wildcard
    query = "%" + request.args.get("book") + "%"

    # Capitalize all words of input for search
    # https://docs.python.org/3.7/library/stdtypes.html?highlight=title#str.title
    query = query.title()
    rows = db.execute("SELECT isbn, title, author, year FROM books WHERE \
                        isbn LIKE :query OR \
                        title LIKE :query OR \
                        author LIKE :query LIMIT 15",
                        {"query": query})

    # Books not founded
    if rows.rowcount == 0:
        return render_template("error.html", message="we can't find books with that description.")

    # Fetch all the results
    books = rows.fetchall()

    return render_template("results.html", books=books)

    books = rows.fetchall()

    return render_template("results.html", books = books)

@app.route("/book/<isbn>", methods = ["POST","GET"])
@login_required
def book(isbn):

    if request.method == "POST":
        # get current user info
        current = session["user_id"]

        rating = request.form.get("rating")
        comment = request.form.get("comment")
        # search book by ISBN
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn",
                        {"isbn": isbn})

        bookId = row.fetchone()[0]
        # Check user for submissions on this book id
        row2 = db.execute("SELECT * FROM reviews WHERE user_id = :user_id AND book_id = :book_id",
                            {"user_id": current,
                            "book_id": bookId})

        # if a review from this user already exitis, renders book template with existing review by user
        if row2.rowcount == 1:
            flash("you have already submitted a review for this book","warning")
            return redirect("/book/"+isbn)

        # otherwise, save rating and user review
        db.execute("INSERT INTO reviews (comment, rating, user_id, book_id) VALUES\
                    (:comment, :rating, :user_id, :book_id)",
                    {"user_id": current,
                    "book_id": bookId,
                    "comment": comment,
                    "rating": rating})

        db.commit()
        flash("Review submitted successfully","info")
        return redirect("/book/" + isbn)

    else:
        row = db.execute("SELECT isbn, author, title, year FROM books WHERE\
                            isbn = :isbn",
                            {"isbn": isbn})
        bookInfo = row.fetchall()
        """GOODREADS reviews from API"""
        query = requests.get("https://www.goodreads.com/book/review_counts.json",
                params = {"key" : API_key,"isbns": isbn})

        response = query.json()['books'][0]

        bookInfo.append(response)
        # search user reviews
        row = db.execute("SELECT id FROM books WHERE isbn = :isbn",{"isbn": isbn})

        book = row.fetchone()[0]

        results = db.execute("SELECT users.username, comment, rating\
                            FROM users \
                            INNER JOIN reviews \
                            ON users.id = reviews.user_id \
                            WHERE book_id = :book",
                            {"book": book})
        reviews = results.fetchall()
        print(bookInfo)
        return render_template("book.html", bookInfo = bookInfo, reviews = reviews)


@app.route("/pw_change",methods = ["POST","GET"]) # added feature
@login_required
def pw_change():
    if request.method == "GET":
        return render_template("pw_change.html")
    else:
        old_pw = request.form.get("password")
        new_pw1 = request.form.get("new_password1")
        new_pw2 = request.form.get("new_password2")
        print(old_pw)
        # check if old password is correct
        user_result = db.execute("SELECT * FROM users WHERE username = :username",
                          {'username': session["user_name"]})

        if not check_password_hash(user_result.fetchone()[2], old_pw):
            return render_template("error.html", message = "Current password is incorrect")

        elif new_pw1 != new_pw2:
            return render_template("error.html", message = "new passwords must match")

        db.execute("UPDATE users SET hash = :hash WHERE id = :id",
                    {'hash': generate_password_hash(new_pw1,method = 'pbkdf2:sha1', salt_length=8),
                    'id': session["user_id"]})
        db.commit()
        flash("Password change successful!")
        return redirect("/")

@app.route("/api/<isbn>", methods = ["GET"]) #satisfies API request requirement of project
@login_required
def api(isbn):

    # return a JSON response containing the book’s title, author, publication date, ISBN number, review count, and average score
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {"isbn": isbn}).fetchone()
    if book is None:
        return "No Such A Book in the Database", 422
    bookId = book[4]
    numOfRatings = db.execute("SELECT COUNT (*) FROM reviews WHERE book_id = :book_id", {"book_id": bookId}).fetchone()
    averageRating = db.execute("SELECT AVG (rating) FROM reviews WHERE book_id = :book_id", {"book_id": bookId}).fetchone()

    response = {}
    response['title'] = book.title
    response['author'] = book.author
    response['year'] = book.year
    response['isbn'] = book.isbn
    response['review_count'] = str(numOfRatings[0])
    response['average_score'] = '% 1.1f' % averageRating[0]

    return jsonify(response)

@app.route("/logout")
def logout():
    session.clear()

    return redirect("/")
