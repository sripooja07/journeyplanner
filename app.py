import os
import smtplib
import sqlite3
import secrets
import hashlib

from email.message import EmailMessage
from datetime import datetime, timedelta
from functools import wraps

import pandas as pd
import joblib

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# =====================================================
# FLASK CONFIGURATION
# =====================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    'SECRET_KEY',
    'development-key-change-before-deployment'
)

DATABASE = 'database/users.db'

MAIL_SERVER = 'smtp.gmail.com'
MAIL_PORT = 587

MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')


# =====================================================
# DATABASE SETUP
# =====================================================

os.makedirs('database', exist_ok=True)


def get_db_connection():

    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    return connection


def create_tables():

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            route TEXT NOT NULL,
            travel_date TEXT NOT NULL,
            hour INTEGER NOT NULL,
            predicted_passengers REAL NOT NULL,
            crowdedness TEXT NOT NULL,
            prediction_time TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            token_hash TEXT UNIQUE NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    connection.commit()
    connection.close()


create_tables()


# =====================================================
# LOAD MACHINE LEARNING MODEL
# =====================================================

model_data = joblib.load(
    'final_crowdedness_model.pkl'
)

model = model_data['model']

features = model_data['features']

low_threshold = model_data['low_threshold']

high_threshold = model_data['high_threshold']


# =====================================================
# LOAD HISTORICAL DATA
# =====================================================

historical_data = pd.read_csv(
    'historical_bus_data.csv'
)

historical_data['date'] = pd.to_datetime(
    historical_data['date'],
    errors='coerce'
)

historical_data['passenger_count'] = pd.to_numeric(
    historical_data['passenger_count'],
    errors='coerce'
)

historical_data['hour'] = pd.to_numeric(
    historical_data['hour'],
    errors='coerce'
)

historical_data = historical_data.dropna(
    subset=[
        'date',
        'route',
        'passenger_count',
        'hour'
    ]
).copy()

historical_data['hour'] = (
    historical_data['hour'].astype(int)
)

historical_data['day_of_week'] = (
    historical_data['date'].dt.dayofweek
)

historical_data['month'] = (
    historical_data['date'].dt.month
)

available_routes = sorted(
    historical_data['route'].dropna().unique().tolist()
)


# =====================================================
# LOGIN REQUIRED
# =====================================================

def login_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if 'user_id' not in session:

            flash('Please login to access this page.')

            return redirect(url_for('login'))

        return function(*args, **kwargs)

    return wrapper


# =====================================================
# SEND PASSWORD RESET EMAIL
# =====================================================

def send_reset_email(email, reset_link):

    if not MAIL_USERNAME or not MAIL_PASSWORD:

        raise ValueError(
            'Gmail credentials are not configured.'
        )

    msg = EmailMessage()

    msg['Subject'] = (
        'Crowdedness Journey Planner - Password Reset'
    )

    msg['From'] = MAIL_USERNAME

    msg['To'] = email

    msg.set_content(f"""
Hello,

We received a request to reset your password.

Click the link below to reset your password:

{reset_link}

This link expires in 30 minutes.

If you did not request this change,
you can ignore this email.

Regards,
Crowdedness-Aware Journey Planner
""")

    with smtplib.SMTP(
        MAIL_SERVER,
        MAIL_PORT,
        timeout=30
    ) as smtp:

        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()

        smtp.login(
            MAIL_USERNAME,
            MAIL_PASSWORD.replace(' ', '')
        )

        smtp.send_message(msg)


# =====================================================
# REGISTER
# =====================================================

