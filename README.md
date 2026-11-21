# 🚌 Crowdedness-Aware Journey Planner

An intelligent, machine-learning-based web application that predicts bus passenger demand and helps users identify less busy travel hours.

The system uses historical Delhi bus e-ticketing data to estimate passenger demand for different bus routes and travel times. It provides demand predictions, route analysis, peak-hour insights, and alternative travel recommendations.

## 🚀 Key Features

### 1. User Authentication
- User registration and login
- Secure password hashing
- Forgot password and password reset through email
- Change password
- User profile management

### 2. Passenger Demand Prediction
- Predicts expected passenger demand.
- Supports route, date, and hour selection.
- Categorizes predicted demand into Low, Medium, and High.
- Provides alternative travel-hour recommendations.

### 3. Prediction History
- Stores individual users' prediction records.
- Displays previous predictions.
- Provides demand statistics and visualizations.

### 4. Route Intelligence
- Analyzes passenger demand across bus routes.
- Identifies busiest and least busy routes.
- Displays route-wise demand statistics.

### 5. Peak-Hour Analysis
- Analyzes passenger demand across 24 hours.
- Identifies busiest and quietest hours.
- Displays hourly demand patterns.

### 6. Weekly Insights
- Analyzes demand across weekdays.
- Identifies the busiest and quietest days.
- Displays weekly demand trends.

### 7. Analytics Dashboard
- Interactive charts and visualizations.
- Passenger demand summaries.
- Historical data insights.

## 🧠 Machine Learning

The project uses an **XGBoost Regression Model** to predict passenger demand.

### Model Features
- Route
- Hour
- Day of the week
- Month
- Weekend indicator
- Previous day's passenger count
- Previous week's passenger count
- Rolling average passenger count

### Model Performance

| Metric | Result |
|---|---:|
| Mean Absolute Error (MAE) | 2.512 |
| Root Mean Squared Error (RMSE) | 4.271 |
| R² Score | 0.821 |
| Crowdedness Classification Accuracy | 59.26% |

These results are based on the project's evaluation dataset.

### Demand Categories

The predicted passenger count is converted into three demand categories:

- **Low:** 2 passengers or fewer
- **Medium:** More than 2 and up to 5 passengers
- **High:** More than 5 passengers

*Note: These categories represent ticket-based passenger demand, not actual physical bus occupancy or confirmed seat availability.*

## 🛠️ Technologies Used

### Frontend
- HTML5
- CSS3
- JavaScript
- Chart.js

### Backend
- Python
- Flask
- SQLite

### Machine Learning & Data Analysis
- XGBoost
- Scikit-learn
- Pandas
- NumPy
- Joblib

### Development Tools
- Visual Studio Code
- Google Colab
- Git
- GitHub

## 📁 Project Structure

```text
Crowdedness_Aware_Journey_Planner/
│
├── app.py
├── final_crowdedness_model.pkl
├── historical_bus_data.csv
├── requirements.txt
├── README.md
├── .gitignore
│
├── templates/
│   ├── index.html
│   ├── result.html
│   ├── history.html
│   ├── route_analysis.html
│   ├── bus_route_performance.html
│   ├── peak_hour_analysis.html
│   ├── weekly_analysis.html
│   ├── smart_recommendation.html
│   ├── advanced_dashboard.html
│   ├── project_info.html
│   ├── login.html
│   ├── register.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   ├── change_password.html
│   └── profile.html
│
└── static/
    ├── style.css
    └── script.js
```

## ⚙️ Installation and Setup

### Step 1: Clone the Repository

```bash
git clone https://github.com/sripooja07/journeyplanner
```

### Step 2: Open the Project Folder

```bash
cd Crowdedness-Aware-Journey-Planner
```

### Step 3: Create a Virtual Environment

```bash
python -m venv venv
```

### Step 4: Activate the Virtual Environment

For Windows:

```bash
venv\Scripts\activate
```

### Step 5: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 6: Configure Email Password Reset

Set the following environment variables if you want to use the password-reset email feature:

```text
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_google_app_password
```

Do not upload your actual email credentials to GitHub.

### Step 7: Run the Application

```bash
python app.py
```

### Step 8: Open in Browser

```text
http://127.0.0.1:5000
```

Register an account and log in to explore the application.

## 📊 Dataset

The project uses historical Delhi bus e-ticketing data.

The dataset is processed and aggregated to identify passenger demand patterns based on routes, dates, and hours.

## 🔮 Future Enhancements

- Integration with real-time bus passenger data.
- Live bus tracking.
- More advanced demand forecasting.
- Route optimization.
- Mobile application integration.
- Improved prediction accuracy using larger and more diverse datasets.

## 👩‍💻 Project Purpose

The main objective is to help passengers make informed travel-time decisions by understanding historical bus passenger demand patterns.

The application demonstrates how machine learning, data analytics, and web development can be combined to build an intelligent public transportation planning system.
