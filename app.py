from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
import datetime
import secrets
import string
import random
from functools import wraps


app = Flask(__name__)
app.secret_key = 'Ubv6trWUdU'


HOST = "localhost"
USER = "root"
PASSWORD = "12345678"
DATABASE = "movieticketbooking"

# Define connection to the database
def connect_to_database():
    return mysql.connector.connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        database=DATABASE
    )
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            print("User not in session")
            return redirect(url_for('login'))
        if not is_admin(session['user']):
            print("User is not an admin")
            return redirect(url_for('login'))  # Redirect to login if the user is not an admin
        return f(*args, **kwargs)
    return decorated_function

def is_admin(email):
    try:
        db = connect_to_database()
        cursor = db.cursor()
        cursor.execute("SELECT AdminEmail FROM Admin WHERE AdminEmail = %s", (email,))
        admin = cursor.fetchone()
        print("Admin:", admin) 
        return admin is not None
    except mysql.connector.Error as err:
        print(f"Error checking admin status: {err}")
        return False
    finally:
        cursor.close()
        db.close()


@app.route('/admin')
@admin_required
def admin():
    # Execute the first query for customer results
    db = connect_to_database()
    cursor = db.cursor()
    cursor.execute("""
        SELECT `User`.Name
        FROM `User`
        WHERE `User`.UserID IN (
             SELECT BookingInfo.UserID
             FROM BookingInfo
             JOIN ShowTime ON BookingInfo.ShowID = ShowTime.ShowID
             WHERE MONTH(ShowTime.ShowTiming) = MONTH(CURRENT_DATE()) AND YEAR(ShowTime.ShowTiming) = YEAR(CURRENT_DATE())
             GROUP BY BookingInfo.UserID
             HAVING COUNT(BookingInfo.ShowID) > 2
             )
    """)
    customer_results = cursor.fetchall()
    
    # Execute the second query for payment results
    db = connect_to_database()
    cursor = db.cursor()
    cursor.execute("""
        SELECT `User`.Name
        FROM `User`
        JOIN Payment ON `User`.UserID = Payment.UserID
        WHERE Payment.Amount >= ALL (
            SELECT MIN(Amount) FROM Payment GROUP BY ShowID
        )
    """)
    payment_results = cursor.fetchall()
    return render_template('admin.html', customer_results=customer_results, payment_results=payment_results)





def group_by_movies():
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.callproc('GroupByMovies')
    results = []
    for result in cursor.stored_results():
        results.append(result.fetchall())
    print("group_by_movies()")
    print(results)
    conn.close()
    return results

def correlated_subquery():
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.callproc('CorrelatedSubquery')
    results = []
    for result in cursor.stored_results():
        results.append(result.fetchall())
    print("correlated_subquery()")
    print(results)
    conn.close()
    return results

def inner_join_shows():
    conn = connect_to_database()
    cursor = conn.cursor()
    cursor.callproc('InnerJoinShows')
    results = []
    for result in cursor.stored_results():
        results.append(result.fetchall())
    print("inner_join_shows()")
    print(results)
    conn.close()
    
    return results

def view_next_immediate_shows():
    try:
        conn = connect_to_database()
        cursor = conn.cursor()
        cursor.callproc('ViewNextImmediateShows')
        results = []
        for result in cursor.stored_results():
            results.append(result.fetchall())
        conn.close()
        return results
    except mysql.connector.errors.ProgrammingError as e:
        if e.errno == 1050:
            # Table already exists, handle the error gracefully
            return []
        else:
            # Handle other errors
            raise e

# Route to render assigned.html and pass query results
@app.route('/assigned')
def assigned():
    group_by_movies_result = group_by_movies()
    correlated_subquery_result = correlated_subquery()
    
    inner_join_shows_result = inner_join_shows()
    view_next_immediate_shows_result = view_next_immediate_shows()
    return render_template('assigned.html', 
                           group_by_movies_result=group_by_movies_result,
                           correlated_subquery_result=correlated_subquery_result,
                           inner_join_shows_result=inner_join_shows_result,
                           view_next_immediate_shows_result=view_next_immediate_shows_result)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        phone = request.form['phone']
        age = request.form['age']

        db = connect_to_database()
        cursor = db.cursor()

        try:
            cursor.execute("INSERT INTO user (name, email, password, PhoneNo, age) VALUES (%s, %s, %s, %s, %s)", (name, email, password, phone, age))
            db.commit()

            # Registration successful, redirect to login page
            return redirect(url_for('login'))

        except mysql.connector.Error as err:
            print(f"Error: {err}")
            return render_template('register.html', error='An error occurred, please try again later')

        finally:
            cursor.close()
            db.close()
    else:
        # Render the registration page
        return render_template('register.html')