@app.route('/register', methods=['GET', 'POST'])
def register():

    if 'user_id' in session:

        return redirect(url_for('home'))

    if request.method == 'POST':

        name = request.form.get(
            'name', ''
        ).strip()

        email = request.form.get(
            'email', ''
        ).strip().lower()

        password = request.form.get(
            'password', ''
        )

        confirm_password = request.form.get(
            'confirm_password', ''
        )

        if not name or not email or not password:

            flash('Please fill in all fields.')

            return redirect(url_for('register'))

        if len(name) < 2 or len(name) > 100:

            flash('Name must contain 2 to 100 characters.')

            return redirect(url_for('register'))

        if len(password) < 8:

            flash('Password must contain at least 8 characters.')

            return redirect(url_for('register'))

        if password != confirm_password:

            flash('Passwords do not match.')

            return redirect(url_for('register'))

        hashed_password = generate_password_hash(
            password
        )

        connection = get_db_connection()

        try:

            connection.execute(
                """
                INSERT INTO users
                (name, email, password, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    name,
                    email,
                    hashed_password,
                    datetime.now().strftime(
                        '%Y-%m-%d %H:%M:%S'
                    )
                )
            )

            connection.commit()

        except sqlite3.IntegrityError:

            flash('Email already registered.')

            return redirect(url_for('register'))

        finally:

            connection.close()

        flash('Registration successful! Please login.')

        return redirect(url_for('login'))

    return render_template('register.html')


# =====================================================
# LOGIN
# =====================================================

@app.route('/login', methods=['GET', 'POST'])
def login():

    if 'user_id' in session:

        return redirect(url_for('home'))

    if request.method == 'POST':

        email = request.form.get(
            'email', ''
        ).strip().lower()

        password = request.form.get(
            'password', ''
        )

        connection = get_db_connection()

        try:

            user = connection.execute(
                """
                SELECT *
                FROM users
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

        finally:

            connection.close()

        if user and check_password_hash(
            user['password'],
            password
        ):

            session.clear()

            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']

            flash('Login successful!')

            return redirect(url_for('home'))

        flash('Invalid email or password.')

        return redirect(url_for('login'))

    return render_template('login.html')


# =====================================================
# CHANGE PASSWORD
# =====================================================

@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():

    if request.method == 'POST':

        current_password = request.form.get(
            'current_password', ''
        )

        new_password = request.form.get(
            'new_password', ''
        )

        confirm_password = request.form.get(
            'confirm_password', ''
        )

        connection = get_db_connection()

        try:

            user = connection.execute(
                """
                SELECT *
                FROM users
                WHERE id = ?
                """,
                (session['user_id'],)
            ).fetchone()

            if not user:

                session.clear()

                flash('Account not found. Please login again.')

                return redirect(url_for('login'))

            if not check_password_hash(
                user['password'],
                current_password
            ):

                flash('Current password is incorrect.')

                return redirect(url_for('change_password'))

            if len(new_password) < 8:

                flash('New password must contain at least 8 characters.')

                return redirect(url_for('change_password'))

            if new_password != confirm_password:

                flash('Passwords do not match.')

                return redirect(url_for('change_password'))

            if check_password_hash(
                user['password'],
                new_password
            ):

                flash('New password must differ from current password.')

                return redirect(url_for('change_password'))

            connection.execute(
                """
                UPDATE users
                SET password = ?
                WHERE id = ?
                """,
                (
                    generate_password_hash(new_password),
                    session['user_id']
                )
            )

            connection.execute(
                """
                DELETE FROM password_reset_tokens
                WHERE user_id = ?
                """,
                (session['user_id'],)
            )

            connection.commit()

            flash('Password changed successfully!')

        finally:

            connection.close()

        return redirect(url_for('change_password'))

    return render_template('change_password.html')


# =====================================================
# PROFILE
# =====================================================

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():

    connection = get_db_connection()

    if request.method == 'POST':

        name = request.form.get(
            'name', ''
        ).strip()

        email = request.form.get(
            'email', ''
        ).strip().lower()

        if not name or not email:

            connection.close()

            flash('Please fill in all fields.')

            return redirect(url_for('profile'))

        if len(name) < 2 or len(name) > 100:

            connection.close()

            flash('Name must contain 2 to 100 characters.')

            return redirect(url_for('profile'))

        try:

            connection.execute(
                """
                UPDATE users
                SET name = ?, email = ?
                WHERE id = ?
                """,
                (
                    name,
                    email,
                    session['user_id']
                )
            )

            connection.commit()

            session['user_name'] = name
            session['user_email'] = email

        except sqlite3.IntegrityError:

            flash('Email already registered.')

            return redirect(url_for('profile'))

        finally:

            connection.close()

        flash('Profile updated successfully!')

        return redirect(url_for('profile'))

    user = connection.execute(
        """
        SELECT id, name, email, created_at
        FROM users
        WHERE id = ?
        """,
        (session['user_id'],)
    ).fetchone()

    connection.close()

    if not user:

        session.clear()

        return redirect(url_for('login'))

    return render_template(
        'profile.html',
        user=user
    )


# =====================================================
# LOGOUT
# =====================================================

@app.route('/logout')
@login_required
def logout():

    session.clear()

    flash('Logged out successfully.')

    return redirect(url_for('login'))


# =====================================================
# FORGOT PASSWORD
# =====================================================

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():

    if request.method == 'POST':

        email = request.form.get(
            'email', ''
        ).strip().lower()

        connection = get_db_connection()

        try:

            user = connection.execute(
                """
                SELECT *
                FROM users
                WHERE email = ?
                """,
                (email,)
            ).fetchone()

            if user:

                token = secrets.token_urlsafe(32)

                token_hash = hashlib.sha256(
                    token.encode()
                ).hexdigest()

                expires_at = (
                    datetime.now() +
                    timedelta(minutes=30)
                ).strftime('%Y-%m-%d %H:%M:%S')

                connection.execute(
                    """
                    DELETE FROM password_reset_tokens
                    WHERE user_id = ?
                    """,
                    (user['id'],)
                )

                connection.execute(
                    """
                    INSERT INTO password_reset_tokens
                    (user_id, token_hash, expires_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        user['id'],
                        token_hash,
                        expires_at
                    )
                )

                connection.commit()

                reset_link = url_for(
                    'reset_password',
                    token=token,
                    _external=True
                )

                try:

                    send_reset_email(
                        email,
                        reset_link
                    )

                except Exception:

                    app.logger.exception(
                        'Password reset email failed.'
                    )

                    connection.execute(
                        """
                        DELETE FROM password_reset_tokens
                        WHERE token_hash = ?
                        """,
                        (token_hash,)
                    )

                    connection.commit()

            flash(
                'If the account exists, a reset link will be sent.',
                'success'
            )

        finally:

            connection.close()

        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')


# =====================================================
# RESET PASSWORD
# =====================================================

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):

    token_hash = hashlib.sha256(
        token.encode()
    ).hexdigest()

    connection = get_db_connection()

    reset_record = connection.execute(
        """
        SELECT *
        FROM password_reset_tokens
        WHERE token_hash = ?
        """,
        (token_hash,)
    ).fetchone()

    if not reset_record:

        connection.close()

        flash('Invalid or expired reset link.')

        return redirect(url_for('forgot_password'))

    expires_at = datetime.strptime(
        reset_record['expires_at'],
        '%Y-%m-%d %H:%M:%S'
    )

    if datetime.now() > expires_at:

        connection.execute(
            """
            DELETE FROM password_reset_tokens
            WHERE token_hash = ?
            """,
            (token_hash,)
        )

        connection.commit()
        connection.close()

        flash('Reset link has expired.')

        return redirect(url_for('forgot_password'))

    if request.method == 'POST':

        new_password = request.form.get(
            'new_password', ''
        )

        confirm_password = request.form.get(
            'confirm_password', ''
        )

        if len(new_password) < 8:

            connection.close()

            flash('Password must contain at least 8 characters.')

            return render_template('reset_password.html')

        if new_password != confirm_password:

            connection.close()

            flash('Passwords do not match.')

            return render_template('reset_password.html')

        connection.execute(
            """
            UPDATE users
            SET password = ?
            WHERE id = ?
            """,
            (
                generate_password_hash(new_password),
                reset_record['user_id']
            )
        )

        connection.execute(
            """
            DELETE FROM password_reset_tokens
            WHERE token_hash = ?
            """,
            (token_hash,)
        )

        connection.commit()
        connection.close()

        flash('Password reset successful. Please login.')

        return redirect(url_for('login'))

    connection.close()

    return render_template('reset_password.html')


# =====================================================
# HISTORICAL FEATURES
# =====================================================

def get_historical_features(route, travel_date, hour):

    travel_date = pd.Timestamp(
        travel_date
    ).normalize()

    route_data = historical_data[
        (historical_data['route'] == route) &
        (historical_data['hour'] == hour)
    ].sort_values('date')

    past_data = route_data[
        route_data['date'] < travel_date
    ]['passenger_count']

    fallback = (
        past_data.median()
        if not past_data.empty
        else historical_data['passenger_count'].median()
    )

    previous_day = travel_date - pd.Timedelta(days=1)

    previous_week = travel_date - pd.Timedelta(days=7)

    lag_1 = route_data[
        route_data['date'] == previous_day
    ]['passenger_count']

    lag_7 = route_data[
        route_data['date'] == previous_week
    ]['passenger_count']

    lag_1_day = (
        lag_1.iloc[-1]
        if not lag_1.empty
        else fallback
    )

    lag_7_days = (
        lag_7.iloc[-1]
        if not lag_7.empty
        else fallback
    )

    rolling_mean = (
        past_data.tail(7).mean()
        if not past_data.empty
        else fallback
    )

    return {
        'route': route,
        'hour': hour,
        'day_of_week': travel_date.dayofweek,
        'month': travel_date.month,
        'is_weekend': int(travel_date.dayofweek >= 5),
        'lag_1_day': lag_1_day,
        'lag_7_days': lag_7_days,
        'rolling_mean': rolling_mean
    }


# =====================================================
# PREDICT DEMAND
# =====================================================

def predict_demand(route, travel_date, hour):

    input_data = pd.DataFrame([
        get_historical_features(
            route,
            travel_date,
            hour
        )
    ])

    input_data = input_data[features]

    prediction = max(
        0,
        float(model.predict(input_data)[0])
    )

    if prediction <= low_threshold:

        crowdedness = 'Low'

    elif prediction <= high_threshold:

        crowdedness = 'Medium'

    else:

        crowdedness = 'High'

    return round(prediction, 2), crowdedness


# =====================================================
# PREDICT ALL ROUTES
# =====================================================

def predict_all_routes(travel_date, hour):

    travel_date = pd.Timestamp(
        travel_date
    ).normalize()

    hour_data = historical_data[
        historical_data['hour'] == hour
    ]

    input_rows = []

    previous_day = travel_date - pd.Timedelta(days=1)

    previous_week = travel_date - pd.Timedelta(days=7)

    global_fallback = historical_data[
        'passenger_count'
    ].median()

    for route in available_routes:

        route_data = hour_data[
            hour_data['route'] == route
        ].sort_values('date')

        past_data = route_data[
            route_data['date'] < travel_date
        ]['passenger_count']

        fallback = (
            past_data.median()
            if not past_data.empty
            else global_fallback
        )

        lag_1 = route_data[
            route_data['date'] == previous_day
        ]['passenger_count']

        lag_7 = route_data[
            route_data['date'] == previous_week
        ]['passenger_count']

        input_rows.append({

            'route': route,

            'hour': hour,

            'day_of_week': travel_date.dayofweek,

            'month': travel_date.month,

            'is_weekend': int(
                travel_date.dayofweek >= 5
            ),

            'lag_1_day': (
                lag_1.iloc[-1]
                if not lag_1.empty
                else fallback
            ),

            'lag_7_days': (
                lag_7.iloc[-1]
                if not lag_7.empty
                else fallback
            ),

            'rolling_mean': (
                past_data.tail(7).mean()
                if not past_data.empty
                else fallback
            )

        })

    if not input_rows:
        return []

    input_data = pd.DataFrame(input_rows)

    input_data = input_data[features]

    predictions = model.predict(input_data)

    recommendations = []

    for route, passengers in zip(
        available_routes,
        predictions
    ):

        passengers = max(
            0,
            float(passengers)
        )

        if passengers <= low_threshold:

            crowdedness = 'Low'

        elif passengers <= high_threshold:

            crowdedness = 'Medium'

        else:

            crowdedness = 'High'

        recommendations.append({

            'route': route,

            'passengers': round(
                passengers, 2
            ),

            'crowdedness': crowdedness

        })

    recommendations.sort(
        key=lambda x: x['passengers']
    )

    return recommendations


# =====================================================
# SAVE PREDICTION
# =====================================================

def save_prediction(
    user_id,
    route,
    travel_date,
    hour,
    passengers,
    crowdedness
):

    connection = get_db_connection()

    try:

        connection.execute(
            """
            INSERT INTO predictions
            (
                user_id,
                route,
                travel_date,
                hour,
                predicted_passengers,
                crowdedness,
                prediction_time
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                route,
                str(travel_date),
                hour,
                passengers,
                crowdedness,
                datetime.now().strftime(
                    '%Y-%m-%d %H:%M:%S'
                )
            )
        )

        connection.commit()

    finally:

        connection.close()


# =====================================================
# HOME
# =====================================================

@app.route('/')
@login_required
def home():

    return render_template(
        'index.html',
        routes=available_routes,
        user_name=session.get('user_name')
    )


# =====================================================
# PREDICTION
# =====================================================

@app.route('/predict', methods=['POST'])
@login_required
def predict():

    route = request.form.get('route')

    date_input = request.form.get('travel_date')

    hour_input = request.form.get('hour')

    try:

        travel_date = datetime.strptime(
            date_input,
            '%Y-%m-%d'
        ).date()

        hour = int(hour_input)

        if hour < 0 or hour > 23:
            raise ValueError

        if route not in available_routes:
            raise ValueError

    except (ValueError, TypeError):

        return 'Invalid route, date or hour.', 400

    passengers, crowdedness = predict_demand(
        route,
        travel_date,
        hour
    )

    all_alternatives = []

    for alternative_hour in range(24):

        if alternative_hour == hour:
            continue

        alt_passengers, alt_crowdedness = predict_demand(
            route,
            travel_date,
            alternative_hour
        )

        all_alternatives.append({

            'hour': alternative_hour,

            'time': datetime.strptime(
                str(alternative_hour),
                '%H'
            ).strftime('%I:%M %p'),

            'passengers': alt_passengers,

            'crowdedness': alt_crowdedness

        })

    lower_alternatives = [
        item for item in all_alternatives
        if item['passengers'] < passengers
    ]

    if lower_alternatives:

        alternatives = sorted(
            lower_alternatives,
            key=lambda x: x['passengers']
        )[:3]

        recommendation_type = 'lower'

        recommendation_note = (
            'These times have lower predicted passenger demand.'
        )

    else:

        alternatives = sorted(
            all_alternatives,
            key=lambda x: x['passengers']
        )[:3]

        recommendation_type = 'best_available'

        recommendation_note = (
            'These are the three least-demand alternative times.'
        )

    save_prediction(
        session['user_id'],
        route,
        travel_date,
        hour,
        passengers,
        crowdedness
    )

    return render_template(
        'result.html',
        route=route,
        travel_date=travel_date,
        hour=hour,
        passengers=passengers,
        crowdedness=crowdedness,
        alternatives=alternatives,
        recommendation_note=recommendation_note,
        recommendation_type=recommendation_type
    )


# =====================================================
# PREDICTION HISTORY
# =====================================================

@app.route('/history')
@login_required
def history():

    connection = get_db_connection()

    try:

        history_data = connection.execute(
            """
            SELECT *
            FROM predictions
            WHERE user_id = ?
            ORDER BY id DESC
            """,
            (session['user_id'],)
        ).fetchall()

    finally:

        connection.close()

    records = [
        dict(row)
        for row in history_data
    ]

    low_count = sum(
        1 for record in records
        if record['crowdedness'] == 'Low'
    )

    medium_count = sum(
        1 for record in records
        if record['crowdedness'] == 'Medium'
    )

    high_count = sum(
        1 for record in records
        if record['crowdedness'] == 'High'
    )

    total_predictions = len(records)

    average_passengers = round(
        sum(
            float(record['predicted_passengers'])
            for record in records
        ) / total_predictions,
        2
    ) if total_predictions else 0

    chart_labels = [
        record['travel_date']
        for record in reversed(records)
    ]

    chart_values = [
        float(record['predicted_passengers'])
        for record in reversed(records)
    ]

    return render_template(
        'history.html',
        records=records,
        low_count=low_count,
        medium_count=medium_count,
        high_count=high_count,
        total_predictions=total_predictions,
        average_passengers=average_passengers,
        chart_labels=chart_labels,
        chart_values=chart_values
    )


# =====================================================
# ROUTE INTELLIGENCE + BUS ROUTE PERFORMANCE
# =====================================================

@app.route('/route-analysis', endpoint='route_analysis')
@app.route('/bus-route-performance', endpoint='bus_route_performance')
@login_required
def route_intelligence():

    route_summary = historical_data.groupby(
        'route'
    ).agg(
        average_passengers=('passenger_count', 'mean'),
        total_passengers=('passenger_count', 'sum'),
        total_observations=('passenger_count', 'count')
    ).reset_index()

    # Calculate demand categories
    demand_data = historical_data.copy()

    demand_data['demand_level'] = 'High'

    demand_data.loc[
        demand_data['passenger_count'] <= low_threshold,
        'demand_level'
    ] = 'Low'

    demand_data.loc[
        (
            (demand_data['passenger_count'] > low_threshold) &
            (demand_data['passenger_count'] <= high_threshold)
        ),
        'demand_level'
    ] = 'Medium'

    demand_counts = demand_data.groupby(
        ['route', 'demand_level']
    ).size().unstack(fill_value=0)

    for level in ['Low', 'Medium', 'High']:

        if level not in demand_counts.columns:
            demand_counts[level] = 0

    demand_counts = demand_counts[
        ['Low', 'Medium', 'High']
    ]

    route_summary = route_summary.merge(
        demand_counts,
        left_on='route',
        right_index=True,
        how='left'
    )

    route_summary['average_passengers'] = (
        route_summary['average_passengers'].round(2)
    )

    route_summary['total_passengers'] = (
        route_summary['total_passengers'].round().astype(int)
    )

    route_summary['total_observations'] = (
        route_summary['total_observations'].astype(int)
    )

    for level in ['Low', 'Medium', 'High']:

        route_summary[level] = (
            route_summary[level].fillna(0).astype(int)
        )

    route_summary = route_summary.sort_values(
        'average_passengers',
        ascending=False
    ).reset_index(drop=True)

    route_summary['rank'] = route_summary.index + 1

    total_routes = len(route_summary)

    total_observations = len(historical_data)

    total_passengers = int(
        historical_data['passenger_count'].sum()
    )

    overall_average = round(
        historical_data['passenger_count'].mean(), 2
    )

    busiest_route = route_summary.iloc[0]

    least_busy_route = route_summary.iloc[-1]

    chart_data = route_summary.head(15)

    route_records = []

    for _, row in route_summary.iterrows():

        route_records.append({

            'route': str(row['route']),

            'total_predictions': int(
                row['total_observations']
            ),

            'average_passengers': float(
                row['average_passengers']
            ),

            'total_passengers': int(
                row['total_passengers']
            ),

            'low_count': int(row['Low']),

            'medium_count': int(row['Medium']),

            'high_count': int(row['High']),

            'rank': int(row['rank'])

        })

    return render_template(
        'bus_route_performance.html',
        total_routes=total_routes,
        total_observations=total_observations,
        total_passengers=total_passengers,
        overall_average=overall_average,
        busiest_route=busiest_route['route'],
        busiest_route_average=busiest_route['average_passengers'],
        least_busy_route=least_busy_route['route'],
        least_busy_route_average=least_busy_route['average_passengers'],
        route_labels=chart_data['route'].astype(str).tolist(),
        route_values=chart_data['average_passengers'].tolist(),
        low_values=chart_data['Low'].astype(int).tolist(),
        medium_values=chart_data['Medium'].astype(int).tolist(),
        high_values=chart_data['High'].astype(int).tolist(),
        route_records=route_records
    )


# =====================================================
# PEAK HOUR ANALYSIS - FIXED
# =====================================================

@app.route('/peak-hour-analysis')
@login_required
def peak_hour_analysis():

    hourly_data = historical_data.copy()

    hourly_summary = (
        hourly_data.groupby('hour')['passenger_count']
        .agg(['mean', 'count'])
        .reindex(range(24), fill_value=0)
    )

    hourly_records = []

    for hour in range(24):

        average = round(
            float(hourly_summary.loc[hour, 'mean']), 2
        )

        observations = int(
            hourly_summary.loc[hour, 'count']
        )

        hour_data = hourly_data[
            hourly_data['hour'] == hour
        ]

        low_count = int(
            (hour_data['passenger_count'] <= low_threshold).sum()
        )

        medium_count = int(
            (
                (hour_data['passenger_count'] > low_threshold) &
                (hour_data['passenger_count'] <= high_threshold)
            ).sum()
        )

        high_count = int(
            (hour_data['passenger_count'] > high_threshold).sum()
        )

        hourly_records.append({

            'hour': hour,

            'average_passengers': average,

            'total_observations': observations,

            'low_count': low_count,

            'medium_count': medium_count,

            'high_count': high_count

        })

    available_hours = [
        record for record in hourly_records
        if record['total_observations'] > 0
    ]

    if available_hours:

        busiest = max(
            available_hours,
            key=lambda x: x['average_passengers']
        )

        quietest = min(
            available_hours,
            key=lambda x: x['average_passengers']
        )

        busiest_hour = datetime.strptime(
            str(busiest['hour']),
            '%H'
        ).strftime('%I:00 %p')

        quietest_hour = datetime.strptime(
            str(quietest['hour']),
            '%H'
        ).strftime('%I:00 %p')

        busiest_demand = busiest['average_passengers']

        quietest_demand = quietest['average_passengers']

    else:

        busiest_hour = 'No data'

        quietest_hour = 'No data'

        busiest_demand = 0

        quietest_demand = 0

    return render_template(
        'peak_hour_analysis.html',
        hourly_records=hourly_records,
        hour_labels=[
            record['hour'] for record in hourly_records
        ],
        hour_values=[
            record['average_passengers']
            for record in hourly_records
        ],
        busiest_hour=busiest_hour,
        quietest_hour=quietest_hour,
        busiest_demand=busiest_demand,
        quietest_demand=quietest_demand
    )


# =====================================================
# WEEKLY INSIGHTS - FIXED
# =====================================================

@app.route('/weekly-analysis')
@login_required
def weekly_analysis():

    weekly_data = historical_data.copy()

    day_names = {
        0: 'Monday',
        1: 'Tuesday',
        2: 'Wednesday',
        3: 'Thursday',
        4: 'Friday',
        5: 'Saturday',
        6: 'Sunday'
    }

    weekly_data['day_of_week'] = (
        weekly_data['date'].dt.dayofweek
    )

    actual_summary = (
        weekly_data.groupby('day_of_week')['passenger_count']
        .mean()
    )

    weekly_summary = actual_summary.reindex(
        range(7),
        fill_value=0
    )

    day_labels = [
        day_names[i] for i in range(7)
    ]

    day_values = [
        round(float(weekly_summary[i]), 2)
        for i in range(7)
    ]

    if not actual_summary.empty:

        busiest_index = actual_summary.idxmax()

        quietest_index = actual_summary.idxmin()

        busiest_day = day_names[busiest_index]

        quietest_day = day_names[quietest_index]

        weekly_average = round(
            weekly_data['passenger_count'].mean(),
            2
        )

    else:

        busiest_day = 'No data'

        quietest_day = 'No data'

        weekly_average = 0

    return render_template(
        'weekly_analysis.html',
        day_labels=day_labels,
        day_values=day_values,
        busiest_day=busiest_day,
        quietest_day=quietest_day,
        weekly_average=weekly_average,
        total_records=len(weekly_data)
    )


# =====================================================
# SMART RECOMMENDATION
# =====================================================

@app.route(
    '/smart-recommendation',
    methods=['GET', 'POST']
)
@login_required
def smart_recommendation():

    recommendations = []

    best_route = None

    selected_date = ''

    selected_hour = None

    chart_records = []

    error = None

    if request.method == 'POST':

        date_input = request.form.get(
            'travel_date', ''
        ).strip()

        hour_input = request.form.get(
            'hour', ''
        ).strip()

        try:

            selected_date = datetime.strptime(
                date_input,
                '%Y-%m-%d'
            ).date()

            selected_hour = int(hour_input)

            if selected_hour < 0 or selected_hour > 23:
                raise ValueError

        except (ValueError, TypeError):

            error = 'Please enter a valid date and hour.'

        if not error:

            recommendations = predict_all_routes(
                selected_date,
                selected_hour
            )

            if recommendations:

                best_route = recommendations[0]

                chart_records = recommendations[:10]

    return render_template(
        'smart_recommendation.html',
        recommendations=recommendations,
        best_route=best_route,
        selected_date=selected_date,
        selected_hour=selected_hour,
        chart_records=chart_records,
        error=error
    )


# =====================================================
# ANALYTICS CENTER
# =====================================================

@app.route('/advanced-dashboard')
@login_required
def advanced_dashboard():

    total_routes = historical_data['route'].nunique()

    total_observations = len(historical_data)

    overall_average = round(
        historical_data['passenger_count'].mean(),
        2
    )

    route_summary = historical_data.groupby(
        'route'
    ).agg(
        average_passengers=('passenger_count', 'mean'),
        total_passengers=('passenger_count', 'sum'),
        total_observations=('passenger_count', 'count')
    ).reset_index()

    route_summary = route_summary.sort_values(
        'average_passengers',
        ascending=False
    )

    busiest_route = route_summary.iloc[0]

    least_busy_route = route_summary.iloc[-1]

    top_routes = route_summary.head(10)

    hourly_summary = historical_data.groupby(
        'hour'
    )['passenger_count'].mean().reindex(
        range(24),
        fill_value=0
    )

    hour_labels = [
        datetime.strptime(
            str(hour),
            '%H'
        ).strftime('%I %p')
        for hour in hourly_summary.index
    ]

    low_count = int(
        (
            historical_data['passenger_count'] <= low_threshold
        ).sum()
    )

    medium_count = int(
        (
            (historical_data['passenger_count'] > low_threshold) &
            (historical_data['passenger_count'] <= high_threshold)
        ).sum()
    )

    high_count = int(
        (
            historical_data['passenger_count'] > high_threshold
        ).sum()
    )

    return render_template(
        'advanced_dashboard.html',
        total_routes=int(total_routes),
        total_observations=int(total_observations),
        overall_average=overall_average,
        busiest_route=busiest_route['route'],
        busiest_demand=round(
            busiest_route['average_passengers'], 2
        ),
        least_busy_route=least_busy_route['route'],
        least_busy_demand=round(
            least_busy_route['average_passengers'], 2
        ),
        route_labels=top_routes['route'].astype(str).tolist(),
        route_values=top_routes['average_passengers'].round(2).tolist(),
        hour_labels=hour_labels,
        hour_values=hourly_summary.round(2).tolist(),
        low_count=low_count,
        medium_count=medium_count,
        high_count=high_count
    )


# =====================================================
# PROJECT INFORMATION
# =====================================================

@app.route('/project-info')
@login_required
def project_info():

    return render_template(
        'project_info.html'
    )


# =====================================================
# RUN APPLICATION
# =====================================================

if __name__ == '__main__':

    app.run(debug=True)