def connect_to_database():
    return mysql.connector.connect(
        host=HOST,
        user=USER,
        password=PASSWORD,
        database=DATABASE
    )

def get_latest_movies():
    """Fetches the latest movies with showtimes from the database."""
    try:
        db = connect_to_database()
        cursor = db.cursor()

        # Fetching the latest movies
        cursor.execute("""
            SELECT m.MovieID, m.MovieName, m.MovieRate, s.ShowID, s.TheaterID, s.ShowTiming 
            FROM Movie m 
            JOIN Showtime s ON m.MovieID = s.MovieID 
            ORDER BY m.MovieID
        """)
        movies_with_showtimes = cursor.fetchall()
        
        return movies_with_showtimes
    except mysql.connector.Error as err:
        print(f"Error fetching movies: {err}")
        return []
    finally:
        cursor.close()
        db.close()



# Function to generate a unique ticket ID
def generate_ticket_id():
    try:
        db = connect_to_database()
        cursor = db.cursor()
        cursor.execute("SELECT MAX(TicketID) FROM tickets")
        last_ticket_id = cursor.fetchone()[0]
        if last_ticket_id:
            return last_ticket_id + 1
        else:
            return 1
    except mysql.connector.Error as err:
        print(f"Error generating ticket ID: {err}")
        return None
    finally:
        cursor.close()
        db.close()

# Route to render individual movie pages
@app.route("/movie/<int:movie_id>")
def movie_details(movie_id):
    try:
        db = connect_to_database()
        cursor = db.cursor()
        # Fetch movie details based on movie_id
        cursor.execute("SELECT * FROM movie WHERE MovieID = %s", (movie_id,))
        movie_details = cursor.fetchone()
        if movie_details:
            # Fetch show timings for the movie
            cursor.execute("SELECT * FROM showtime WHERE MovieID = %s", (movie_id,))
            show_timings = cursor.fetchall()
            return render_template("movie_details.html", movie=movie_details, show_timings=show_timings)
        else:
            return render_template("error.html", message="Movie not found")
    except mysql.connector.Error as err:
        print(f"Error fetching movie details: {err}")
        return render_template("error.html", message="An error occurred while fetching movie details")
    finally:
        cursor.close()
        db.close()


# Route to handle payment submission
@app.route("/make_payment", methods=["POST"])
def make_payment():
    if request.method == "POST":
        user_id = request.form["user_id"]
        show_id = request.form["show_id"]
        seating_no = request.form["seating_no"]
        # Update bookinginfo table with booking information
        update_booking_info(user_id, show_id, seating_no)
        # Update tickets table with booking information
        update_tickets(user_id, show_id, seating_no)
        # Redirect to a success page
        return redirect(url_for("payment_success"))
    else:
        return render_template("error.html", message="Invalid request")

# Route to render payment success page
@app.route("/payment_success")
def payment_success():
    return render_template("payment_success.html")

# Function to authenticate user
def authenticate_user(email, password):
    try:
        db = connect_to_database()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM user WHERE email = %s AND password = %s", (email, password))
        user = cursor.fetchone()
        return user
    except mysql.connector.Error as err:
        print(f"Error authenticating user: {err}")
        return None
    finally:
        cursor.close()
        db.close()


def get_now_showing_shows(movie_id=None):
    """Fetches the currently showing shows with details from the database."""
    try:
        db = connect_to_database()
        cursor = db.cursor()
        current_time = datetime.datetime.now()
        if movie_id is not None:
            cursor.execute(
                """
                SELECT ShowTime.ShowID, Movie.MovieName, Theater.TheaterName, ShowTime.ShowTiming
                FROM ShowTime
                JOIN Movie ON ShowTime.MovieID = Movie.MovieID
                JOIN Theater ON ShowTime.TheaterID = Theater.TheaterID
                WHERE ShowTime.ShowTiming >= %s AND ShowTime.MovieID = %s""",
                (current_time, movie_id,)
            )
        else:
            cursor.execute(
                """
                SELECT ShowTime.ShowID, Movie.MovieName, Theater.TheaterName, ShowTime.ShowTiming
                FROM ShowTime
                JOIN Movie ON ShowTime.MovieID = Movie.MovieID
                JOIN Theater ON ShowTime.TheaterID = Theater.TheaterID
                WHERE ShowTime.ShowTiming >= %s""",
                (current_time,)
            )
        
        shows = cursor.fetchall()
        return shows
    except mysql.connector.Error as err:
        print(f"Error fetching shows: {err}")
        return []
    finally:
        cursor.close()
        db.close()

@app.route("/login", methods=['GET', 'POST'])
def login():
    """Handles user login."""
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = authenticate_user(email, password)
        if user:
            user_id = user[0]
            session['user_id'] = user_id  # Store user ID in the session
            session['user'] = email  # Start session and store user email
            
            # Check if the user is an admin
            if is_admin(email):
                session['admin'] = True
            
            return redirect(url_for('dashboard'))
        else:
            return render_template('login.html', error='Invalid email or password')
    else:
        return render_template('login.html')

def get_user_tickets(user_id):
    """Fetches the tickets booked by the user."""
    try:
        db = connect_to_database()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT b.TicketID, s.MovieID, s.TheaterID, s.ShowTiming, b.SeatingNo, b.Price, b.Confirmation
            FROM bookinginfo b
            JOIN showtime s ON b.ShowID = s.ShowID
            WHERE b.UserID = %s
            """,
            (user_id,)
        )
        tickets = cursor.fetchall()
        return tickets
    except mysql.connector.Error as err:
        print(f"Error fetching user tickets: {err}")
        return []
    finally:
        cursor.close()
        db.close()

def get_user_payments(user_id):
    """Fetches the payments made by the user."""
    try:
        db = connect_to_database()
        cursor = db.cursor()
        cursor.execute(
            """
            SELECT p.PaymentID, p.TransactionID, p.Amount, p.PaymentMethod, p.PaymentType, p.GiftcardID, s.ShowTiming
            FROM payment p
            JOIN showtime s ON p.ShowID = s.ShowID
            WHERE p.UserID = %s
            """,
            (user_id,)
        )
        payments = cursor.fetchall()
        return payments
    except mysql.connector.Error as err:
        print(f"Error fetching user payments: {err}")
        return []
    finally:
        cursor.close()
        db.close()


@app.route("/dashboard")
def dashboard():
    """Renders the user dashboard."""
    if 'user' in session:
        user_email = session['user']
        # Fetch user-specific dashboard data here
        # Get user ID based on email
        try:
            db = connect_to_database()
            cursor = db.cursor()
            cursor.execute("SELECT UserID FROM user WHERE email = %s", (user_email,))
            user_row = cursor.fetchone()
            if user_row is not None:
                user_id = user_row[0]
                # Fetch user tickets and payments
                user_tickets = get_user_tickets(user_id)
                user_payments = get_user_payments(user_id)
                return render_template("dashboard.html", user=user_email, tickets=user_tickets, payments=user_payments)
            else:
                return render_template("error.html", message="User not found")
        except mysql.connector.Error as err:
            print(f"Error fetching user data: {err}")
            return render_template("error.html", message="An error occurred while fetching user data.")
        finally:
            cursor.close()
            db.close()
    else:
        return redirect(url_for('login'))  # Redirect to login if not logged in


def generate_confirmation_code():
    return "Confirmed-TXN" + ''.join(random.choices(string.digits, k=4))


def generate_ticket_id():
    try:
        db = connect_to_database()
        cursor = db.cursor()
        cursor.execute("SELECT MAX(TicketID) FROM tickets")
        last_ticket_id = cursor.fetchone()[0]
        if last_ticket_id:
            return last_ticket_id + 1
        else:
            return 1
    except mysql.connector.Error as err:
        print(f"Error generating ticket ID: {err}")
        return None
    finally:
        cursor.close()
        db.close()

def generate_seating_numbers(num_tickets, existing_seats):
    MAX_SEATS_PER_ROW = 9
    letters = string.ascii_uppercase
    seating_numbers = []

    # Start seating from letter 'C'
    current_letter_index = letters.index('C')

    # Generate seating numbers with a combination of letter and number
    for i in range(num_tickets):
        # Iterate through letters to find available seats
        for letter in letters[current_letter_index:]:
            available_seats = [seat for seat in range(1, MAX_SEATS_PER_ROW + 1) if f"{letter}{seat}" not in existing_seats]
            if available_seats:
                seat_number = available_seats[0]
                seating_numbers.append(f"{letter}{seat_number}")
                existing_seats.append(f"{letter}{seat_number}")
                break  # Break the loop once a seat is found for the current letter
        else:
            raise ValueError("Not enough available seats")

        # If seats for the current letter are exhausted, move to the next letter
        if len(available_seats) == 0:
            current_letter_index += 1

            # Check if all letters are exhausted
            if current_letter_index >= len(letters):
                raise ValueError("Not enough available seats")

    return seating_numbers


# Function to calculate ticket price
def calculate_ticket_price(show_id):
    # Replace this with your actual logic to calculate ticket price based on show details
    return 10  # Example price

MAX_SEATS_PER_SHOW = 100  # Define the maximum number of seats per show


from flask import Response

# Route to handle ticket booking
@app.route("/book_tickets", methods=["POST"])
def book_tickets():
    if request.method == 'POST':
        if 'user' not in session:
            return redirect(url_for('login'))  # Redirect to login if not logged in

        show_id = request.form['show_id']
        num_tickets = int(request.form['num_tickets'])
        user_id = session['user_id']  # Assuming you store the user ID in the session

        try:
            db = connect_to_database()
            cursor = db.cursor()

            # Fetch seating numbers for the selected show
            cursor.execute("SELECT SeatingNo FROM tickets WHERE ShowID = %s", (show_id,))
            existing_seats = [row[0] for row in cursor.fetchall()]

            # Generate seating numbers for new tickets
            seating_numbers = generate_seating_numbers(num_tickets, existing_seats)

            # Check if there are enough available seats
            if len(existing_seats) + num_tickets > MAX_SEATS_PER_SHOW:
                return "Not enough available seats"

            # Generate a single ticket ID for all booked tickets
            ticket_id = generate_ticket_id()

            # Generate ticket IDs and seating numbers
            ticket_ids = [ticket_id + i for i in range(num_tickets)]

            # Insert tickets into the database
            tickets_data = []
            booking_info_data = []
            for ticket_id, seating_no in zip(ticket_ids, seating_numbers):
                tickets_data.append((ticket_id, seating_no, user_id, show_id))
                # Insert booking information
                price = calculate_ticket_price(show_id)  # Assuming you have a function to calculate ticket price
                confirmation_code = generate_confirmation_code()  # Generate a confirmation code
                booking_info_data.append((ticket_id, user_id, show_id, seating_no, price, confirmation_code))
            


            # Insert payment data
            price_sum = sum([price for _, _, _, _, price, _ in booking_info_data])
            payment_type = "Debit Card"
            gift = "NULL"
            PM = "Online"

            # Determine the next TransactionID
            cursor.execute("SELECT MAX(TransactionID) FROM payment")
            last_transaction_id = cursor.fetchone()[0]
            if last_transaction_id:
                last_id_num = int(last_transaction_id[3:])
                next_id = "TXN" + str(last_id_num + 1).zfill(4)
            else:
                next_id = "TXN0001"

            cursor.execute("INSERT INTO payment (TransactionID, UserID, ShowID, SeatingNo, Amount, PaymentMethod, PaymentType, GiftcardID) "
                           "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)", (next_id, user_id, show_id, seating_no, price_sum, payment_type, PM, gift))

            db.commit()

            # Return a response with JavaScript for redirection after 5 seconds
            js_redirect = """
            <script>
                setTimeout(function() {
                    window.location.href = "/";
                }, 5000);
            </script>
            <p>Tickets booked successfully. Redirecting to homepage in 5 seconds...</p>
            """
            return js_redirect

        except mysql.connector.Error as err:
            print(f"Error booking tickets: {err}")
            return "An error occurred while booking tickets"
        finally:
            cursor.close()
            db.close()
    else:
        return "Invalid request"




@app.route("/search_movies")
def search_movies():
    if 'search_query' in request.args:
        search_query = request.args['search_query']
        try:
            db = connect_to_database()
            cursor = db.cursor()

            # Perform a SQL query to search for movies based on the search query
            cursor.execute("""
                SELECT m.MovieID, m.MovieName, m.MovieRate, s.ShowID, s.TheaterID, s.ShowTiming 
                FROM Movie m 
                JOIN Showtime s ON m.MovieID = s.MovieID 
                WHERE m.MovieName LIKE %s
            """, ('%' + search_query + '%',))
            search_results = cursor.fetchall()

            # Fetch latest movies for displaying on the homepage
            movies = get_latest_movies()

            return render_template("index.html", movies=movies, search_results=search_results, search_query=search_query)
        except mysql.connector.Error as err:
            print(f"Error searching for movies: {err}")
            return render_template("error.html", message="An error occurred while searching for movies.")
        finally:
            cursor.close()
            db.close()
    else:
        return render_template("error.html", message="No search query provided")



@app.route("/")
def homepage():

    """Renders the homepage with movie and show data."""
    movies = get_latest_movies()
    shows = get_now_showing_shows()
    return render_template("index.html", movies=movies, shows=shows)

@app.route('/logout')
def logout():
    session.pop('user', None)  # Clear the 'user' session variable
    return redirect(url_for('homepage'))  # Redirect to the homepage or any other page after logout

if __name__ == '__main__':
    app.run(debug=True)
